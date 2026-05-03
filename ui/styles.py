"""Dark theme stylesheet for FujiRecipe — Visual Overhaul v4.

Single source of truth: every hex code in the app routes through PALETTE.
Other UI modules (main_window, recipe_browser, preset_panel) import PALETTE
rather than hard-coding hex values inline.
"""

from typing import Final


# ---------------------------------------------------------------------------
# Token palette
# ---------------------------------------------------------------------------

PALETTE: Final[dict[str, str]] = {
    # Brand
    'accent':         '#E8840A',
    'accentHover':    '#ff9620',
    'onAccent':       '#000000',

    # Surfaces — deeper contrast ramp for layered glass feel
    'bg':             '#0b0b10',   # absolute floor — window/rail backgrounds
    'bgDeep':         '#070709',   # deepest shade — image placeholder bg
    'panel':          '#191926',   # card surface — group boxes, panels
    'panelAlt':       '#1f2030',   # control background — inputs, combos
    'panelRaised':    '#232337',   # elevated elements — toasts, menus

    # Borders / hairlines
    'border':         '#26263e',
    'borderSoft':     '#151520',

    # Text
    'text':           '#e2e2f0',
    'textBright':     '#c4c4d8',
    'textDim':        '#6a6a82',
    'textMute':       '#5a5a72',

    # Status
    'danger':         '#d94343',
    'dangerHover':    '#c0392b',
    'ok':             '#3ab873',
    'white':          '#ffffff',

    # Slot rail states
    'slotSel':        '#1e1e30',
    'slotHover':      '#161626',
    'slotSep':        '#1a1a28',

    # Recipe list row states
    'rowSel':         '#212138',
    'rowHover':       '#1c1c2e',

    # Section headers
    'sectionHdr':     '#888894',
    'sectionHdrBg':   '#16162a',

    # Swatches / fallbacks
    'swatchFallback': '#444450',
    'simDefault':     '#666670',

    # Value pills (recipe-browser detail)
    'pillBg':         '#1e1e30',
    'pillBorder':     '#2a2a42',
    'pillText':       '#f0f0fa',
}


# ---------------------------------------------------------------------------
# Back-compat module-level shortcuts
# ---------------------------------------------------------------------------

ACCENT    = PALETTE['accent']
BG        = PALETTE['bg']
PANEL     = PALETTE['panel']
PANEL_ALT = PALETTE['panelAlt']
BORDER    = PALETTE['border']
TEXT      = PALETTE['text']
TEXT_DIM  = PALETTE['textDim']
DANGER    = PALETTE['danger']
OK        = PALETTE['ok']

P = PALETTE  # local shortcut for stylesheet f-string

MONO_FONT = '"JetBrains Mono", "Cascadia Mono", "Consolas", "Menlo", monospace'

