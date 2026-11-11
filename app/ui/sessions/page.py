from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QPlainTextEdit, QVBoxLayout

from app.core import events as ev
from app.core.bootstrap import AppContext
from app.database.models import PlaySession, SessionStatus
from app.ui.widgets import (
    Col, DataTable, Page, account_combo, button, combo_data, game_combo, info, label, row,
    run_dialog, safe, status_col,
)
from app.ui.widgets import fmt_duration as dur


class SessionDialog(QDialog):
    """Associa conta/jogo a uma sessão detectada ou cria uma sessão manual."""

    def __init__(self, ctx: AppContext, session: PlaySession | None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Sessão #{session.id}" if session else "Nova sessão manual")
        self.setMinimumWidth(420)
        self.account = account_combo(ctx, selected=session.account_id if session else None)
        self.game = game_combo(ctx, selected=session.game_id if session else None)
        self.notes = QPlainTextEdit(session.notes if session else "")
        self.notes.setFixedHeight(70)
        form = QFormLayout()
        form.addRow("Conta", self.account)
        form.addRow("Jogo", self.game)
        form.addRow("Observações", self.notes)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        box = QVBoxLayout(self)
        box.addLayout(form)
        hint = label("O processo não informa qual conta está logada: confirme a associação "
                     "olhando a janela do jogo.", "muted")
        hint.setWordWrap(True)
        box.addWidget(hint)
        box.addWidget(buttons)

    def values(self) -> tuple[int | None, int | None, str]:
        return combo_data(self.account), self.game.currentData(), self.notes.toPlainText()


class SessionsPage(Page):
    title = "Sessões"
    subtitle = "Clientes Roblox abertos neste computador são detectados automaticamente."
    events = (ev.SESSIONS_CHANGED, ev.ACCOUNTS_CHANGED)
    auto_refresh = True

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.root.addLayout(row(
            button("Sessão manual", self.add_manual, "primary", icon="plus"),
            button("Verificar agora", self.scan, icon="refresh"),
            button("Associar conta/jogo", self.assign, icon="link-variant"),
            button("Marcar/limpar problema", self.flag, icon="flag-outline"),
            button("Encerrar acompanhamento", self.end, "danger", icon="stop-circle-outline",
                   tip="Encerra apenas o registro no RFM — o jogo não é fechado."), 1,
        ))
        common = [
            Col("#", lambda s: s.id, width=50, right=True),
            Col("Conta", lambda s: s.account.username if s.account else None, width=140),
            Col("Jogo", lambda s: s.game.name if s.game else None, width=150),
        ]
        self.open_table = DataTable(common + [
            status_col("Status", SessionStatus.LABELS),
            Col("Origem", lambda s: "Manual" if s.manual else f"{s.process_name} · PID {s.pid}", width=200),
            Col("Início", lambda s: s.started_at, width=125),
            Col("Duração", lambda s: s.elapsed_s, fmt=dur, width=85),
            Col("CPU média", lambda s: None if s.manual else s.cpu_avg, fmt=lambda v: f"{v:.1f}%", width=80, right=True),
            Col("Memória", lambda s: None if s.manual else s.memory_mb, fmt=lambda v: f"{v:.0f} MB", width=80, right=True),
            Col("Pico", lambda s: None if s.manual else s.memory_peak_mb, fmt=lambda v: f"{v:.0f} MB", right=True),
        ])
        self.open_table.setColumnWidth(3, 150)
        self.open_table.row_activated.connect(lambda _s: self.assign())
        self.history_table = DataTable(common + [
            Col("Início", lambda s: s.started_at, width=140), Col("Fim", lambda s: s.ended_at, width=140),
            Col("Duração", lambda s: s.duration_s, fmt=dur, width=100),
            Col("CPU média", lambda s: None if s.manual else s.cpu_avg, fmt=lambda v: f"{v:.1f}%", width=90, right=True),
            Col("Pico de memória", lambda s: None if s.manual else s.memory_peak_mb, fmt=lambda v: f"{v:.0f} MB", width=120, right=True),
            Col("Observações", lambda s: s.notes or None),
        ])
        self.summary = label("", "muted")
        self.root.addWidget(label("Sessões em andamento", "sectionTitle"))
        self.root.addWidget(self.open_table, 3)
        self.root.addWidget(self.summary)
        self.root.addWidget(label("Histórico (últimas 500)", "sectionTitle"))
        self.root.addWidget(self.history_table, 2)

    def refresh(self) -> None:
        sessions = self.ctx.sessions.open_sessions()
        self.open_table.set_rows(sessions)
        self.history_table.set_rows(self.ctx.sessions.history())
        problems = sum(s.status in (SessionStatus.IDLE, SessionStatus.PROBLEM) for s in sessions)
        unassigned = sum(s.account_id is None for s in sessions)
        names = ", ".join(sorted(self.ctx.sessions.process_names()))
        self.summary.setText(
            f"{len(sessions)} sessão(ões) abertas · {problems} com atenção · {unassigned} sem conta associada"
            f"   |   Processos monitorados: {names}"
        )

    @safe
    def scan(self) -> None:
        self.ctx.sessions.scan()
        self.refresh()

    @safe
    def add_manual(self) -> None:
        dialog = SessionDialog(self.ctx, None, self)
        run_dialog(dialog, lambda: self.ctx.sessions.start_manual(*dialog.values()))

    @safe
    def assign(self) -> None:
        session = self.open_table.require_selected("uma sessão em andamento")
        dialog = SessionDialog(self.ctx, session, self)
        run_dialog(dialog, lambda: self.ctx.sessions.assign(session.id, *dialog.values()))

    @safe
    def flag(self) -> None:
        session = self.open_table.require_selected("uma sessão em andamento")
        self.ctx.sessions.set_problem(session.id, session.status != SessionStatus.PROBLEM)

    @safe
    def end(self) -> None:
        session = self.open_table.require_selected("uma sessão em andamento")
        self.ctx.sessions.end(session.id)
        if not session.manual:
            info(self, "Acompanhamento encerrado. Se o cliente continuar aberto, uma nova sessão "
                       "será registrada na próxima verificação.")
