"""Recipe Browser — modeless dialog for browsing and loading built-in / user recipes.

Opens alongside the main window.  Signals emitted:
    recipeLoadRequested(slot: int, name: str, values: PresetUIValues)
        → main window loads values into panel (no write)
    recipeWriteRequested(slot: int, name: str, values: PresetUIValues)
        → main window loads values into panel AND writes to camera

Part-3 additions
----------------
* Recently Used pinned section — shown at the top of the list when no search
  query / film-sim filter is active and the view is not "My Recipes".
* Export Card… button — renders a 900×540 PNG recipe card via recipe_card.py.
"""

from __future__ import annotations

import re
from typing import Optional

from PyQt6.QtCore import Qt, QRect, QSize, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStyledItemDelegate,
    QStyle,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)

import recipes.user_store as user_store
from profile.enums import (
    DynRangeLabels,
    FilmSimLabels,
    GrainEffectLabels,
    SIM_COLORS,
    WBModeLabels,
)
from profile.preset_translate import PresetUIValues
from recipes.loader import Recipe, SENSOR_LABELS, load_catalog

from .styles import PALETTE

# ---------------------------------------------------------------------------
# Background catalog loader
# ---------------------------------------------------------------------------

class _SensorLoaderThread(QThread):
    """Calls load_catalog() off the main thread; emits (folder, recipes) when done."""
    loaded = pyqtSignal(str, list)

    def __init__(self, sensor_folder: str, parent=None) -> None:
        super().__init__(parent)
        self._sensor = sensor_folder

    def run(self) -> None:
        self.loaded.emit(self._sensor, load_catalog(self._sensor))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_OWS = {0: "Off", 1: "Weak", 2: "Strong"}

# Sentinel — not a real folder, handled specially
_MY_RECIPES_KEY = "my-recipes"

# All film sims in display order for the filter dropdown
_FILM_SIM_FILTER_ITEMS: list[tuple[str, Optional[int]]] = [
    ("All Film Sims", None),
] + [(label, value) for value, label in FilmSimLabels.items()]

# Maximum number of "Recently Used" items shown in the pinned section
_MAX_PINNED_RECENT = 8

# Dim colour for section-header items (non-selectable list rows)
_SECTION_HDR_COLOR = QColor(PALETTE['sectionHdr'])
_SECTION_HDR_BG    = QColor(PALETTE['sectionHdrBg'])


