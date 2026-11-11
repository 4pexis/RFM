"""Componentes de interface compartilhados pelas telas."""
from __future__ import annotations

import functools
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable, Sequence

from PySide6.QtCharts import (
    QBarCategoryAxis, QBarSeries, QBarSet, QChart, QChartView, QHorizontalBarSeries,
    QLineSeries, QPieSeries, QValueAxis,
)
from PySide6.QtCore import QAbstractTableModel, QMargins, QModelIndex, QSize, QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDoubleSpinBox, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QMessageBox, QPushButton, QSpinBox, QTableView, QVBoxLayout, QWidget,
)

from app.core.bootstrap import AppContext
from app.core.config import APP_NAME
from app.core.security import PermissionDenied, ValidationError

from . import icons, theme

log = logging.getLogger(__name__)

# ------------------------------------------------------------------- formatação


def to_local(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc).astimezone()


def fmt_dt(value: datetime | None) -> str:
    return to_local(value).strftime("%d/%m/%Y %H:%M") if value else "—"


def fmt_duration(seconds: float | None) -> str:
    seconds = int(seconds or 0)
    hours, minutes = seconds // 3600, (seconds % 3600) // 60
    if hours:
        return f"{hours}h {minutes:02d}min"
    return f"{minutes}min" if minutes else f"{seconds}s"


def _display(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, datetime):
        return fmt_dt(value)
    if isinstance(value, float):
        return f"{value:.1f}"
    return str(value)


# -------------------------------------------------------------- erros e diálogos


def safe(method: Callable) -> Callable:
    """Decorador para slots: mostra erros de validação/permissão ao usuário em
    vez de derrubar a aplicação."""

    @functools.wraps(method)
    def wrapper(self, *_args, **_kwargs):
        try:
            return method(self)
        except (ValidationError, PermissionDenied) as exc:
            QMessageBox.warning(self, APP_NAME, str(exc))
        except Exception as exc:
            log.exception("Erro inesperado em %s", method.__qualname__)
            QMessageBox.critical(self, APP_NAME, f"Erro inesperado:\n{exc}")
        return None

    return wrapper


def run_dialog(dialog, action: Callable[[], Any]) -> bool:
    """Abre o diálogo e executa ``action`` ao confirmar. Em erro de validação a
    mensagem é exibida e o diálogo continua aberto para correção."""
    while dialog.exec():
        try:
            action()
            return True
        except (ValidationError, PermissionDenied) as exc:
            QMessageBox.warning(dialog, APP_NAME, str(exc))
    return False


def confirm(parent: QWidget, text: str) -> bool:
    return QMessageBox.question(parent, APP_NAME, text) == QMessageBox.StandardButton.Yes


def info(parent: QWidget, text: str) -> None:
    QMessageBox.information(parent, APP_NAME, text)


# ------------------------------------------------------------------- utilidades


def button(text: str, slot: Callable | None = None, kind: str = "", tip: str = "",
           icon: str = "") -> QPushButton:
    btn = QPushButton(text)
    if icon:
        btn.setIcon(icons.icon(icon, "white" if kind == "primary" else theme.TEXT))
        btn.setIconSize(QSize(16, 16))
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    if kind:
        btn.setObjectName(kind)
    if tip:
        btn.setToolTip(tip)
    if slot is not None:
        btn.clicked.connect(slot)
    return btn


def search_icon(edit) -> None:
    """Lupa à esquerda do campo de pesquisa."""
    edit.addAction(icons.icon("magnify", theme.MUTED), edit.ActionPosition.LeadingPosition)


def fill_combo(combo: QComboBox, items: Sequence[tuple[str, Any]], all_label: str | None = None) -> None:
    """Preenche o combo preservando a seleção atual. ``all_label`` cria a opção
    'todos' (dado None)."""
    current = combo.currentData()
    combo.blockSignals(True)
    combo.clear()
    if all_label is not None:
        combo.addItem(all_label, None)
    for label, data in items:
        combo.addItem(label, data)
    index = combo.findData(current)
    combo.setCurrentIndex(index if index >= 0 else 0)
    combo.blockSignals(False)


def spin(low: float, high: float, suffix: str = "", decimals: int = 0) -> QSpinBox | QDoubleSpinBox:
    box: QSpinBox | QDoubleSpinBox
    if decimals:
        box = QDoubleSpinBox()
        box.setDecimals(decimals)
        box.setSingleStep(10 ** -decimals)
    else:
        box = QSpinBox()
    box.setRange(low, high)
    box.setSuffix(suffix)
    box.lineEdit().setTextMargins(8, 0, 0, 0)
    return box