STYLESHEET = f"""
* {{
    font-family: "Inter", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 10pt;
    color: {P['text']};
    font-weight: 500;
}}

QMainWindow {{
    background-color: {P['bg']};
    border: 1px solid {P['border']};
}}

QDialog {{
    background-color: {P['bg']};
}}

/* ── Custom title bar ──────────────────────────────────────────────────── */

QWidget#TitleBar {{
    background-color: {P['panel']};
    border-bottom: 1px solid {P['border']};
}}

QLabel#titleLabel {{
    font-size: 11pt;
    font-weight: 700;
    letter-spacing: 0.5px;
    color: {P['text']};
    background: transparent;
}}

QLabel#titleDot {{
    color: {P['accent']};
    font-size: 9pt;
    background: transparent;
}}

QPushButton#winCtrlBtn {{
    background: transparent;
    border: none;
    border-radius: 5px;
    color: {P['textDim']};
    font-size: 12pt;
    font-weight: 500;
    padding: 0;
    min-width: 32px;
    max-width: 32px;
    min-height: 28px;
    max-height: 28px;
}}

QPushButton#winCtrlBtn:hover {{
    background: rgba(255, 255, 255, 0.07);
    color: {P['text']};
}}

QPushButton#winCtrlBtn[role="close"]:hover {{
    background: {P['dangerHover']};
    color: {P['white']};
}}

/* ── Top toolbar ───────────────────────────────────────────────────────── */

QWidget#TopBar {{
    background-color: {P['panel']};
    border-bottom: 1px solid {P['border']};
}}

/* ── Slot rail ─────────────────────────────────────────────────────────── */

QListWidget#SlotRail {{
    background-color: {P['bg']};
    border: none;
    border-right: 1px solid {P['border']};
    outline: none;
    padding: 6px 0;
}}

QListWidget#SlotRail::item {{
    padding: 0;
    border: none;
    background: transparent;
}}

QListWidget#SlotRail::item:selected {{
    background: transparent;
}}

QListWidget#SlotRail::item:hover {{
    background: transparent;
}}

/* ── Labels ────────────────────────────────────────────────────────────── */

QLabel {{
    color: {P['text']};
    background: transparent;
    font-weight: 500;
}}

QLabel[role="heading"] {{
    font-size: 14pt;
    font-weight: 600;
    color: {P['accent']};
}}

QLabel[role="slotTag"] {{
    font-size: 15pt;
    font-weight: 700;
    color: {P['accent']};
    padding: 2px 8px 2px 14px;
    border: none;
    border-left: 3px solid {P['accent']};
    background: transparent;
}}

QLabel[role="dim"] {{
    color: {P['textDim']};
    font-weight: 500;
}}

QLabel[role="paramLabel"] {{
    color: {P['textDim']};
    font-size: 9pt;
    font-weight: 500;
    letter-spacing: 0.3px;
}}

QLabel[role="paramValue"] {{
    color: {P['text']};
    font-weight: 600;
}}

QLabel[role="valuePill"] {{
    background-color: {P['pillBg']};
    color: {P['pillText']};
    font-family: {MONO_FONT};
    font-weight: 600;
    font-size: 9pt;
    padding: 3px 10px;
    border: 1px solid {P['pillBorder']};
    border-radius: 10px;
}}

QLabel#RecipeImage {{
    background-color: {P['bgDeep']};
    border: 1px solid {P['border']};
    border-radius: 8px;
    color: {P['textDim']};
}}

QLabel#RecipeTitle {{
    font-size: 13pt;
    font-weight: 700;
    color: {P['text']};
    letter-spacing: 0.2px;
}}

/* ── Inputs ────────────────────────────────────────────────────────────── */

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {P['panelAlt']};
    border: 1px solid {P['border']};
    border-radius: 6px;
    padding: 4px 7px;
    min-height: 20px;
    font-weight: 600;
    selection-background-color: {P['accent']};
    selection-color: {P['onAccent']};
}}

/* Accent halo on focus — border + subtle background tint */
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 2px solid {P['accent']};
    padding: 3px 6px;
    background-color: rgba(232, 132, 10, 0.06);
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
}}

QComboBox QAbstractItemView {{
    background-color: {P['panelRaised']};
    border: 1px solid {P['border']};
    border-radius: 6px;
    selection-background-color: {P['accent']};
    selection-color: {P['onAccent']};
    padding: 2px;
}}

/* ── Buttons ───────────────────────────────────────────────────────────── */

QPushButton {{
    background-color: {P['panelAlt']};
    border: 1px solid {P['border']};
    border-radius: 6px;
    padding: 6px 14px;
    color: {P['text']};
    font-weight: 600;
}}

QPushButton:hover {{
    border: 1px solid {P['accent']};
    color: {P['accent']};
    background-color: rgba(232, 132, 10, 0.06);
}}

QPushButton:pressed {{
    background-color: {P['bg']};
}}

QPushButton[role="primary"] {{
    background-color: {P['accent']};
    color: {P['onAccent']};
    font-weight: 700;
    border: 1px solid {P['accent']};
    border-radius: 6px;
}}

QPushButton[role="primary"]:hover {{
    background-color: {P['accentHover']};
    color: {P['onAccent']};
}}

QPushButton:disabled {{
    color: {P['textMute']};
    border-color: {P['borderSoft']};
    background-color: {P['bg']};
}}

/* ── Status bar ────────────────────────────────────────────────────────── */

QStatusBar {{
    background-color: {P['panel']};
    color: {P['textDim']};
    border-top: 1px solid {P['border']};
    font-size: 9pt;
    font-weight: 500;
}}

/* ── Dividers ──────────────────────────────────────────────────────────── */

QFrame[role="divider"] {{
    background: {P['border']};
    max-height: 1px;
    min-height: 1px;
    border: none;
}}

/* ── Connection dot ────────────────────────────────────────────────────── */

QLabel#connDot[state="off"] {{
    color: {P['danger']};
}}

QLabel#connDot[state="connecting"] {{
    color: {P['accent']};
}}

QLabel#connDot[state="on"] {{
    color: {P['ok']};
}}

/* ── Group boxes — card surface with subtle glass overlay ──────────────── */

QGroupBox {{
    border: 1px solid {P['border']};
    border-radius: 10px;
    margin-top: 18px;
    padding-top: 14px;
    padding-left: 8px;
    padding-right: 8px;
    padding-bottom: 10px;
    background-color: {P['panel']};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 8px;
    color: {P['accent']};
    font-weight: 700;
    font-size: 8pt;
    letter-spacing: 1px;
    text-transform: uppercase;
    background: transparent;
}}

/* ── Scroll areas ──────────────────────────────────────────────────────── */

QScrollArea, QScrollArea > QWidget > QWidget {{
    background-color: {P['bg']};
}}

QScrollBar:vertical {{
    background: {P['bg']};
    width: 5px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {P['border']};
    border-radius: 2px;
    min-height: 24px;
}}

QScrollBar::handle:vertical:hover {{
    background: {P['accent']};
}}

QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
}}

/* ── Recipe list ───────────────────────────────────────────────────────── */

QListWidget#RecipeList {{
    background-color: {P['bg']};
    border: none;
    border-right: 1px solid {P['border']};
    outline: none;
}}

QListWidget#RecipeList::item {{
    padding: 6px 8px;
    border-bottom: 1px solid {P['borderSoft']};
    color: {P['text']};
    border-radius: 0px;
}}

QListWidget#RecipeList::item:selected {{
    background-color: {P['rowSel']};
    color: {P['accent']};
    border-left: 3px solid {P['accent']};
    padding-left: 5px;
}}

QListWidget#RecipeList::item:hover:!selected {{
    background-color: {P['rowHover']};
}}

/* ── File / tool buttons ───────────────────────────────────────────────── */

QToolButton {{
    background-color: {P['panelAlt']};
    border: 1px solid {P['border']};
    border-radius: 6px;
    padding: 6px 14px;
    color: {P['text']};
    font-weight: 600;
}}

QToolButton:hover {{
    border: 1px solid {P['accent']};
    color: {P['accent']};
    background-color: rgba(232, 132, 10, 0.06);
}}

QToolButton:pressed {{
    background-color: {P['bg']};
}}

QMenu {{
    background-color: {P['panelRaised']};
    border: 1px solid {P['border']};
    border-radius: 8px;
    padding: 4px 4px;
}}

QMenu::item {{
    padding: 6px 20px 6px 12px;
    color: {P['text']};
    font-weight: 500;
    border-radius: 5px;
}}

QMenu::item:selected {{
    background-color: rgba(232, 132, 10, 0.15);
    color: {P['accent']};
}}

QMenu::separator {{
    height: 1px;
    background: {P['border']};
    margin: 4px 0;
}}
"""
