from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QListWidget, QPlainTextEdit,
    QSplitter, QVBoxLayout, QWidget,
)

from app.core import events as ev
from app.core.bootstrap import AppContext
from app.database.models import Game, IntegrationStatus, ProgressKind
from app.ui import theme
from app.ui.icons import DEFAULT_GAME_ICON, GAME_ICONS, game_icon
from app.ui.widgets import (
    Card, Col, DataTable, Page, button, confirm, fill_combo, info, label, row, run_dialog, safe,
)


class GameDialog(QDialog):
    def __init__(self, ctx: AppContext, game: Game | None, parent=None) -> None:
        super().__init__(parent)
        self.game = game
        self.setWindowTitle("Editar jogo" if game else "Novo jogo")
        self.setMinimumWidth(480)
        self.name = QLineEdit(game.name if game else "")
        self.experience = QLineEdit(game.experience_id if game else "")
        self.experience.setPlaceholderText("Place ID — o número em roblox.com/games/<número>")
        self.category = QLineEdit(game.category if game else "")
        self.icon = QComboBox()
        for name, text in GAME_ICONS:
            self.icon.addItem(game_icon(name), text, name)
        self.icon.setCurrentIndex(max(0, self.icon.findData(game.icon if game else DEFAULT_GAME_ICON)))
        self.description = QPlainTextEdit(game.description if game else "")
        self.description.setFixedHeight(60)
        self.integration = QComboBox()
        has_module = bool(game and ctx.plugins.has(game.module_name))
        options = (IntegrationStatus.MODULE, IntegrationStatus.DISABLED) if has_module else (
            IntegrationStatus.MANUAL, IntegrationStatus.DISABLED)
        fill_combo(self.integration, [(IntegrationStatus.LABELS[o], o) for o in options])
        if game:
            self.integration.setCurrentIndex(max(0, self.integration.findData(game.integration_status)))
        self.objectives = QPlainTextEdit("\n".join(o["name"] for o in ctx.games.objectives(game)))
        self.objectives.setPlaceholderText("Um objetivo por linha (ex.: Nível, Itens raros…)")
        self.objectives.setFixedHeight(150)

        form = QFormLayout()
        form.addRow("Nome *", self.name)
        form.addRow("ID da experiência", self.experience)
        form.addRow("Categoria", self.category)
        form.addRow("Ícone", self.icon)
        form.addRow("Descrição", self.description)
        form.addRow("Integração", self.integration)
        form.addRow("Objetivos", self.objectives)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        box = QVBoxLayout(self)
        box.addLayout(form)
        box.addWidget(buttons)
        self._known = {o["name"]: o for o in ctx.games.objectives(game)}

    def values(self) -> dict:
        names = [line.strip() for line in self.objectives.toPlainText().splitlines() if line.strip()]
        return {
            "name": self.name.text(), "experience_id": self.experience.text(),
            "category": self.category.text(), "icon": self.icon.currentData(),
            "description": self.description.toPlainText(),
            "integration_status": self.integration.currentData(),
            # objetivos já existentes mantêm tipo e limites definidos pelo módulo
            "objectives": [self._known.get(name, {"name": name}) for name in dict.fromkeys(names)],
        }


