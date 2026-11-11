from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QInputDialog, QLineEdit,
    QPlainTextEdit, QVBoxLayout,
)

from app.core import events as ev
from app.core.bootstrap import AppContext
from app.database.models import Task, TaskPriority, TaskStatus
from app.ui import theme
from app.ui.widgets import (
    Col, DataTable, Page, account_combo, button, combo_data, confirm, fill_combo, game_combo,
    label, row, run_dialog, safe, search_icon, status_col,
)

_PRIORITY_COLORS = {TaskPriority.URGENT: theme.RED, TaskPriority.HIGH: theme.YELLOW,
                    TaskPriority.LOW: theme.MUTED}


class TaskDialog(QDialog):
    def __init__(self, ctx: AppContext, task: Task | None, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle(f"Tarefa #{task.id}" if task else "Nova tarefa")
        self.setMinimumWidth(460)
        self.account = account_combo(ctx, selected=task.account_id if task else None)
        self.game = game_combo(ctx, selected=task.game_id if task else None)
        self.type = QComboBox()
        self.type.setEditable(True)
        self.game.currentIndexChanged.connect(self._load_types)
        self._load_types()
        if task:
            self.type.setCurrentText(task.type)
        self.priority = QComboBox()
        fill_combo(self.priority, [(t, k) for k, t in TaskPriority.LABELS.items()])
        self.priority.setCurrentIndex(self.priority.findData(task.priority if task else TaskPriority.NORMAL))
        self.description = QPlainTextEdit(task.description if task else "")
        self.description.setFixedHeight(90)
        self.result = QLineEdit(task.result if task else "")
        form = QFormLayout()
        form.addRow("Conta", self.account)
        form.addRow("Jogo", self.game)
        form.addRow("Tipo", self.type)
        form.addRow("Prioridade", self.priority)
        form.addRow("Descrição *", self.description)
        if task:
            form.addRow("Resultado", self.result)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        box = QVBoxLayout(self)
        box.addLayout(form)
        box.addWidget(buttons)

    def _load_types(self) -> None:
        current = self.type.currentText()
        game = self.ctx.games.get(self.game.currentData()) if self.game.currentData() else None
        self.type.clear()
        self.type.addItems(self.ctx.games.module_for(game).task_types())
        if current:
            self.type.setCurrentText(current)

    def values(self) -> dict:
        return {
            "account_id": combo_data(self.account), "game_id": self.game.currentData(),
            "type": self.type.currentText(), "priority": self.priority.currentData(),
            "description": self.description.toPlainText(), "result": self.result.text(),
        }


class TasksPage(Page):
    title = "Tarefas"
    subtitle = "Fila de trabalho por prioridade: o que precisa ser feito em cada conta e jogo."
    events = (ev.TASKS_CHANGED, ev.GAMES_CHANGED)

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.header_row.addLayout(row(
            button("Nova tarefa", self.add, "primary", icon="plus"),
            button("Editar", self.edit, icon="pencil-outline"),
            button("Excluir", self.delete, "danger", icon="delete-outline"),
        ))
        self.search = QLineEdit()
        search_icon(self.search)
        self.search.setPlaceholderText("Pesquisar por descrição, tipo, resultado ou usuário…")
        self.search.setClearButtonEnabled(True)
        self.status, self.game, self.priority = QComboBox(), QComboBox(), QComboBox()
        fill_combo(self.status, [(t, k) for k, t in TaskStatus.LABELS.items()], "Todos os status")
        fill_combo(self.priority, [(t, k) for k, t in TaskPriority.LABELS.items()], "Todas as prioridades")
        self.open_only = QCheckBox("Somente em aberto")
        self.queue_order = QCheckBox("Ordem da fila")
        self.queue_order.setToolTip("Mostra apenas as pendentes, da mais prioritária e antiga para a mais nova.")
        for combo in (self.status, self.game, self.priority):
            combo.setMinimumWidth(150)
            combo.currentIndexChanged.connect(self.refresh)
        self.open_only.toggled.connect(self.refresh)
        self.queue_order.toggled.connect(self.refresh)
        self._debounce = QTimer(self, singleShot=True, interval=250)
        self._debounce.timeout.connect(self.refresh)
        self.search.textChanged.connect(lambda _t: self._debounce.start())
        self.root.addLayout(row(self.search, self.status, self.game, self.priority,
                                self.open_only, self.queue_order))

        self.table = DataTable([
            Col("#", lambda t: t.id, width=50, right=True),
            Col("Prioridade", lambda t: t.priority, fmt=lambda v: TaskPriority.LABELS.get(v, str(v)),
                color=lambda t: _PRIORITY_COLORS.get(t.priority), width=90),
            status_col("Status", TaskStatus.LABELS),
            Col("Tipo", lambda t: t.type, width=110),
            Col("Descrição", lambda t: t.description.replace("\n", " "), width=280),
            Col("Conta", lambda t: t.account.username if t.account else None, width=140),
            Col("Jogo", lambda t: t.game.name if t.game else None, width=150),
            Col("Criada", lambda t: t.created_at, width=135),
            Col("Início", lambda t: t.started_at, width=135),
            Col("Conclusão", lambda t: t.finished_at, width=135),
            Col("Resultado", lambda t: t.result or None, width=200),
        ], stretch=4)
        self.table.setColumnWidth(2, 110)
        self.table.row_activated.connect(lambda _t: self.edit())
        self.root.addWidget(self.table, 1)

        S = TaskStatus
        self.root.addLayout(row(
            label("Mudar status:", "muted"),
            button("Iniciar", lambda: self.set_status(S.RUNNING), icon="play"),
            button("Pausar", lambda: self.set_status(S.PAUSED), icon="pause"),
            button("Concluir", lambda: self.set_status(S.DONE, ask_result=True), icon="check"),
            button("Cancelar", lambda: self.set_status(S.CANCELED), icon="close"),
            button("Erro", lambda: self.set_status(S.ERROR, ask_result=True), icon="alert-outline"),
            button("Reabrir", lambda: self.set_status(S.PENDING), icon="restore"), 1,
        ))
        self.footer = label("", "muted")
        self.root.addWidget(self.footer)

    def refresh(self) -> None:
        fill_combo(self.game, [(g.name, g.id) for g in self.ctx.games.all()], "Todos os jogos")
        if self.queue_order.isChecked():
            tasks = self.ctx.tasks.queue()
            self.table.horizontalHeader().setSortIndicator(-1, self.table.horizontalHeader().sortIndicatorOrder())
        else:
            tasks = self.ctx.tasks.search(
                self.search.text(), self.status.currentData(), self.game.currentData(),
                priority=self.priority.currentData(), open_only=self.open_only.isChecked(),
            )
        self.table.set_rows(tasks)
        counts = self.ctx.tasks.counts()
        summary = " · ".join(f"{TaskStatus.LABELS[k]}: {counts[k]}" for k in TaskStatus.LABELS if counts.get(k))
        self.footer.setText(f"{len(tasks)} tarefa(s) exibida(s)" + (f"   |   {summary}" if summary else ""))

    @safe
    def add(self) -> None:
        dialog = TaskDialog(self.ctx, None, self)

        def create() -> None:
            values = dialog.values()
            values.pop("result")
            self.ctx.tasks.create(**values)

        run_dialog(dialog, create)

    @safe
    def edit(self) -> None:
        task = self.table.require_selected("uma tarefa")
        dialog = TaskDialog(self.ctx, task, self)
        run_dialog(dialog, lambda: self.ctx.tasks.update(task.id, **dialog.values()))

    def set_status(self, status: str, ask_result: bool = False) -> None:
        self._pending = (status, ask_result)
        self._apply_status()

    @safe
    def _apply_status(self) -> None:
        status, ask_result = self._pending
        task = self.table.require_selected("uma tarefa")
        result = None
        if ask_result:
            result, ok = QInputDialog.getText(self, TaskStatus.LABELS[status], "Resultado / observação:",
                                              text=task.result)
            if not ok:
                return
        self.ctx.tasks.set_status(task.id, status, result)

    @safe
    def delete(self) -> None:
        task = self.table.require_selected("uma tarefa")
        if confirm(self, f"Excluir a tarefa #{task.id}?"):
            self.ctx.tasks.delete(task.id)
