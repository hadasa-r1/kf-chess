"""Central configuration for the UI layer.

Like config/settings.py for game logic, this is the single place UI-layer
literal values live - no other UI module should contain literal values
like these.
"""

PIECES_DIR = "pieces2"
BOARD_FILE = "boards/start.txt"
DEFAULT_STATE = "idle"
BOARD_IMAGE_PATH = "UI/board.png"

# Per-side move-history/score panel (UI/rendering/side_panel_renderer.py)
SIDE_PANEL_WIDTH = 220
SIDE_PANEL_BACKGROUND_COLOR = (30, 30, 30, 255)  # BGRA, dark gray
SIDE_PANEL_TEXT_COLOR = (255, 255, 255, 255)  # BGRA, white

# Milliseconds each animation frame is shown before advancing to the next.
FRAME_DURATION_MS = 120

# Real asset folder names are "<KIND><COLOR>" (e.g. "KW" for white king),
# not the "<color><kind>" token format used by game logic (e.g. "wK").
FOLDER_MAP = {
    "wK": "KW", "bK": "KB",
    "wQ": "QW", "bQ": "QB",
    "wR": "RW", "bR": "RB",
    "wB": "BW", "bB": "BB",
    "wN": "NW", "bN": "NB",
    "wP": "PW", "bP": "PB",
}

# Real state frames live nested under "states/<name>/sprites/", not
# directly under "<name>/" - the value carries that full relative path.
STATE_MAP = {
    "idle": "states/idle/sprites",
    "move": "states/move/sprites",
    "jump": "states/jump/sprites",
    "short_rest": "states/short_rest/sprites",
    "long_rest": "states/long_rest/sprites",
}
