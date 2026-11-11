from __future__ import annotations

from collections import deque

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QListWidget, QListWidgetItem, QProgressBar, QVBoxLayout

from app.services.monitoring import Alert, HardwareSnapshot
from app.ui import theme
from app.ui.icons import icon
from app.ui.widgets import Card, ChartCard, Col, DataTable, Page, StatCard, label, to_local

HISTORY = 60  # amostras no gráfico ao vivo


class Gauge(Card):
    def __init__(self, title: str) -> None:
        super().__init__(title)
        self.value = label("—", "cardValue")
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.hint = label("", "muted")
        self.box.addWidget(self.value)
        self.box.addWidget(self.bar)
        self.box.addWidget(self.hint)

    def set(self, percent: float, hint: str, warn: float) -> None:
        self.value.setText(f"{percent:.0f}%")
        self.bar.setValue(int(percent))
        level = "high" if warn and percent >= warn else "warn" if warn and percent >= warn * 0.85 else ""
        if self.bar.property("level") != level:
            self.bar.setProperty("level", level)
            self.bar.style().unpolish(self.bar)
            self.bar.style().polish(self.bar)
        self.value.setStyleSheet(f"color: {theme.RED if level == 'high' else theme.TEXT};")
        self.hint.setText(hint)


class MonitoringPage(Page):
    title = "Monitoramento"
    subtitle = "Uso de CPU, memória e disco deste computador e dos processos acompanhados."

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.cpu, self.ram, self.disk = Gauge("CPU"), Gauge("Memória RAM"), Gauge("Uso de disco")
        self.free = StatCard("Espaço disponível")
        self.procs = StatCard("Processos acompanhados", theme.CYAN)
        self.sessions = StatCard("Sessões monitoradas", theme.CYAN)
        grid = QGridLayout()
        grid.setSpacing(12)
        for i, card in enumerate((self.cpu, self.ram, self.disk, self.free, self.procs, self.sessions)):
            grid.addWidget(card, 0, i)
        self.root.addLayout(grid)

        self.chart = ChartCard("Uso ao vivo", 260)
        self.table = DataTable([
            Col("PID", lambda p: p.pid, width=80, right=True), Col("Processo", lambda p: p.name, width=200),
            Col("CPU", lambda p: p.cpu_percent, fmt=lambda v: f"{v:.1f}%", width=80, right=True),
            Col("Memória", lambda p: p.memory_mb, fmt=lambda v: f"{v:.0f} MB", right=True),
        ])
        self.alerts = QListWidget()
        self.chart_hint = label("Coletando amostras…", "muted")
        self.chart.box.addWidget(self.chart_hint)
        left = QVBoxLayout()
        left.addWidget(self.chart, 1)
        right = QVBoxLayout()
        right.addWidget(label("Processos acompanhados", "sectionTitle"))
        right.addWidget(self.table, 2)
        right.addWidget(label("Alertas recentes", "sectionTitle"))
        right.addWidget(self.alerts, 1)
        body = QHBoxLayout()
        body.setSpacing(12)
        body.addLayout(left, 3)
        body.addLayout(right, 2)
        self.root.addLayout(body, 1)

        self._cpu: deque[float] = deque(maxlen=HISTORY)
        self._ram: deque[float] = deque(maxlen=HISTORY)
        self._last: HardwareSnapshot | None = None

    # Chamados pela janela principal a cada evento, mesmo com a tela oculta.
    def on_snapshot(self, snap: HardwareSnapshot) -> None:
        self._cpu.append(snap.cpu_percent)
        self._ram.append(snap.memory_percent)
        self._last = snap
        if self.isVisible():
            self.refresh()

    def on_alert(self, alert: Alert) -> None:
        text = f"{to_local(self._last.timestamp):%d/%m %H:%M:%S}  {alert.message}" if self._last else alert.message
        self.alerts.insertItem(0, QListWidgetItem(icon("alert-outline", theme.YELLOW), text))
        while self.alerts.count() > 100:
            self.alerts.takeItem(self.alerts.count() - 1)

    def refresh(self) -> None:
        snap = self._last
        if snap is None:
            return
        cfg = self.ctx.config
        on = cfg.get("monitor.alerts_enabled")
        self.cpu.set(snap.cpu_percent, "do processador", cfg.get("monitor.cpu_alert") if on else 0)
        self.ram.set(snap.memory_percent, f"{snap.memory_used_gb:.1f} de {snap.memory_total_gb:.1f} GB",
                     cfg.get("monitor.ram_alert") if on else 0)
        self.disk.set(snap.disk_percent, f"de {snap.disk_total_gb:.0f} GB",
                      cfg.get("monitor.disk_alert") if on else 0)
        self.free.set(f"{snap.disk_free_gb:.0f} GB", "livres no disco do RFM")
        memory = sum(p.memory_mb for p in snap.processes)
        self.procs.set(len(snap.processes), f"{memory:.0f} MB em uso" if snap.processes else "nenhum cliente aberto")
        self.sessions.set(snap.session_count, "em andamento")
        self.table.set_rows(snap.processes)
        count = len(self._cpu)
        if count >= 2:
            self.chart.set_lines(list(range(count)), {"CPU": list(self._cpu), "RAM": list(self._ram)},
                                 percent=True, hide_x=True)
            self.chart_hint.setText(f"Últimos {(count - 1) * cfg.get('monitor.interval_s')} segundos")
