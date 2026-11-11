from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtWidgets import QComboBox, QFileDialog, QGridLayout, QTabWidget, QVBoxLayout, QWidget

from app.core import events as ev
from app.database.models import utcnow
from app.ui import theme
from app.ui.widgets import (
    ChartCard, Col, DataTable, Page, StatCard, button, fill_combo, fmt_duration, info, label, row,
    safe,
)

_PERIODS = [("Hoje", 0), ("Últimos 7 dias", 7), ("Últimos 30 dias", 30), ("Últimos 90 dias", 90),
            ("Todo o período", -1)]


class ReportsPage(Page):
    title = "Relatórios"
    subtitle = "Tempo de operação, produtividade e histórico de atividades."
    events = (ev.TASKS_CHANGED, ev.SESSIONS_CHANGED, ev.PROGRESS_CHANGED)

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.period, self.group = QComboBox(), QComboBox()
        fill_combo(self.period, _PERIODS)
        self.period.setCurrentIndex(1)
        fill_combo(self.group, [("Por conta", "account"), ("Por jogo", "game")])
        self.period.currentIndexChanged.connect(self.refresh)
        self.group.currentIndexChanged.connect(self.refresh)
        self.header_row.addLayout(row(self.period, self.group, button("Exportar CSV", self.export, "primary", icon="file-export-outline")))

        self.cards = {
            "time": StatCard("Tempo de operação", theme.ACCENT),
            "sessions": StatCard("Sessões"),
            "tasks": StatCard("Tarefas concluídas", theme.GREEN),
            "progress": StatCard("Registros de progresso", theme.PURPLE),
        }
        grid = QGridLayout()
        grid.setSpacing(12)
        for i, card in enumerate(self.cards.values()):
            grid.addWidget(card, 0, i)
        self.root.addLayout(grid)

        self.table = DataTable([
            Col("Conta / Jogo", lambda r: r.label, width=260),
            Col("Sessões", lambda r: r.sessions, width=90, right=True),
            Col("Tempo", lambda r: r.seconds, fmt=fmt_duration, width=120, right=True),
            Col("Tarefas concluídas", lambda r: r.tasks_done, width=150, right=True),
            Col("Registros de progresso", lambda r: r.progress_records, right=True),
        ])
        self.chart = ChartCard("Tempo de operação (horas) — 10 maiores", 280)
        productivity = QWidget()
        box = QVBoxLayout(productivity)
        box.setContentsMargins(8, 8, 8, 8)
        box.addWidget(self.table, 3)
        box.addWidget(self.chart, 2)

        self.activity = DataTable([
            Col("Data", lambda r: r.timestamp, width=140), Col("Perfil", lambda r: r.actor, width=90),
            Col("Ação", lambda r: r.action, width=160), Col("Entidade", lambda r: r.entity_type, width=100),
            Col("ID", lambda r: r.entity_id, width=60, right=True), Col("Detalhes", lambda r: r.details),
        ])
        tabs = QTabWidget()
        tabs.addTab(productivity, "Produtividade")
        tabs.addTab(self.activity, "Histórico de atividades (auditoria)")
        self.root.addWidget(tabs, 1)
        self.footer = label("", "muted")
        self.root.addWidget(self.footer)
        self._rows: list = []

    def _range(self) -> tuple[datetime, datetime]:
        """Período em UTC; 'Hoje' e 'N dias' começam à meia-noite local."""
        days = self.period.currentData()
        end = utcnow() + timedelta(minutes=1)
        if days < 0:
            return datetime(2000, 1, 1), end
        local_midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        offset = datetime.now() - utcnow()
        return local_midnight - offset - timedelta(days=max(0, days - 1)), end

    def refresh(self) -> None:
        start, end = self._range()
        self._rows = self.ctx.reports.time_report(start, end, self.group.currentData())
        self.table.set_rows(self._rows)
        self.cards["time"].set(fmt_duration(sum(r.seconds for r in self._rows)))
        self.cards["sessions"].set(sum(r.sessions for r in self._rows))
        self.cards["tasks"].set(sum(r.tasks_done for r in self._rows))
        self.cards["progress"].set(sum(r.progress_records for r in self._rows))
        top = [r for r in self._rows if r.seconds >= 36][:10]
        self.chart.set_bars([r.label for r in top], [round(r.seconds / 3600, 1) for r in top], horizontal=True)
        logs = self.ctx.reports.activity(start, end)
        self.activity.set_rows(logs)
        self.footer.setText(f"{len(self._rows)} linha(s) no relatório · {len(logs)} atividade(s) no período")

    @safe
    def export(self) -> None:
        name = f"relatorio_rfm_{datetime.now():%Y%m%d}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Exportar relatório", name, "CSV (*.csv)")
        if path:
            by = "conta" if self.group.currentData() == "account" else "jogo"
            self.ctx.reports.export_time_report(path, self._rows, by)
            info(self, f"Relatório exportado com {len(self._rows)} linha(s).")