def account_combo(ctx: AppContext, none_label: str | None = "(sem conta)", selected: int | None = None) -> QComboBox:
    """Combo pesquisável de contas (digite parte do nome para filtrar)."""
    combo = QComboBox()
    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    fill_combo(combo, [(a.username, a.id) for a in ctx.accounts.all()], none_label)
    completer = combo.completer()
    completer.setFilterMode(Qt.MatchFlag.MatchContains)
    completer.setCompletionMode(completer.CompletionMode.PopupCompletion)
    combo.setCurrentIndex(max(0, combo.findData(selected)))
    return combo


def game_combo(ctx: AppContext, none_label: str | None = "(sem jogo)", selected: int | None = None) -> QComboBox:
    combo = QComboBox()
    fill_combo(combo, [(g.name, g.id) for g in ctx.games.all()], none_label)
    for index in range(combo.count()):
        game = ctx.games.get(combo.itemData(index)) if combo.itemData(index) else None
        if game is not None:
            combo.setItemIcon(index, icons.game_icon(game.icon))
    combo.setCurrentIndex(max(0, combo.findData(selected)))
    return combo


def combo_data(combo: QComboBox) -> Any:
    """Dado do item selecionado; em combos editáveis exige que o texto digitado
    corresponda a um item existente."""
    if combo.isEditable():
        index = combo.findText(combo.currentText().strip(), Qt.MatchFlag.MatchFixedString)
        if index < 0:
            raise ValidationError(f"“{combo.currentText()}” não corresponde a nenhum registro.")
        return combo.itemData(index)
    return combo.currentData()


def row(*widgets: QWidget | int | None, spacing: int = 8) -> QHBoxLayout:
    """Linha horizontal; um inteiro vira espaço flexível (stretch)."""
    layout = QHBoxLayout()
    layout.setSpacing(spacing)
    for widget in widgets:
        if isinstance(widget, int):
            layout.addStretch(widget)
        elif widget is not None:
            layout.addWidget(widget)
    return layout


def label(text: str, name: str = "") -> QLabel:
    lbl = QLabel(text)
    if name:
        lbl.setObjectName(name)
    return lbl


class Card(QFrame):
    def __init__(self, title: str = "") -> None:
        super().__init__()
        self.setObjectName("card")
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(16, 14, 16, 14)
        self.box.setSpacing(6)
        if title:
            self.box.addWidget(label(title, "cardTitle"))


class StatCard(Card):
    def __init__(self, title: str, color: str = theme.TEXT) -> None:
        super().__init__(title)
        self.value = label("—", "cardValue")
        self.value.setStyleSheet(f"color: {color};")
        self.hint = label("", "muted")
        self.box.addWidget(self.value)
        self.box.addWidget(self.hint)
        self.setMinimumHeight(104)

    def set(self, value: Any, hint: str = "") -> None:
        self.value.setText(str(value))
        self.hint.setText(hint)


class Page(QWidget):
    """Base das telas. ``events`` lista os eventos que pedem atualização e
    ``auto_refresh`` liga a atualização periódica enquanto a tela está visível."""

    title = ""
    subtitle = ""
    events: tuple[str, ...] = ()
    auto_refresh = False

    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self.ctx = ctx
        self.setObjectName("page")
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(24, 20, 24, 16)
        self.root.setSpacing(12)
        header = QVBoxLayout()
        header.setSpacing(2)
        header.addWidget(label(self.title, "pageTitle"))
        if self.subtitle:
            header.addWidget(label(self.subtitle, "muted"))
        self.header_row = QHBoxLayout()
        self.header_row.addLayout(header)
        self.header_row.addStretch(1)
        self.root.addLayout(self.header_row)

    def refresh(self) -> None:  # pragma: no cover - sobrescrito
        pass


# ------------------------------------------------------------------------ tabela


@dataclass
class Col:
    header: str
    getter: Callable[[Any], Any]
    fmt: Callable[[Any], str] | None = None  # formata o valor para exibição
    color: Callable[[Any], str | None] | None = None  # cor do texto a partir da linha
    width: int | None = None
    right: bool = False
    icon: Callable[[Any], Any] | None = None  # QIcon a partir da linha


