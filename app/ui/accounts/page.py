from __future__ import annotations

from collections import Counter

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QLineEdit,
    QListWidget, QListWidgetItem, QPlainTextEdit, QTabWidget, QVBoxLayout,
)

from app.core import events as ev
from app.core.bootstrap import AppContext
from app.database.models import Account, AccountStatus, ProgressKind, SessionStatus
from app.ui.icons import game_icon
from app.ui.widgets import (
    Col, DataTable, Page, button, confirm, fill_combo, fmt_duration, info, label, row, run_dialog,
    safe, search_icon, spin, status_col,
)


class AccountDialog(QDialog):
    def __init__(self, ctx: AppContext, account: Account | None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar conta" if account else "Nova conta")
        self.setMinimumWidth(460)
        self.username = QLineEdit(account.username if account else "")
        self.username.setPlaceholderText("3 a 20 caracteres: letras, números e _")
        self.user_id = QLineEdit(str(account.roblox_user_id or "") if account else "")
        self.user_id.setPlaceholderText("opcional — ID público do perfil")
        self.category = QComboBox()
        self.category.setEditable(True)
        self.category.addItems([""] + ctx.accounts.categories())
        self.category.setCurrentText(account.category if account else "")
        self.level = spin(0, 10_000_000)
        self.level.setValue(account.level if account else 0)
        self.status = QComboBox()
        fill_combo(self.status, [(text, key) for key, text in AccountStatus.LABELS.items()])
        if account:
            self.status.setCurrentIndex(self.status.findData(account.status))
        self.tags = QLineEdit(account.tags.replace(",", ", ") if account else "")
        self.tags.setPlaceholderText("separadas por vírgula")
        self.notes = QPlainTextEdit(account.notes if account else "")
        self.notes.setFixedHeight(70)
        self.games = QListWidget()
        self.games.setFixedHeight(150)
        linked = {g.id for g in account.games} if account else set()
        for game in ctx.games.all():
            item = QListWidgetItem(game_icon(game.icon), game.name)
            item.setData(Qt.ItemDataRole.UserRole, game.id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if game.id in linked else Qt.CheckState.Unchecked)
            self.games.addItem(item)

        form = QFormLayout()
        form.addRow("Usuário *", self.username)
        form.addRow("ID público", self.user_id)
        form.addRow("Categoria", self.category)
        form.addRow("Nível registrado", self.level)
        form.addRow("Status", self.status)
        form.addRow("Tags", self.tags)
        form.addRow("Jogos", self.games)
        form.addRow("Observações", self.notes)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        box = QVBoxLayout(self)
        box.addLayout(form)
        box.addWidget(label("O RFM não pede nem guarda senhas, cookies ou tokens.", "muted"))
        box.addWidget(buttons)

    def values(self) -> dict:
        games = [self.games.item(i) for i in range(self.games.count())]
        return {
            "username": self.username.text(), "roblox_user_id": self.user_id.text(),
            "category": self.category.currentText(), "level": self.level.value(),
            "status": self.status.currentData(), "tags": self.tags.text(),
            "notes": self.notes.toPlainText(),
            "game_ids": [g.data(Qt.ItemDataRole.UserRole) for g in games
                         if g.checkState() == Qt.CheckState.Checked],
        }


class HistoryDialog(QDialog):
    def __init__(self, ctx: AppContext, account: Account, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Histórico — {account.username}")
        self.resize(820, 520)
        activity = DataTable([
            Col("Data", lambda r: r.timestamp, width=140), Col("Ação", lambda r: r.action, width=150),
            Col("Detalhes", lambda r: r.details),
        ])
        activity.set_rows(ctx.accounts.history(account.id))
        progress = DataTable([
            Col("Jogo", lambda r: r.game.name if r.game else "Geral", width=170),
            Col("Tipo", lambda r: ProgressKind.LABELS.get(r.kind, r.kind), width=110),
            Col("Indicador", lambda r: r.name, width=200), Col("Valor atual", lambda r: r.value, width=140),
            Col("Atualizado em", lambda r: r.recorded_at),
        ])
        progress.set_rows(ctx.progress.latest(account.id))
        sessions = DataTable([
            Col("Início", lambda r: r.started_at, width=140), Col("Fim", lambda r: r.ended_at, width=140),
            Col("Duração", lambda r: r.duration_s, fmt=fmt_duration, width=100),
            Col("Jogo", lambda r: r.game.name if r.game else None, width=170),
            status_col("Status", SessionStatus.LABELS),
        ])
        sessions.set_rows(ctx.sessions.history(account.id))
        tabs = QTabWidget()
        tabs.addTab(activity, "Atividades")
        tabs.addTab(progress, "Progresso atual")
        tabs.addTab(sessions, "Sessões")
        box = QVBoxLayout(self)
        box.addWidget(tabs)


class AccountsPage(Page):
    title = "Contas"
    subtitle = "Cadastro e organização dos registros de contas."
    events = (ev.ACCOUNTS_CHANGED, ev.GAMES_CHANGED)

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.search = QLineEdit()
        search_icon(self.search)
        self.search.setPlaceholderText("Pesquisar por usuário, tag ou observação…")
        self.search.setClearButtonEnabled(True)
        self.game, self.status, self.category = QComboBox(), QComboBox(), QComboBox()
        for combo in (self.game, self.status, self.category):
            combo.setMinimumWidth(150)
            combo.currentIndexChanged.connect(self.refresh)
        fill_combo(self.status, [(t, k) for k, t in AccountStatus.LABELS.items()], "Todos os status")
        self.group = QCheckBox("Agrupar por categoria")
        self.group.toggled.connect(self.refresh)
        self._debounce = QTimer(self, singleShot=True, interval=250)
        self._debounce.timeout.connect(self.refresh)
        self.search.textChanged.connect(lambda _t: self._debounce.start())
        self.root.addLayout(row(self.search, self.game, self.status, self.category, self.group))

        self.header_row.addLayout(row(
            button("Nova conta", self.add, "primary", icon="plus"), button("Editar", self.edit, icon="pencil-outline"),
            button("Histórico", self.history, icon="history"),
            button("Importar CSV", self.import_csv, icon="file-import-outline"),
            button("Exportar CSV", self.export_csv, icon="file-export-outline"),
            button("Excluir", self.delete, "danger", icon="delete-outline"),
        ))

        self.table = DataTable([
            Col("Usuário", lambda a: a.username, width=150),
            Col("ID público", lambda a: a.roblox_user_id, width=95),
            Col("Categoria", lambda a: a.category or None, width=95),
            Col("Jogos", lambda a: a.game_names or None, width=240),
            Col("Nível", lambda a: a.level, width=60, right=True),
            status_col("Status", AccountStatus.LABELS),
            Col("Tags", lambda a: a.tags.replace(",", ", ") or None, width=100),
            Col("Última atividade", lambda a: a.last_activity, width=125),
            Col("Cadastro", lambda a: a.created_at, width=125),
        ], stretch=3)
        self.table.setColumnWidth(5, 145)
        self.table.row_activated.connect(lambda _a: self.edit())
        self.root.addWidget(self.table, 1)
        self.footer = label("", "muted")
        self.root.addWidget(self.footer)

    def refresh(self) -> None:
        fill_combo(self.game, [(g.name, g.id) for g in self.ctx.games.all()], "Todos os jogos")
        fill_combo(self.category, [(c, c) for c in self.ctx.accounts.categories()], "Todas as categorias")
        accounts = self.ctx.accounts.search(
            self.search.text(), self.game.currentData(), self.status.currentData(),
            self.category.currentData(),
        )
        self.table.set_rows(accounts)
        if self.group.isChecked():
            self.table.sortByColumn(2, Qt.SortOrder.AscendingOrder)
            groups = Counter(a.category or "(sem categoria)" for a in accounts)
            detail = " · ".join(f"{name}: {total}" for name, total in sorted(groups.items()))
        else:
            counts = Counter(a.status for a in accounts)
            detail = " · ".join(f"{AccountStatus.LABELS[k]}: {v}" for k, v in counts.items())
        self.footer.setText(f"{len(accounts)} de {self.ctx.accounts.count()} contas" + (f"   |   {detail}" if detail else ""))

    @safe
    def add(self) -> None:
        dialog = AccountDialog(self.ctx, None, self)
        run_dialog(dialog, lambda: self.ctx.accounts.create(**dialog.values()))

    @safe
    def edit(self) -> None:
        account = self.table.require_selected("uma conta")
        dialog = AccountDialog(self.ctx, account, self)
        run_dialog(dialog, lambda: self.ctx.accounts.update(account.id, **dialog.values()))

    @safe
    def delete(self) -> None:
        account = self.table.require_selected("uma conta")
        if confirm(self, f"Excluir a conta “{account.username}” e todo o seu progresso?\n"
                         "Para apenas ocultá-la, mude o status para “Arquivada”."):
            self.ctx.accounts.delete(account.id)

    @safe
    def history(self) -> None:
        HistoryDialog(self.ctx, self.table.require_selected("uma conta"), self).exec()

    @safe
    def import_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Importar contas", "", "CSV (*.csv)")
        if not path:
            return
        result = self.ctx.accounts.import_csv(path)
        text = f"{result.created} contas criadas, {result.updated} atualizadas."
        if result.errors:
            shown = "\n".join(result.errors[:15])
            more = f"\n… e mais {len(result.errors) - 15}" if len(result.errors) > 15 else ""
            text += f"\n\n{len(result.errors)} linha(s) ignorada(s):\n{shown}{more}"
        info(self, text)

    @safe
    def export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Exportar contas", "contas_rfm.csv", "CSV (*.csv)")
        if path:
            total = self.ctx.accounts.export_csv(path, self.table.rows())
            info(self, f"{total} contas exportadas (as que estão filtradas na tabela).")
