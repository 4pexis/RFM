from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QVBoxLayout,
)

from app.core import events as ev
from app.core.bootstrap import AppContext
from app.database.models import ProgressKind
from app.ui.widgets import (
    Col, DataTable, Page, account_combo, button, search_icon, combo_data, confirm, fill_combo, game_combo,
    label, row, run_dialog, safe,
)


class ProgressDialog(QDialog):
    def __init__(self, ctx: AppContext, account_id: int | None, game_id: int | None, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("Registrar progresso")
        self.setMinimumWidth(440)
        self.account = account_combo(ctx, none_label=None, selected=account_id)
        self.game = game_combo(ctx, "(geral — sem jogo)", game_id)
        self.name = QComboBox()
        self.name.setEditable(True)
        self.kind = QComboBox()
        fill_combo(self.kind, [(t, k) for k, t in ProgressKind.LABELS.items()])
        self.value = QLineEdit()
        self.value.setPlaceholderText("ex.: 1500 · 2,5m · Buddha · Concluído")
        self.notes = QLineEdit()
        self.game.currentIndexChanged.connect(self._load_objectives)
        self.name.currentIndexChanged.connect(self._sync_kind)
        self._load_objectives()
        form = QFormLayout()
        form.addRow("Conta *", self.account)
        form.addRow("Jogo", self.game)
        form.addRow("Objetivo / indicador *", self.name)
        form.addRow("Tipo", self.kind)
        form.addRow("Valor *", self.value)
        form.addRow("Observações", self.notes)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        box = QVBoxLayout(self)
        box.addLayout(form)
        box.addWidget(label("Cada registro é guardado com data — o histórico mostra a evolução.", "muted"))
        box.addWidget(buttons)

    def _load_objectives(self) -> None:
        game = self.ctx.games.get(self.game.currentData()) if self.game.currentData() else None
        self.name.blockSignals(True)
        self.name.clear()
        for obj in self.ctx.games.objectives(game):
            self.name.addItem(obj["name"], obj.get("kind"))
        self.name.blockSignals(False)
        self._sync_kind()

    def _sync_kind(self) -> None:
        index = self.kind.findData(self.name.currentData())
        if index >= 0:
            self.kind.setCurrentIndex(index)

    def values(self) -> dict:
        return {
            "account_id": combo_data(self.account), "game_id": self.game.currentData(),
            "name": self.name.currentText(), "kind": self.kind.currentData(),
            "value": self.value.text(), "notes": self.notes.text(),
        }


class ProgressPage(Page):
    title = "Progresso"
    subtitle = "Níveis, itens, conquistas e estatísticas registrados por conta e jogo."
    events = (ev.PROGRESS_CHANGED, ev.GAMES_CHANGED, ev.ACCOUNTS_CHANGED)

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.header_row.addLayout(row(
            button("Registrar progresso", self.add, "primary", icon="plus"),
            button("Excluir", self.delete, "danger", icon="delete-outline"),
        ))
        self.search = QLineEdit()
        search_icon(self.search)
        self.search.setPlaceholderText("Pesquisar por usuário, indicador ou valor…")
        self.search.setClearButtonEnabled(True)
        self.game, self.kind = QComboBox(), QComboBox()
        fill_combo(self.kind, [(t, k) for k, t in ProgressKind.LABELS.items()], "Todos os tipos")
        for combo in (self.game, self.kind):
            combo.setMinimumWidth(170)
            combo.currentIndexChanged.connect(self.refresh)
        self._debounce = QTimer(self, singleShot=True, interval=250)
        self._debounce.timeout.connect(self.refresh)
        self.search.textChanged.connect(lambda _t: self._debounce.start())
        self.root.addLayout(row(self.search, self.game, self.kind))

        self.table = DataTable([
            Col("Data", lambda r: r.recorded_at, width=140),
            Col("Conta", lambda r: r.account.username, width=170),
            Col("Jogo", lambda r: r.game.name if r.game else "Geral", width=180),
            Col("Tipo", lambda r: ProgressKind.LABELS.get(r.kind, r.kind), width=110),
            Col("Indicador", lambda r: r.name, width=220),
            Col("Valor", lambda r: r.value, width=150),
            Col("Observações", lambda r: r.notes or None),
        ])
        self.root.addWidget(self.table, 1)
        self.footer = label("", "muted")
        self.root.addWidget(self.footer)

    def refresh(self) -> None:
        fill_combo(self.game, [(g.name, g.id) for g in self.ctx.games.all()], "Todos os jogos")
        records = self.ctx.progress.search(self.search.text(), game_id=self.game.currentData(),
                                           kind=self.kind.currentData())
        self.table.set_rows(records)
        text = f"{len(records)} registro(s)"
        if self.game.currentData():
            stats = self.ctx.progress.game_statistics(self.game.currentData())
            best = " · ".join(f"{k}: {v:g}" for k, v in list(stats.get("maiores_valores", {}).items())[:5])
            text += f"   |   {stats.get('contas', 0)} conta(s) com registros" + (f"   |   Maiores valores — {best}" if best else "")
        self.footer.setText(text)

    @safe
    def add(self) -> None:
        current = self.table.selected()
        dialog = ProgressDialog(self.ctx, current.account_id if current else None,
                                current.game_id if current else self.game.currentData(), self)
        run_dialog(dialog, lambda: self.ctx.progress.record(**dialog.values()))

    @safe
    def delete(self) -> None:
        record = self.table.require_selected("um registro")
        if confirm(self, f"Excluir o registro “{record.name}: {record.value}”?"):
            self.ctx.progress.delete(record.id)
