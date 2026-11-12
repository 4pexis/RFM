from __future__ import annotations

import os
import re
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame, QGridLayout, QGroupBox,
    QInputDialog, QLineEdit, QScrollArea, QVBoxLayout, QWidget,
)

from app.core import events as ev
from app.core.config import APP_NAME, APP_VERSION
from app.core.security import Role
from app.ui.widgets import Page, button, confirm, fill_combo, info, label, row, safe
from app.ui.widgets import spin as _spin
from app.workers.task_worker import PRIORITY_HIGH


class SettingsPage(Page):
    title = "Configurações"
    subtitle = "Monitoramento, alertas, backups e segurança."
    events = (ev.SETTINGS_CHANGED, ev.BACKUP_DONE)

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.header_row.addLayout(row(button("Salvar configurações", self.save, "primary", icon="content-save-outline")))
        # chave -> widget
        self.fields: dict[str, QWidget] = {
            "monitor.interval_s": _spin(1, 60, " s"),
            "monitor.alerts_enabled": QCheckBox("Alertar quando o uso ficar elevado"),
            "monitor.cpu_alert": _spin(0, 100, " %"),
            "monitor.ram_alert": _spin(0, 100, " %"),
            "monitor.disk_alert": _spin(0, 100, " %"),
            "monitor.metric_retention_days": _spin(1, 365, " dias"),
            "sessions.scan_interval_s": _spin(2, 300, " s"),
            "sessions.process_names": QLineEdit(),
            "sessions.idle_cpu_percent": _spin(0, 100, " %", decimals=1),
            "sessions.idle_minutes": _spin(1, 240, " min"),
            "sessions.notify": QCheckBox("Avisar quando uma sessão for encerrada ou ficar ociosa"),
            "backup.enabled": QCheckBox("Fazer backup automático"),
            "backup.interval_h": _spin(1, 720, " h"),
            "backup.keep": _spin(1, 200, " arquivos"),
            "ui.refresh_s": _spin(2, 120, " s"),
        }
        f = self.fields

        monitor = QGroupBox("Monitoramento de hardware")
        form = QFormLayout(monitor)
        form.addRow("Intervalo de leitura", f["monitor.interval_s"])
        form.addRow("", f["monitor.alerts_enabled"])
        form.addRow("Alerta de CPU a partir de", f["monitor.cpu_alert"])
        form.addRow("Alerta de RAM a partir de", f["monitor.ram_alert"])
        form.addRow("Alerta de disco a partir de", f["monitor.disk_alert"])
        form.addRow("Guardar métricas por", f["monitor.metric_retention_days"])
        form.addRow("Atualizar telas a cada", f["ui.refresh_s"])
        form.addRow(label("0 % desativa o alerta do recurso.", "muted"))

        sessions = QGroupBox("Sessões")
        form = QFormLayout(sessions)
        form.addRow("Verificar processos a cada", f["sessions.scan_interval_s"])
        form.addRow("Executáveis acompanhados", f["sessions.process_names"])
        form.addRow("Considerar ociosa abaixo de", f["sessions.idle_cpu_percent"])
        form.addRow("…por pelo menos", f["sessions.idle_minutes"])
        form.addRow("", f["sessions.notify"])
        form.addRow(label("Vários executáveis: separe por vírgula.", "muted"))

        backup = QGroupBox("Backup do banco de dados")
        form = QFormLayout(backup)
        form.addRow("", f["backup.enabled"])
        form.addRow("Intervalo", f["backup.interval_h"])
        form.addRow("Manter os últimos", f["backup.keep"])
        self.backup_info = label("", "muted")
        form.addRow(self.backup_info)
        form.addRow(row(button("Fazer backup agora", self.backup_now, icon="database-export-outline"),
                        button("Restaurar…", self.restore, icon="backup-restore"),
                        button("Abrir pasta", self.open_backups, icon="folder-open-outline"), 1))

        security = QGroupBox("Segurança e permissões")
        form = QFormLayout(security)
        self.role = QComboBox()
        fill_combo(self.role, [(t, k) for k, t in Role.LABELS.items()])
        self.role.activated.connect(self.change_role)
        form.addRow("Perfil em uso", self.role)
        self.pin_info = label("", "muted")
        form.addRow(row(button("Definir/alterar PIN de administrador", self.set_pin, icon="key-outline"), 1))
        form.addRow(self.pin_info)
        note = label("Operador: cria e edita registros. Somente leitura: apenas consulta. "
                     "Com PIN definido, voltar a Administrador exige o PIN.", "muted")
        note.setWordWrap(True)
        form.addRow(note)

        system = QGroupBox("Sistema")
        form = QFormLayout(system)
        url = re.sub(r"://([^:/@]+):[^@]+@", r"://\1:****@", ctx.settings.database_url)
        for title, text in (
            ("Versão", f"{APP_NAME} {APP_VERSION}"), ("Ambiente", ctx.settings.env),
            ("Banco de dados", url), ("Pasta de dados", str(ctx.settings.data_dir)),
            ("Módulos de jogo", f"{len(ctx.plugins.modules)} carregados"),
        ):
            value = label(text)
            value.setWordWrap(True)
            form.addRow(title, value)
        form.addRow(row(button("Abrir pasta de dados", self.open_data),
                        button("Abrir pasta de logs", self.open_logs), 1))

        content = QWidget()
        grid = QGridLayout(content)
        grid.setContentsMargins(0, 0, 8, 0)
        grid.setSpacing(14)
        grid.addWidget(monitor, 0, 0)
        grid.addWidget(sessions, 0, 1)
        grid.addWidget(backup, 1, 0)
        grid.addWidget(security, 1, 1)
        grid.addWidget(system, 2, 0, 1, 2)
        grid.setRowStretch(3, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        self.root.addWidget(scroll, 1)
        self._loaded = False

    def refresh(self) -> None:
        # Os campos só são recarregados quando não há edição pendente do usuário.
        if not self._loaded:
            for key, widget in self.fields.items():
                value = self.ctx.config.get(key)
                if isinstance(widget, QCheckBox):
                    widget.setChecked(bool(value))
                elif isinstance(widget, QLineEdit):
                    widget.setText(str(value))
                else:
                    widget.setValue(value)
            self._loaded = True
        self.role.setCurrentIndex(self.role.findData(self.ctx.access.role))
        self.pin_info.setText("PIN de administrador: " + ("definido" if self.ctx.config.has_pin else "não definido"))
        backups = self.ctx.backups
        if not backups.supported:
            self.backup_info.setText("Backup integrado indisponível para este banco (use pg_dump no PostgreSQL).")
        else:
            files = backups.list_backups()
            last = backups.last_backup_time()
            self.backup_info.setText(
                f"{len(files)} backup(s) · último: {last:%d/%m/%Y %H:%M}" if last else "Nenhum backup ainda."
            )

    @safe
    def save(self) -> None:
        values = {}
        for key, widget in self.fields.items():
            if isinstance(widget, QCheckBox):
                values[key] = widget.isChecked()
            elif isinstance(widget, QLineEdit):
                values[key] = widget.text().strip() or "RobloxPlayerBeta.exe"
            else:
                values[key] = widget.value()
        self.ctx.config.set_many(values)
        self._loaded = False
        self.refresh()
        info(self, "Configurações salvas.")

    @safe
    def change_role(self) -> None:
        role = self.role.currentData()
        if role == self.ctx.access.role:
            return
        pin = ""
        if self.ctx.access.role != Role.ADMIN and self.ctx.config.has_pin:
            pin, ok = QInputDialog.getText(self, "PIN de administrador", "Informe o PIN:",
                                           QLineEdit.EchoMode.Password)
            if not ok:
                self.refresh()
                return
        try:
            self.ctx.config.change_role(role, pin)
        finally:
            self.refresh()

    @safe
    def set_pin(self) -> None:
        pin, ok = QInputDialog.getText(self, "PIN de administrador",
                                       "Novo PIN (mínimo 4 caracteres; vazio remove o PIN):",
                                       QLineEdit.EchoMode.Password)
        if ok:
            self.ctx.config.set_pin(pin)
            info(self, "PIN atualizado." if pin else "PIN removido.")

    @safe
    def backup_now(self) -> None:
        future = self.ctx.queue.submit("Backup manual", lambda: self.ctx.backups.create("manual"), PRIORITY_HIGH)
        path = future.result(timeout=120)
        self.refresh()
        info(self, f"Backup criado:\n{path}")

    @safe
    def restore(self) -> None:
        self.ctx.access.require("admin")
        path, _ = QFileDialog.getOpenFileName(self, "Restaurar backup", str(self.ctx.settings.backup_dir),
                                              "Backups do RFM (*.db)")
        if not path:
            return
        if not confirm(self, f"Substituir TODOS os dados atuais pelo backup “{Path(path).name}”?\n"
                             "Uma cópia do estado atual será salva antes."):
            return
        self.ctx.scheduler.stop()  # nenhuma tarefa pode usar o banco durante a troca
        try:
            safety = self.ctx.backups.restore(Path(path))
        finally:
            self.ctx.scheduler.start()
        self.ctx.config.reload()
        self.ctx.games.sync_modules()
        self._loaded = False
        for event in (ev.ACCOUNTS_CHANGED, ev.GAMES_CHANGED, ev.TASKS_CHANGED, ev.SESSIONS_CHANGED,
                      ev.PROGRESS_CHANGED, ev.SETTINGS_CHANGED):
            self.ctx.events.publish(event)
        info(self, f"Backup restaurado.\nCópia de segurança do estado anterior:\n{safety.name}")

    def _open(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.fspath(path)))

    def open_backups(self) -> None:
        self._open(self.ctx.settings.backup_dir)

    def open_data(self) -> None:
        self._open(self.ctx.settings.data_dir)

    def open_logs(self) -> None:
        self._open(self.ctx.settings.log_dir)