class GamesPage(Page):
    title = "Jogos"
    subtitle = "Catálogo de experiências. Cada jogo tem um módulo de acompanhamento independente."
    events = (ev.GAMES_CHANGED, ev.ACCOUNTS_CHANGED)

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.header_row.addLayout(row(
            button("Novo jogo", self.add, "primary", icon="plus"), button("Editar", self.edit, icon="pencil-outline"),
            button("Abrir no Roblox", self.launch, icon="play",
                   tip="Abre a experiência pelo link oficial roblox://"),
            button("Página do jogo", self.open_page, icon="open-in-new"),
            button("Excluir", self.delete, "danger", icon="delete-outline"),
        ))
        self._counts: dict[int, int] = {}
        self.table = DataTable([
            Col("", lambda g: "", icon=lambda g: game_icon(g.icon), width=40),
            Col("Nome", lambda g: g.name, width=180),
            Col("ID da experiência", lambda g: g.experience_id or None, width=125),
            Col("Categoria", lambda g: g.category or None, width=140),
            Col("Integração", lambda g: IntegrationStatus.LABELS.get(g.integration_status),
                color=lambda g: {IntegrationStatus.MODULE: theme.GREEN,
                                 IntegrationStatus.DISABLED: theme.MUTED}.get(g.integration_status),
                width=150),
            Col("Módulo", lambda g: g.module_name or None, width=125),
            Col("Contas", lambda g: self._counts.get(g.id, 0), width=60, right=True),
            Col("Objetivos", lambda g: len(self.ctx.games.objectives(g)), right=True),
        ])
        self.table.row_activated.connect(lambda _g: self.edit())
        self.table.selectionModel().selectionChanged.connect(lambda *_: self._show_details())

        details = Card()
        self.detail_title = label("Selecione um jogo", "sectionTitle")
        self.detail_text = label("", "muted")
        self.detail_text.setWordWrap(True)
        self.objectives = QListWidget()
        details.box.addWidget(self.detail_title)
        details.box.addWidget(self.detail_text)
        details.box.addWidget(label("Objetivos disponíveis", "cardTitle"))
        details.box.addWidget(self.objectives, 1)

        splitter = QSplitter()
        splitter.addWidget(self.table)
        holder = QWidget()
        holder_box = QVBoxLayout(holder)
        holder_box.setContentsMargins(12, 0, 0, 0)
        holder_box.addWidget(details)
        splitter.addWidget(holder)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([920, 250])
        self.root.addWidget(splitter, 1)
        errors = ctx.plugins.load_errors
        if errors:
            warning = label("Módulos com erro ao carregar: " + ", ".join(errors), "muted")
            warning.setStyleSheet(f"color: {theme.YELLOW};")
            self.root.addWidget(warning)

    def refresh(self) -> None:
        self._counts = self.ctx.games.account_counts()
        self.table.set_rows(self.ctx.games.all())
        self._show_details()

    def _show_details(self) -> None:
        game = self.table.selected()
        self.objectives.clear()
        if game is None:
            self.detail_title.setText("Selecione um jogo")
            self.detail_text.setText("")
            return
        self.detail_title.setText(game.name)
        self.detail_text.setText(game.description or "Sem descrição.")
        for obj in self.ctx.games.objectives(game):
            kind = ProgressKind.LABELS.get(obj.get("kind", ""), "Objetivo")
            limit = f" (máx. {obj['max_value']:g})" if obj.get("max_value") else ""
            self.objectives.addItem(f"{obj['name']}  —  {kind}{limit}")

    @safe
    def add(self) -> None:
        dialog = GameDialog(self.ctx, None, self)
        run_dialog(dialog, lambda: self.ctx.games.create(**dialog.values()))

    @safe
    def edit(self) -> None:
        game = self.table.require_selected("um jogo")
        dialog = GameDialog(self.ctx, game, self)
        run_dialog(dialog, lambda: self.ctx.games.update(game.id, **dialog.values()))

    @safe
    def delete(self) -> None:
        game = self.table.require_selected("um jogo")
        if confirm(self, f"Excluir o jogo “{game.name}” do catálogo?"):
            self.ctx.games.delete(game.id)

    @safe
    def launch(self) -> None:
        game = self.table.require_selected("um jogo")
        self.ctx.sessions.launch(game.experience_id)
        info(self, f"Pedido de abertura enviado ao Roblox para “{game.name}”.\n"
                   "A sessão aparecerá na tela Sessões quando o cliente iniciar.")

    @safe
    def open_page(self) -> None:
        self.ctx.sessions.launch(self.table.require_selected("um jogo").experience_id, via_browser=True)
