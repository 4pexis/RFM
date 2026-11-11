"""SESSION MANAGER: acompanhamento de sessões locais.

O que este módulo faz:
- detecta processos do cliente Roblox já abertos (pelo nome do executável);
- registra início, encerramento, duração e consumo de CPU/memória;
- permite associar manualmente cada sessão a uma conta e a um jogo;
- permite registrar sessões manuais (sem processo);
- abre uma experiência pelo link oficial ``roblox://`` ou pelo site.

O que ele deliberadamente NÃO faz: abrir múltiplas instâncias contornando o
cliente (mutex, arquivos internos), ler memória, injetar código ou usar
cookies/tokens. Um processo não revela de forma confiável qual conta está
logada, portanto a associação conta ↔ sessão é sempre confirmada pelo usuário.
"""
from __future__ import annotations

import os
import sys
import webbrowser
from datetime import datetime, timedelta, timezone
from typing import Sequence

from sqlalchemy import func, select

from app.core import events as ev
from app.core.security import Permission, ValidationError, clean_text, validate_experience_id
from app.database.models import Account, Game, PlaySession, SessionStatus, utcnow
from app.database.repositories import SessionRepository
from app.services.monitoring import ProcessInfo, ProcessProvider

from .base import BaseManager
from .settings_manager import SettingsManager