class _Model(QAbstractTableModel):
    def __init__(self, columns: list[Col]) -> None:
        super().__init__()
        self.columns = columns
        self.rows: list[Any] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.columns)

    def headerData(self, section: int, orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.columns[section].header
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        col, item = self.columns[index.column()], self.rows[index.row()]
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            value = col.getter(item)
            return col.fmt(value) if col.fmt and value is not None else _display(value)
        if role == Qt.ItemDataRole.UserRole:  # valor bruto, usado na ordenação
            value = col.getter(item)
            if isinstance(value, (datetime, date)):
                return value.isoformat()
            if isinstance(value, bool):
                return int(value)
            if isinstance(value, str):
                return value.lower()
            return value if isinstance(value, (int, float)) else ""
        if role == Qt.ItemDataRole.DecorationRole and col.icon:
            return col.icon(item)
        if role == Qt.ItemDataRole.ForegroundRole and col.color:
            color = col.color(item)
            return QColor(color) if color else None
        if role == Qt.ItemDataRole.TextAlignmentRole and col.right:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None

    def set_rows(self, rows: Sequence[Any]) -> None:
        self.beginResetModel()
        self.rows = list(rows)
        self.endResetModel()


class DataTable(QTableView):
    """Tabela ordenável baseada em modelo (leve mesmo com milhares de linhas)."""

    row_activated = Signal(object)

    def __init__(self, columns: list[Col], stretch: int | None = None) -> None:
        super().__init__()
        self._model = _Model(columns)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setSortRole(Qt.ItemDataRole.UserRole)
        self.setModel(self._proxy)
        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setIconSize(QSize(20, 20))
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(32)
        header = self.horizontalHeader()
        header.setHighlightSections(False)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)  # mantém a ordem do banco
        for i, col in enumerate(columns):
            if col.width:
                self.setColumnWidth(i, col.width)
        if stretch is None:
            header.setStretchLastSection(True)
        else:
            header.setSectionResizeMode(stretch, QHeaderView.ResizeMode.Stretch)
        self.doubleClicked.connect(lambda _i: self.row_activated.emit(self.selected()))

    def set_rows(self, rows: Sequence[Any]) -> None:
        selected = getattr(self.selected(), "id", None)
        self._model.set_rows(rows)
        if selected is not None:
            for i, item in enumerate(self._model.rows):
                if getattr(item, "id", None) == selected:
                    self.selectRow(self._proxy.mapFromSource(self._model.index(i, 0)).row())
                    break

    def selected(self) -> Any | None:
        indexes = self.selectionModel().selectedRows() if self.selectionModel() else []
        if not indexes:
            return None
        return self._model.rows[self._proxy.mapToSource(indexes[0]).row()]

    def require_selected(self, what: str = "um registro") -> Any:
        item = self.selected()
        if item is None:
            raise ValidationError(f"Selecione {what} na tabela.")
        return item

    def rows(self) -> list[Any]:
        return list(self._model.rows)


def status_col(header: str, labels: dict[str, str], attr: str = "status") -> Col:
    return Col(header, lambda r: labels.get(getattr(r, attr), getattr(r, attr)),
               color=lambda r: theme.STATUS_COLORS.get(getattr(r, attr)))


# ---------------------------------------------------------------------- gráficos


