from __future__ import annotations

from PySide6.QtWidgets import QFrame, QGridLayout, QScrollArea, QVBoxLayout, QWidget

from app.core import events as ev
from app.database.models import AccountStatus
from app.ui import theme
from app.ui.widgets import ChartCard, Page, StatCard, fmt_duration


class DashboardPage(Page):
    title = "Dashboard"
    subtitle = "Visão geral de contas, jogos, tarefas e sessões — atualizada automaticamente."
    events = (ev.ACCOUNTS_CHANGED, ev.GAMES_CHANGED, ev.TASKS_CHANGED, ev.PROGRESS_CHANGED,
              ev.SESSIONS_CHANGED)
    auto_refresh = True

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        content = QWidget()
        box = QVBoxLayout(content)
        box.setContentsMargins(0, 0, 8, 0)
        box.setSpacing(12)

        self.cards = {
            "accounts": StatCard("Total de contas"),
            "games": StatCard("Total de jogos"),
            "active": StatCard("Contas ativas", theme.GREEN),
            "paused": StatCard("Contas pausadas", theme.YELLOW),
            "pending": StatCard("Tarefas pendentes", theme.YELLOW),
            "done": StatCard("Tarefas concluídas", theme.GREEN),
            "sessions": StatCard("Sessões acompanhadas", theme.CYAN),
            "time": StatCard("Tempo total registrado", theme.ACCENT),
        }
        grid = QGridLayout()
        grid.setSpacing(12)
        for i, card in enumerate(self.cards.values()):
            grid.addWidget(card, i // 4, i % 4)
        box.addLayout(grid)

        self.per_game = ChartCard("Contas por jogo", 320)
        self.status = ChartCard("Distribuição de status", 320)
        self.activity = ChartCard("Atividade diária (últimos 14 dias)")
        self.productivity = ChartCard("Produtividade semanal (tarefas concluídas)")
        self.progress = ChartCard("Progresso por jogo (registros)", 320)
        charts = QGridLayout()
        charts.setSpacing(12)
        charts.addWidget(self.per_game, 0, 0)
        charts.addWidget(self.status, 0, 1)
        charts.addWidget(self.activity, 1, 0)
        charts.addWidget(self.productivity, 1, 1)
        charts.addWidget(self.progress, 2, 0, 1, 2)
        box.addLayout(charts)
        box.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        self.root.addWidget(scroll, 1)

    def refresh(self) -> None:
        reports = self.ctx.reports
        s = reports.summary()
        self.cards["accounts"].set(s.total_accounts)
        self.cards["games"].set(s.total_games)
        share = f"{s.active_accounts / s.total_accounts:.0%} do total" if s.total_accounts else ""
        self.cards["active"].set(s.active_accounts, share)
        self.cards["paused"].set(s.paused_accounts)
        self.cards["pending"].set(s.pending_tasks)
        self.cards["done"].set(s.done_tasks)
        problems = len(self.ctx.sessions.problems())
        self.cards["sessions"].set(s.open_sessions, f"{problems} com problema" if problems else "em aberto agora")
        self.cards["time"].set(fmt_duration(s.total_seconds))

        per_game = [(name, total) for name, total in reports.accounts_per_game() if total][:12]
        self.per_game.set_bars([n for n, _ in per_game], [t for _, t in per_game], horizontal=True)

        labels = AccountStatus.LABELS
        colors = {label: theme.STATUS_COLORS[key] for key, label in labels.items()}
        distribution = reports.status_distribution()
        self.status.set_pie(distribution, [colors[name] for name, _ in distribution])

        daily = reports.daily_activity(14)
        self.activity.set_lines([d.strftime("%d/%m") for d, _ in daily], {"Operações": [t for _, t in daily]})

        week = reports.weekly_productivity(7)
        names = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
        self.productivity.set_bars([f"{names[d.weekday()]} {d.day:02d}" for d, _ in week],
                                   [t for _, t in week], color=theme.GREEN)

        progress = [(name, total) for name, total in reports.progress_per_game() if total][:12]
        self.progress.set_bars([n for n, _ in progress], [t for _, t in progress], horizontal=True,
                               color=theme.PURPLE)