class SessionManager(BaseManager):
    def __init__(self, *args, config: SettingsManager, provider: ProcessProvider, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config = config
        self.provider = provider
        self.last_processes: list[ProcessInfo] = []

    # ---------------------------------------------------------------- detecção

    def process_names(self) -> set[str]:
        raw = str(self.config.get("sessions.process_names"))
        return {name.strip() for name in raw.split(",") if name.strip()}

    def scan(self) -> bool:
        """Sincroniza as sessões com os processos existentes. Retorna True se
        alguma sessão foi aberta, encerrada ou mudou de status."""
        processes = self.provider.list(self.process_names())
        self.last_processes = processes
        by_key = {(p.pid, round(p.create_time, 2)): p for p in processes}
        idle_cpu = float(self.config.get("sessions.idle_cpu_percent"))
        idle_after = timedelta(minutes=float(self.config.get("sessions.idle_minutes")))
        now = utcnow()
        changed = False

        with self.db.session() as s:
            repo = SessionRepository(s)
            known: set[tuple[int, float]] = set()
            for session in repo.open_sessions():
                if session.manual or session.pid is None:
                    continue
                key = (session.pid, round(session.process_created or 0.0, 2))
                proc = by_key.get(key)
                if proc is None:  # o processo terminou
                    self._close(session, session.last_seen or now)
                    self._audit(s, "session.end", "session", session.id, f"PID {session.pid} encerrado")
                    if session.account_id:
                        self._audit(s, "session.end", "account", session.account_id,
                                    f"Sessão #{session.id} encerrada ({session.duration_s // 60} min)")
                    changed = True
                    continue
                known.add(key)
                session.last_seen = now
                session.cpu_avg = (session.cpu_avg * session.cpu_samples + proc.cpu_percent) / (session.cpu_samples + 1)
                session.cpu_samples += 1
                session.memory_mb = proc.memory_mb
                session.memory_peak_mb = max(session.memory_peak_mb, proc.memory_mb)
                # Ociosidade prolongada costuma indicar desconexão ou travamento.
                if proc.cpu_percent <= idle_cpu:
                    session.idle_since = session.idle_since or now
                else:
                    session.idle_since = None
                if session.status != SessionStatus.PROBLEM:
                    idle = session.idle_since is not None and now - session.idle_since >= idle_after
                    status = SessionStatus.IDLE if idle else SessionStatus.ACTIVE
                    if status != session.status:
                        session.status = status
                        changed = True

            for key, proc in by_key.items():
                if key in known:
                    continue
                started = (datetime.fromtimestamp(proc.create_time, timezone.utc).replace(tzinfo=None)
                           if proc.create_time else now)
                session = repo.add(PlaySession(
                    pid=proc.pid, process_name=proc.name, process_created=proc.create_time,
                    started_at=min(started, now), last_seen=now, memory_mb=proc.memory_mb,
                    memory_peak_mb=proc.memory_mb, status=SessionStatus.ACTIVE,
                ))
                self._audit(s, "session.start", "session", session.id, f"{proc.name} (PID {proc.pid})")
                changed = True

        if changed:
            self.events.publish(ev.SESSIONS_CHANGED)
        return changed

    @staticmethod
    def _close(session: PlaySession, when: datetime) -> None:
        session.ended_at = max(when, session.started_at)
        session.duration_s = int((session.ended_at - session.started_at).total_seconds())
        session.status = SessionStatus.ENDED

    # ------------------------------------------------------- operações manuais

    def start_manual(self, account_id: int | None, game_id: int | None, notes: str = "") -> PlaySession:
        self.access.require(Permission.WRITE)
        with self.db.session() as s:
            session = SessionRepository(s).add(PlaySession(
                account_id=account_id, game_id=game_id, manual=True, process_name="(manual)",
                notes=clean_text(notes, 2000, "observações"), last_seen=utcnow(),
            ))
            s.refresh(session)
            self._audit(s, "session.start", "session", session.id, "registro manual")
            self._touch_account(s, account_id, f"Sessão manual #{session.id} iniciada")
        self.events.publish(ev.SESSIONS_CHANGED)
        return session

    def end(self, session_id: int) -> PlaySession:
        """Encerra o ACOMPANHAMENTO da sessão (não fecha o processo)."""
        self.access.require(Permission.WRITE)
        with self.db.session() as s:
            session = SessionRepository(s).require(session_id)
            if session.ended_at is None:
                self._close(session, utcnow())
                self._audit(s, "session.end", "session", session.id, "encerrada manualmente")
                self._touch_account(s, session.account_id,
                                    f"Sessão #{session.id} encerrada ({session.duration_s // 60} min)")
        self.events.publish(ev.SESSIONS_CHANGED)
        return session

    def assign(self, session_id: int, account_id: int | None, game_id: int | None,
               notes: str | None = None) -> PlaySession:
        self.access.require(Permission.WRITE)
        with self.db.session() as s:
            session = SessionRepository(s).require(session_id)
            if account_id is not None and s.get(Account, account_id) is None:
                raise ValidationError("Conta não encontrada.")
            if game_id is not None and s.get(Game, game_id) is None:
                raise ValidationError("Jogo não encontrado.")
            session.account_id, session.game_id = account_id, game_id
            if notes is not None:
                session.notes = clean_text(notes, 2000, "observações")
            s.flush()
            s.refresh(session)
            self._audit(s, "session.assign", "session", session.id,
                        f"conta={account_id}, jogo={game_id}")
            self._touch_account(s, account_id, f"Associada à sessão #{session.id}")
        self.events.publish(ev.SESSIONS_CHANGED)
        return session

    def set_problem(self, session_id: int, problem: bool) -> None:
        self.access.require(Permission.WRITE)
        with self.db.session() as s:
            session = SessionRepository(s).require(session_id)
            if session.ended_at is None:
                session.status = SessionStatus.PROBLEM if problem else SessionStatus.ACTIVE
                self._audit(s, "session.flag", "session", session.id, session.status)
        self.events.publish(ev.SESSIONS_CHANGED)

    def _touch_account(self, s, account_id: int | None, details: str) -> None:
        if account_id is None:
            return
        account = s.get(Account, account_id)
        if account is not None:
            account.last_activity = utcnow()
            self._audit(s, "session", "account", account_id, details)

    # ------------------------------------------------------------------ leitura

    def open_sessions(self) -> Sequence[PlaySession]:
        with self.db.session() as s:
            return SessionRepository(s).open_sessions()

    def history(self, account_id: int | None = None, limit: int = 500) -> Sequence[PlaySession]:
        stmt = select(PlaySession).where(PlaySession.ended_at.is_not(None))
        if account_id is not None:
            stmt = stmt.where(PlaySession.account_id == account_id)
        with self.db.session() as s:
            return s.scalars(stmt.order_by(PlaySession.ended_at.desc()).limit(limit)).unique().all()

    def problems(self) -> Sequence[PlaySession]:
        with self.db.session() as s:
            return SessionRepository(s).list(
                PlaySession.ended_at.is_(None),
                PlaySession.status.in_((SessionStatus.IDLE, SessionStatus.PROBLEM)),
            )

    def open_count(self) -> int:
        with self.db.session() as s:
            return SessionRepository(s).count(PlaySession.ended_at.is_(None))

    def total_seconds(self) -> int:
        with self.db.session() as s:
            closed = s.scalar(select(func.coalesce(func.sum(PlaySession.duration_s), 0))) or 0
            running = SessionRepository(s).open_sessions()
        return int(closed) + sum(session.elapsed_s for session in running)

    # ---------------------------------------------------------- abrir experiência

    @staticmethod
    def experience_urls(experience_id: str) -> tuple[str, str]:
        place = validate_experience_id(experience_id)
        if not place:
            raise ValidationError("Este jogo não tem identificador de experiência cadastrado.")
        return (f"roblox://experiences/start?placeId={place}", f"https://www.roblox.com/games/{place}")

    def launch(self, experience_id: str, via_browser: bool = False) -> str:
        """Abre a experiência pelo link oficial do Roblox (aplicativo) ou pelo site.
        A conta usada é a que estiver logada no aplicativo/navegador do usuário."""
        deep_link, web_url = self.experience_urls(experience_id)
        if via_browser or sys.platform != "win32":
            webbrowser.open(web_url)
            return web_url
        try:
            os.startfile(deep_link)  # type: ignore[attr-defined]
            return deep_link
        except OSError:  # aplicativo Roblox não instalado/registrado
            webbrowser.open(web_url)
            return web_url