class ChartCard(Card):
    def __init__(self, title: str, min_height: int = 250) -> None:
        super().__init__()
        self.box.setContentsMargins(12, 12, 12, 6)
        self.box.addWidget(label(title, "sectionTitle"))
        self.chart = QChart()
        self.chart.setBackgroundVisible(False)
        self.chart.setMargins(QMargins(0, 0, 0, 0))
        self.chart.legend().setVisible(False)
        self.chart.legend().setLabelColor(QColor(theme.MUTED))
        self.view = QChartView(self.chart)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setStyleSheet("background: transparent; border: none;")
        self.view.setMinimumHeight(min_height - 50)
        self.empty = label("Sem dados para exibir ainda.", "muted")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.box.addWidget(self.view, 1)
        self.box.addWidget(self.empty, 1)
        self.setMinimumHeight(min_height)

    def _reset(self, has_data: bool) -> None:
        self.chart.removeAllSeries()
        for axis in self.chart.axes():
            self.chart.removeAxis(axis)
        self.view.setVisible(has_data)
        self.empty.setVisible(not has_data)

    def _style_axis(self, axis, grid: bool) -> None:
        axis.setLabelsColor(QColor(theme.MUTED))
        font = QFont()
        font.setPointSize(8)
        axis.setLabelsFont(font)
        axis.setLinePenColor(QColor(theme.BORDER))
        axis.setGridLineVisible(grid)
        axis.setGridLineColor(QColor(theme.BORDER))

    def _value_axis(self, top: float, percent: bool = False) -> QValueAxis:
        axis = QValueAxis()
        if percent:
            axis.setRange(0, 100)
            axis.setTickCount(5)
        else:
            top = max(4, top)
            step = max(1, -(-int(top) // 4))
            axis.setRange(0, step * 4)
            axis.setTickCount(5)
        axis.setLabelFormat("%d%%" if percent else "%d")
        self._style_axis(axis, True)
        return axis

    def _category_axis(self, labels: Sequence[str]) -> QBarCategoryAxis:
        axis = QBarCategoryAxis()
        axis.append(list(labels))
        axis.setTruncateLabels(False)
        self._style_axis(axis, False)
        return axis

    def set_bars(self, labels: Sequence[str], values: Sequence[float], horizontal: bool = False,
                 color: str = theme.ACCENT) -> None:
        self._reset(bool(labels) and any(values))
        if not labels or not any(values):
            return
        if horizontal:  # o eixo de categorias cresce de baixo para cima
            labels, values = list(reversed(labels)), list(reversed(values))
        bar_set = QBarSet("")
        bar_set.append([float(v) for v in values])
        bar_set.setColor(QColor(color))
        bar_set.setBorderColor(QColor(color))
        series = QHorizontalBarSeries() if horizontal else QBarSeries()
        series.append(bar_set)
        series.setBarWidth(0.6)
        self.chart.addSeries(series)
        categories, numbers = self._category_axis(labels), self._value_axis(max(values))
        cat_side = Qt.AlignmentFlag.AlignLeft if horizontal else Qt.AlignmentFlag.AlignBottom
        num_side = Qt.AlignmentFlag.AlignBottom if horizontal else Qt.AlignmentFlag.AlignLeft
        self.chart.addAxis(categories, cat_side)
        self.chart.addAxis(numbers, num_side)
        series.attachAxis(categories)
        series.attachAxis(numbers)
        self.chart.legend().setVisible(False)

    def set_lines(self, labels: Sequence[str], series_data: dict[str, Sequence[float]],
                  percent: bool = False, hide_x: bool = False) -> None:
        has = bool(labels) and any(any(v) for v in series_data.values())
        self._reset(has)
        if not has:
            return
        if hide_x:  # série temporal contínua: eixo numérico sem rótulos
            categories = QValueAxis()
            categories.setRange(0, max(1, len(labels) - 1))
            categories.setLabelsVisible(False)
            self._style_axis(categories, False)
        else:
            categories = self._category_axis(labels)
        numbers = self._value_axis(max(max(v) for v in series_data.values()), percent)
        self.chart.addAxis(categories, Qt.AlignmentFlag.AlignBottom)
        self.chart.addAxis(numbers, Qt.AlignmentFlag.AlignLeft)
        for i, (name, values) in enumerate(series_data.items()):
            line = QLineSeries()
            line.setName(name)
            for x, y in enumerate(values):
                line.append(x, float(y))
            line.setPen(QPen(QColor(theme.PALETTE[i % len(theme.PALETTE)]), 2))
            line.setPointsVisible(len(values) <= 31)
            self.chart.addSeries(line)
            line.attachAxis(categories)
            line.attachAxis(numbers)
        self.chart.legend().setVisible(len(series_data) > 1)
        self.chart.legend().setAlignment(Qt.AlignmentFlag.AlignTop)

    def set_pie(self, items: Sequence[tuple[str, float]], colors: Sequence[str] | None = None) -> None:
        items = [(name, value) for name, value in items if value]
        self._reset(bool(items))
        if not items:
            return
        series = QPieSeries()
        series.setHoleSize(0.55)
        total = sum(value for _, value in items)
        for i, (name, value) in enumerate(items):
            piece = series.append(f"{name} · {value:g} ({value / total:.0%})", value)
            color = (colors[i] if colors else None) or theme.PALETTE[i % len(theme.PALETTE)]
            piece.setColor(QColor(color))
            piece.setBorderColor(QColor(theme.CARD))
        self.chart.addSeries(series)
        self.chart.legend().setVisible(True)
        self.chart.legend().setAlignment(Qt.AlignmentFlag.AlignRight)