class RecipeListDelegate(QStyledItemDelegate):
    """Paints recipe rows as compact image cards with a film-sim chip."""

    ROW_H = 76
    THUMB = 54

    def sizeHint(self, option, index) -> QSize:
        if index.data(Qt.ItemDataRole.UserRole + 10):
            return QSize(0, 24)
        if index.data(Qt.ItemDataRole.UserRole + 11):
            return QSize(0, 10)
        return QSize(0, self.ROW_H)

    def paint(self, painter: QPainter, option, index) -> None:
        if index.data(Qt.ItemDataRole.UserRole + 10):
            painter.save()
            painter.fillRect(option.rect, QColor(PALETTE['sectionHdrBg']))
            painter.setPen(QColor(PALETTE['sectionHdr']))
            font = QFont(option.font)
            font.setPixelSize(10)
            font.setWeight(QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(
                option.rect.adjusted(10, 0, -10, 0),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                index.data(Qt.ItemDataRole.DisplayRole) or '',
            )
            painter.restore()
            return

        if index.data(Qt.ItemDataRole.UserRole + 11):
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        r = option.rect.adjusted(0, 3, -2, -3)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        bg = QColor(PALETTE['rowSel'] if selected else PALETTE['rowHover'] if hovered else PALETTE['panel'])
        border = QColor(PALETTE['accent'] if selected else PALETTE['border'])
        accent = QColor(index.data(Qt.ItemDataRole.UserRole + 2) or PALETTE['simDefault'])

        painter.setPen(QPen(border, 1))
        painter.setBrush(bg)
        painter.drawRoundedRect(r, 8, 8)

        stripe = QRect(r.left(), r.top() + 8, 3, r.height() - 16)
        painter.fillRect(stripe, accent)

        t = self.THUMB
        thumb_rect = QRect(r.left() + 12, r.top() + (r.height() - t) // 2, t, t)
        painter.setPen(QPen(QColor(PALETTE['borderSoft']), 1))
        painter.setBrush(QColor(PALETTE['bgDeep']))
        painter.drawRoundedRect(thumb_rect, 7, 7)
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        if isinstance(icon, QIcon) and not icon.isNull():
            icon.paint(painter, thumb_rect.adjusted(2, 2, -2, -2))

        title = index.data(Qt.ItemDataRole.UserRole) or ''
        sim = index.data(Qt.ItemDataRole.UserRole + 1) or ''

        title_font = QFont(option.font)
        title_font.setWeight(QFont.Weight.Bold)
        title_font.setPointSize(10)
        painter.setFont(title_font)
        title_fm = QFontMetrics(title_font)
        text_left = thumb_rect.right() + 12
        text_w = max(20, r.right() - text_left - 12)
        painter.setPen(QColor(PALETTE['text']))
        painter.drawText(
            QRect(text_left, r.top() + 13, text_w, 22),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            title_fm.elidedText(title, Qt.TextElideMode.ElideRight, text_w),
        )

        chip_font = QFont(option.font)
        chip_font.setPointSize(8)
        chip_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(chip_font)
        chip_fm = QFontMetrics(chip_font)
        chip_text = chip_fm.elidedText(sim, Qt.TextElideMode.ElideRight, text_w)
        chip_w = min(text_w, chip_fm.horizontalAdvance(chip_text) + 18)
        chip = QRect(text_left, r.top() + 42, chip_w, 20)
        chip_bg = QColor(PALETTE['panelAlt'])
        painter.setPen(QPen(accent, 1))
        painter.setBrush(chip_bg)
        painter.drawRoundedRect(chip, 10, 10)
        painter.setPen(accent)
        painter.drawText(chip.adjusted(9, 0, -9, 0), Qt.AlignmentFlag.AlignVCenter, chip_text)

        painter.restore()


def _ows(val: int) -> str:
    return _OWS.get(val, "—")


def _short_title(title: str) -> str:
    """Strip the '— Fujifilm X100VI Film Simulation Recipe' suffix."""
    return re.sub(r"\s*[—\-–]+\s*Fujifilm.*", "", title).strip() or title


# ---------------------------------------------------------------------------
# Main dialog
# ---------------------------------------------------------------------------

class RecipeBrowserDialog(QDialog):
    """Modeless recipe browser dialog."""

    # slot (1-7), display name, PresetUIValues
    recipeLoadRequested  = pyqtSignal(int, str, object)
    recipeWriteRequested = pyqtSignal(int, str, object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Recipe Browser")
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint
        )
        self.resize(960, 640)
        self.setModal(False)

        self._recipes: list[Recipe] = []          # full catalog for current sensor
        self._visible: list[Recipe] = []          # after search + film-sim filter
        self._recent:  list[Recipe] = []          # recently-used entries (Part 3)

        # Maps each QListWidget row index → Recipe (or None for header/separator rows)
        self._item_map: list[Optional[Recipe]] = []

        self._current_pixmap: Optional[QPixmap] = None  # for resize rescaling
        self._hero_recipe:    Optional[Recipe]  = None  # painted gradient hero
        self._last_image_size = QSize()
        self._is_user_view = False  # True when "My Recipes" is active
        self._loader: Optional[_SensorLoaderThread] = None  # background catalog loader

        # Track last rendered filter state to skip redundant QListWidget rebuilds.
        self._last_vis_slugs: Optional[list] = None
        self._last_rec_slugs: Optional[list] = None

        # Debounce timer for the search box — keeps typing smooth on large catalogs.
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(150)
        self._search_timer.timeout.connect(self._apply_filter)

        self._prerender_swatches()
        self._build_ui()
        self._wire_events()
        self._load_sensor("x-trans-v")

    # ------------------------------------------------------------------ build

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # ── Top bar ──────────────────────────────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(8)

        lbl_sensor = QLabel("Sensor:")
        self.sensorCombo = QComboBox()
        self.sensorCombo.setFixedWidth(130)
        for label in SENSOR_LABELS:
            self.sensorCombo.addItem(label, userData=SENSOR_LABELS[label])
        # "My Recipes" is a special local source — always last
        self.sensorCombo.addItem("My Recipes", userData=_MY_RECIPES_KEY)

        # Film simulation filter
        lbl_sim = QLabel("Film Sim:")
        self.filmSimFilter = QComboBox()
        self.filmSimFilter.setFixedWidth(160)
        for label, value in _FILM_SIM_FILTER_ITEMS:
            self.filmSimFilter.addItem(label, userData=value)

        self.searchEdit = QLineEdit()
        self.searchEdit.setPlaceholderText("Search recipes…")
        self.searchEdit.setClearButtonEnabled(True)

        self.countLabel = QLabel()
        self.countLabel.setProperty("role", "dim")

        # "+ New Recipe" button — only meaningful for My Recipes view
        self.newRecipeBtn = QPushButton("+ New Recipe")
        self.newRecipeBtn.setVisible(False)

        top.addWidget(lbl_sensor)
        top.addWidget(self.sensorCombo)
        top.addSpacing(4)
        top.addWidget(lbl_sim)
        top.addWidget(self.filmSimFilter)
        top.addSpacing(8)
        top.addWidget(self.searchEdit, 1)
        top.addWidget(self.countLabel)
        top.addSpacing(4)
        top.addWidget(self.newRecipeBtn)
        root.addLayout(top)

        # ── Splitter: list | detail ───────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Left — recipe list
        self.recipeList = QListWidget()
        self.recipeList.setObjectName("RecipeList")
        self.recipeList.setMinimumWidth(200)
        self.recipeList.setMaximumWidth(360)
        self.recipeList.setIconSize(QSize(54, 54))
        self.recipeList.setItemDelegate(RecipeListDelegate(self.recipeList))
        self.recipeList.setMouseTracking(True)
        self.recipeList.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        splitter.addWidget(self.recipeList)

        # Right — detail panel
        detail = QWidget()
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(16, 0, 0, 0)
        detail_layout.setSpacing(12)

        # Sample image
        self.imageLabel = QLabel()
        self.imageLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.imageLabel.setMinimumHeight(240)
        self.imageLabel.setMaximumHeight(340)
        self.imageLabel.setMinimumWidth(0)
        self.imageLabel.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        self.imageLabel.setObjectName("RecipeImage")
        detail_layout.addWidget(self.imageLabel)

        self.simBadge = QLabel()
        self.simBadge.setProperty("role", "simBadge")
        self.simBadge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.simBadge.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        detail_layout.addWidget(self.simBadge)

        # Recipe title
        self.titleLabel = QLabel()
        self.titleLabel.setWordWrap(True)
        self.titleLabel.setObjectName("RecipeTitle")
        detail_layout.addWidget(self.titleLabel)

        # Source link (dim)
        self.sourceLabel = QLabel()
        self.sourceLabel.setProperty("role", "dim")
        self.sourceLabel.setWordWrap(True)
        self.sourceLabel.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        detail_layout.addWidget(self.sourceLabel)

        # Params grid inside a scroll area
        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        params_host = QWidget()
        self._params_grid = QGridLayout(params_host)
        self._params_grid.setHorizontalSpacing(14)
        self._params_grid.setVerticalSpacing(6)
        self._params_grid.setColumnStretch(0, 0)
        self._params_grid.setColumnStretch(1, 1)
        scroll.setWidget(params_host)
        detail_layout.addWidget(scroll, 1)

        # ── Action bar ───────────────────────────────────────────────────────
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setProperty("role", "divider")
        detail_layout.addWidget(divider)

        action_bar = QHBoxLayout()
        action_bar.setSpacing(8)

        # Delete button — only visible for user recipes
        self.deleteBtn = QPushButton("Delete")
        self.deleteBtn.setVisible(False)
        action_bar.addWidget(self.deleteBtn)

        # Export Card button — always present, enabled when a recipe is selected
        self.exportCardBtn = QPushButton("Export Card…")
        self.exportCardBtn.setEnabled(False)
        action_bar.addWidget(self.exportCardBtn)

        action_bar.addStretch(1)
        action_bar.addWidget(QLabel("Slot:"))

        self.slotCombo = QComboBox()
        self.slotCombo.setFixedWidth(60)
        for i in range(1, 8):
            self.slotCombo.addItem(f"C{i}", userData=i)
        action_bar.addWidget(self.slotCombo)

        self.loadBtn = QPushButton("Load into Slot")
        self.loadBtn.setEnabled(False)
        action_bar.addWidget(self.loadBtn)

        self.writeBtn = QPushButton("Write to Camera")
        self.writeBtn.setProperty("role", "primary")
        self.writeBtn.setEnabled(False)
        action_bar.addWidget(self.writeBtn)

        detail_layout.addLayout(action_bar)

        splitter.addWidget(detail)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

    # ------------------------------------------------------------------ wire

    def _wire_events(self) -> None:
        self.sensorCombo.currentIndexChanged.connect(self._on_sensor_changed)
        self.filmSimFilter.currentIndexChanged.connect(self._apply_filter)
        # Debounced — restarting the timer on every keystroke collapses bursts
        # into a single _apply_filter call 150 ms after the user pauses.
        self.searchEdit.textChanged.connect(self._search_timer.start)
        self.recipeList.currentRowChanged.connect(self._on_row_changed)
        self.loadBtn.clicked.connect(self._on_load_clicked)
        self.writeBtn.clicked.connect(self._on_write_clicked)
        self.newRecipeBtn.clicked.connect(self._on_new_recipe_clicked)
        self.deleteBtn.clicked.connect(self._on_delete_clicked)
        self.exportCardBtn.clicked.connect(self._on_export_card_clicked)

    # ------------------------------------------------------------------ data

    def _load_sensor(self, sensor_folder: str) -> None:
        self._is_user_view = (sensor_folder == _MY_RECIPES_KEY)
        self.newRecipeBtn.setVisible(self._is_user_view)

        if self._is_user_view:
            self._recipes = user_store.list_recipes()
            # No recently-used pinning inside the My Recipes view
            self._apply_filter()
            return

        self._recent = user_store.load_recent()[:_MAX_PINNED_RECENT]

        # Disconnect stale loader to prevent it from overwriting the new sensor.
        if self._loader is not None:
            try:
                self._loader.loaded.disconnect()
            except RuntimeError:
                pass

        self._loader = _SensorLoaderThread(sensor_folder, self)
        self._loader.loaded.connect(self._on_catalog_loaded)
        self._loader.start()

    def _on_catalog_loaded(self, sensor_folder: str, recipes: list) -> None:
        """Called from _SensorLoaderThread when load_catalog() finishes."""
        if self.sensorCombo.currentData() == sensor_folder:
            self._recipes = recipes
            self._last_vis_slugs = None  # force rebuild after sensor switch
            self._last_rec_slugs = None
            self._apply_filter()

    def _apply_filter(self) -> None:
        query      = self.searchEdit.text().strip().lower()
        sim_filter: Optional[int] = self.filmSimFilter.currentData()

        filtered = self._recipes
        if sim_filter is not None:
            filtered = [r for r in filtered if r.ui_values.filmSimulation == sim_filter]
        if query:
            filtered = [
                r for r in filtered
                if query in r.title.lower() or query in r.slug
            ]

        self._visible = filtered

        # Show recently-used pinned section only when no active filter/search
        show_recent = (
            not query
            and sim_filter is None
            and not self._is_user_view
            and bool(self._recent)
        )

        # Skip the expensive QListWidget rebuild when the visible set hasn't changed.
        new_vis_slugs = [r.slug for r in filtered]
        new_rec_slugs = [r.slug for r in self._recent] if show_recent else []
        if new_vis_slugs == self._last_vis_slugs and new_rec_slugs == self._last_rec_slugs:
            n = len(filtered)
            self.countLabel.setText(f"{n} recipe{'s' if n != 1 else ''}")
            return
        self._last_vis_slugs = new_vis_slugs
        self._last_rec_slugs = new_rec_slugs

        # ── Rebuild QListWidget + item_map ───────────────────────────────────
        self._item_map = []
        self.recipeList.blockSignals(True)
        self.recipeList.clear()

        if show_recent:
            # Section header (non-selectable)
            self._item_map.append(None)
            hdr = QListWidgetItem("  Recently Used")
            hdr.setFlags(Qt.ItemFlag.NoItemFlags)
            hdr.setForeground(QBrush(_SECTION_HDR_COLOR))
            hdr.setBackground(QBrush(_SECTION_HDR_BG))
            hdr.setData(Qt.ItemDataRole.UserRole + 10, True)
            hdr_font = QFont()
            hdr_font.setPixelSize(10)
            hdr.setFont(hdr_font)
            hdr.setSizeHint(QSize(0, 22))
            self.recipeList.addItem(hdr)

            for r in self._recent:
                self._item_map.append(r)
                item = QListWidgetItem()
                item.setIcon(self._make_thumb(r))
                self._decorate_recipe_item(item, r)
                item.setSizeHint(QSize(0, RecipeListDelegate.ROW_H))
                item.setToolTip(r.source)
                self.recipeList.addItem(item)

            # Thin separator
            self._item_map.append(None)
            sep = QListWidgetItem()
            sep.setFlags(Qt.ItemFlag.NoItemFlags)
            sep.setData(Qt.ItemDataRole.UserRole + 11, True)
            sep.setSizeHint(QSize(0, 8))
            self.recipeList.addItem(sep)

        for r in filtered:
            self._item_map.append(r)
            item = QListWidgetItem()
            item.setIcon(self._make_thumb(r))
            self._decorate_recipe_item(item, r)
            item.setSizeHint(QSize(0, RecipeListDelegate.ROW_H))
            item.setToolTip(r.source)
            self.recipeList.addItem(item)

        self.recipeList.blockSignals(False)

        n = len(self._visible)
        self.countLabel.setText(f"{n} recipe{'s' if n != 1 else ''}")

        # Select the first real (non-header) item
        first_idx = next(
            (i for i, r in enumerate(self._item_map) if r is not None), -1
        )
        if first_idx >= 0:
            self.recipeList.setCurrentRow(first_idx)
            self._show_detail(self._item_map[first_idx])   # type: ignore[arg-type]
        else:
            self._clear_detail()

    # --------------------------------------------------------- thumbnails

    @staticmethod
    def _decorate_recipe_item(item: QListWidgetItem, recipe: Recipe) -> None:
        sim_name = FilmSimLabels.get(recipe.ui_values.filmSimulation, '')
        sim_color = SIM_COLORS.get(recipe.ui_values.filmSimulation, PALETTE['simDefault'])
        item.setText(_short_title(recipe.title))
        item.setData(Qt.ItemDataRole.UserRole, _short_title(recipe.title))
        item.setData(Qt.ItemDataRole.UserRole + 1, sim_name)
        item.setData(Qt.ItemDataRole.UserRole + 2, sim_color)

    _THUMB = 54   # thumbnail edge length in pixels

    # Icon caches shared across all instances — QPixmap is cheap to share and
    # the underlying images never change at runtime.
    _thumb_cache: dict[str, QIcon] = {}     # keyed by str(image_path)
    _swatch_cache: dict[int, QIcon] = {}    # keyed by film-sim enum value
    _fallback_swatch: Optional[QIcon] = None

    # Full-res pixmap cache for the detail view (avoids re-decoding on recipe re-visit).
    # Capped to avoid holding too many large bitmaps in memory.
    _detail_pixmap_cache: dict[str, QPixmap] = {}  # str(image_path) -> QPixmap
    _DETAIL_CACHE_MAX = 14

    # Gradient hero cache: one rendered QPixmap per (sim_val, w, h).
    # Invalidated automatically when size changes; keeps the last render per sim.
    _hero_cache: dict[int, tuple] = {}  # sim_val -> (w, h, QPixmap)

    def _prerender_swatches(self) -> None:
        """Pre-render one fallback swatch per SIM_COLORS entry once per process."""
        if self._swatch_cache:
            return
        T = self._THUMB
        for sim, accent_hex in SIM_COLORS.items():
            self._swatch_cache[sim] = self._build_swatch(T, accent_hex)
        type(self)._fallback_swatch = self._build_swatch(T, PALETTE['swatchFallback'])

    @staticmethod
    def _build_swatch(size: int, accent_hex: str) -> QIcon:
        pix = QPixmap(size, size)
        pix.fill(QColor(PALETTE['panelRaised']))
        painter = QPainter(pix)
        painter.fillRect(0, size - 4, size, 4, QColor(accent_hex))
        painter.end()
        return QIcon(pix)

    def _make_thumb(self, recipe: Recipe) -> QIcon:
        """Return a 48×48 QIcon for *recipe*.

        If the recipe has a photo, it is centre-cropped to a square.
        Otherwise a pre-rendered film-sim accent swatch is used so that all
        list items stay the same height regardless of whether an image is
        available. Both cases are cached — the first paint of a recipe pays
        for the decode, every subsequent _apply_filter is a dict lookup.
        """
        T = self._THUMB

        if recipe.image_path is not None:
            key = str(recipe.image_path)
            cached = self._thumb_cache.get(key)
            if cached is not None:
                return cached
            try:
                src = QPixmap(key)
                if not src.isNull():
                    scaled = src.scaled(
                        T, T,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    sx = (scaled.width()  - T) // 2
                    sy = (scaled.height() - T) // 2
                    icon = QIcon(scaled.copy(sx, sy, T, T))
                    self._thumb_cache[key] = icon
                    return icon
            except Exception:
                pass

        return self._swatch_cache.get(
            recipe.ui_values.filmSimulation,
            self._fallback_swatch or self._build_swatch(T, PALETTE['swatchFallback']),
        )

    # --------------------------------------------------------- event handlers

    def _on_sensor_changed(self) -> None:
        folder = self.sensorCombo.currentData()
        if folder:
            self._load_sensor(folder)

    def _on_row_changed(self, row: int) -> None:
        if 0 <= row < len(self._item_map):
            recipe = self._item_map[row]
            if recipe is not None:
                self._show_detail(recipe)
                self.loadBtn.setEnabled(True)
                self.writeBtn.setEnabled(True)
                return
        self._clear_detail()

    def _get_selected_recipe(self) -> Optional[Recipe]:
        """Return the Recipe for the currently selected list row, or None."""
        row = self.recipeList.currentRow()
        if 0 <= row < len(self._item_map):
            return self._item_map[row]
        return None

    def _on_load_clicked(self) -> None:
        recipe = self._get_selected_recipe()
        if recipe is None:
            return
        slot = self.slotCombo.currentData()
        name = _short_title(recipe.title)
        user_store.record_used(recipe.slug, name, recipe.ui_values)
        self.recipeLoadRequested.emit(slot, name, recipe.ui_values)

    def _on_write_clicked(self) -> None:
        recipe = self._get_selected_recipe()
        if recipe is None:
            return
        slot = self.slotCombo.currentData()
        name = _short_title(recipe.title)
        user_store.record_used(recipe.slug, name, recipe.ui_values)
        self.recipeWriteRequested.emit(slot, name, recipe.ui_values)

    def _on_new_recipe_clicked(self) -> None:
        from .recipe_creator import RecipeCreatorDialog
        dlg = RecipeCreatorDialog(parent=self)
        dlg.recipeSaved.connect(self._on_recipe_saved)
        dlg.exec()

    def _on_recipe_saved(self, slug: str, name: str, values) -> None:
        """Called after a recipe is saved from RecipeCreatorDialog."""
        idx = self.sensorCombo.findData(_MY_RECIPES_KEY)
        if idx >= 0:
            self.sensorCombo.blockSignals(True)
            self.sensorCombo.setCurrentIndex(idx)
            self.sensorCombo.blockSignals(False)
        self._load_sensor(_MY_RECIPES_KEY)
        for i, r in enumerate(self._item_map):
            if r is not None and r.slug == slug:
                self.recipeList.setCurrentRow(i)
                break

    def _on_delete_clicked(self) -> None:
        recipe = self._get_selected_recipe()
        if recipe is None:
            return
        name = _short_title(recipe.title)
        answer = QMessageBox.question(
            self,
            "Delete recipe",
            f'Permanently delete "{name}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        user_store.delete_recipe(recipe.slug)
        self._load_sensor(_MY_RECIPES_KEY)

    def _on_export_card_clicked(self) -> None:
        recipe = self._get_selected_recipe()
        if recipe is None:
            return

        from .recipe_card import generate_recipe_card

        name      = _short_title(recipe.title)
        safe_name = re.sub(r"[^\w\s\-]", "", name).strip().replace(" ", "_") or "recipe"
        path, _   = QFileDialog.getSaveFileName(
            self,
            "Export Recipe Card",
            f"{safe_name}_card.png",
            "PNG Image (*.png)",
        )
        if not path:
            return

        pix = generate_recipe_card(recipe)
        if not pix.save(path, "PNG"):
            QMessageBox.warning(self, "Export failed", f"Could not save to:\n{path}")

    # --------------------------------------------------------- detail display

    def _clear_detail(self) -> None:
        self._current_pixmap = None
        self._hero_recipe    = None
        self._last_image_size = QSize()
        self.imageLabel.clear()
        self.imageLabel.setText("No recipe selected")
        self.simBadge.clear()
        self.simBadge.setVisible(False)
        self.titleLabel.clear()
        self.sourceLabel.clear()
        self._clear_params_grid()
        self.loadBtn.setEnabled(False)
        self.writeBtn.setEnabled(False)
        self.exportCardBtn.setEnabled(False)
        self.deleteBtn.setVisible(False)

    def _show_detail(self, recipe: Recipe) -> None:
        self._last_image_size = QSize()

        # Image / hero — use cached full-res pixmap to avoid re-decoding on revisit.
        if recipe.image_path and recipe.image_path.exists():
            key = str(recipe.image_path)
            pix = self._detail_pixmap_cache.get(key)
            if pix is None:
                pix = QPixmap(key)
                if not pix.isNull():
                    if len(self._detail_pixmap_cache) >= self._DETAIL_CACHE_MAX:
                        self._detail_pixmap_cache.pop(next(iter(self._detail_pixmap_cache)))
                    self._detail_pixmap_cache[key] = pix
            if pix and not pix.isNull():
                self._current_pixmap = pix
                self._hero_recipe    = None
                self._refresh_image()
            else:
                self._current_pixmap = None
                self._hero_recipe    = recipe
                self._refresh_image()
        else:
            self._current_pixmap = None
            self._hero_recipe    = recipe
            self._refresh_image()

        self.titleLabel.setText(_short_title(recipe.title))
        self.sourceLabel.setText(recipe.source)
        sim_name = FilmSimLabels.get(recipe.ui_values.filmSimulation, "Recipe")
        sim_color = SIM_COLORS.get(recipe.ui_values.filmSimulation, PALETTE['simDefault'])
        self.simBadge.setText(sim_name.upper())
        self.simBadge.setVisible(True)
        self.simBadge.setStyleSheet(
            f'color: {sim_color}; background-color: {PALETTE["panelAlt"]};'
            f' border: 1px solid {sim_color}; border-radius: 11px;'
            f' padding: 3px 10px; font-size: 8pt; font-weight: 800;'
            f' letter-spacing: 0.8px;'
        )

        # Delete button — only for user recipes (not for recently-used entries
        # even if they originated from My Recipes, as sensor=="recent" here)
        self.deleteBtn.setVisible(recipe.sensor == _MY_RECIPES_KEY)

        # Params — monospaced value pills in column 1
        self._clear_params_grid()
        v = recipe.ui_values
        rows = [
            ("Film Simulation",  FilmSimLabels.get(v.filmSimulation, "—")),
            ("Dynamic Range",    DynRangeLabels.get(v.dynamicRange, "—")),
            ("Grain Effect",     GrainEffectLabels.get(v.grainEffect, "—")),
            ("Color Chrome",     _ows(v.colorChrome)),
            ("CC FX Blue",       _ows(v.colorChromeFxBlue)),
            ("White Balance",    WBModeLabels.get(v.whiteBalance, "—")),
            ("WB Shift R / B",   f"{v.wbShiftR:+d} / {v.wbShiftB:+d}"),
            ("Highlight",        f"{v.highlightTone:+.1f}"),
            ("Shadow",           f"{v.shadowTone:+.1f}"),
            ("Color",            f"{v.color:+.1f}"),
            ("Sharpness",        f"{v.sharpness:+.1f}"),
            ("Noise Reduction",  f"{v.noiseReduction:+d}"),
            ("Clarity",          f"{v.clarity:+.1f}"),
        ]
        for i, (label, value) in enumerate(rows):
            lbl = QLabel(label)
            lbl.setProperty("role", "paramLabel")
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            pill = QLabel(str(value))
            pill.setProperty("role", "valuePill")
            pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pill.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)

            self._params_grid.addWidget(lbl, i, 0)
            self._params_grid.addWidget(
                pill, i, 1, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )

        self.loadBtn.setEnabled(True)
        self.writeBtn.setEnabled(True)
        self.exportCardBtn.setEnabled(True)

    def _clear_params_grid(self) -> None:
        while self._params_grid.count():
            item = self._params_grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _refresh_image(self) -> None:
        size = self.imageLabel.size()
        if size == self._last_image_size:
            return
        self._last_image_size = QSize(size)

        if self._hero_recipe is not None:
            # Repaint the gradient hero at the imageLabel's current size so
            # the type stays crisp and the gradient fills edge-to-edge.
            self.imageLabel.setPixmap(self._make_gradient_hero(self._hero_recipe))
            return
        if self._current_pixmap is None:
            return
        w = max(1, self.imageLabel.width())
        h = max(1, self.imageLabel.height())
        scaled = self._current_pixmap.scaled(
            w, h,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        sx = max(0, (scaled.width() - w) // 2)
        sy = max(0, (scaled.height() - h) // 2)
        self.imageLabel.setPixmap(scaled.copy(sx, sy, w, h))

    def _make_gradient_hero(self, recipe: Recipe) -> QPixmap:
        """Render a film-sim accent gradient with the simulation name baked
        in as the hero — used when no photo is available for *recipe*."""
        w = max(1, self.imageLabel.width())
        h = max(1, self.imageLabel.height())

        sim_val = recipe.ui_values.filmSimulation
        cached = self._hero_cache.get(sim_val)
        if cached is not None and cached[0] == w and cached[1] == h:
            return cached[2]
        sim_color = QColor(SIM_COLORS.get(sim_val, PALETTE['simDefault']))
        sim_name  = FilmSimLabels.get(sim_val, "Recipe")

        pix = QPixmap(w, h)
        pix.fill(QColor(PALETTE['bgDeep']))
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        grad = QLinearGradient(0, 0, w, h)
        # Keep the saturated sim colour at the top-left, fade into the deep
        # surface colour at the bottom-right.
        top = QColor(sim_color)
        top.setAlpha(220)
        grad.setColorAt(0.0, top)
        grad.setColorAt(1.0, QColor(PALETTE['bgDeep']))
        p.fillRect(0, 0, w, h, QBrush(grad))

        # Subtle vignette at the bottom for legibility
        veil = QLinearGradient(0, h * 0.4, 0, h)
        veil.setColorAt(0.0, QColor(0, 0, 0, 0))
        veil.setColorAt(1.0, QColor(0, 0, 0, 110))
        p.fillRect(0, 0, w, h, QBrush(veil))

        # Big film-sim name
        title_font = QFont("Inter", max(20, h // 8))
        title_font.setWeight(QFont.Weight.Bold)
        title_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
        p.setFont(title_font)
        p.setPen(QColor(255, 255, 255, 235))
        p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, sim_name)

        p.end()
        type(self)._hero_cache[sim_val] = (w, h, pix)
        return pix

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._refresh_image()

    # ------------------------------------------------------------------ public

    def refresh_user_recipes(self) -> None:
        """Reload user recipes if the My Recipes view is currently active."""
        if self._is_user_view:
            self._load_sensor(_MY_RECIPES_KEY)
