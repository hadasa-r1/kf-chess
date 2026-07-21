"""Central configuration for KungFu Chess.

All game constants live here so game logic never hardcodes magic numbers.
Changing timing, supported colors, or pawn direction only requires
editing this file - no other module should contain literal values like
these.
"""

# Rendering / timing (milliseconds)
CELL_SIZE = 100
MOVE_DURATION = 1000
JUMP_DURATION = 1000

# How long a piece must rest before it may act again, depending on what it
# just did (long_rest after a move, short_rest after a jump).
MOVE_COOLDOWN_DURATION = 2000
JUMP_COOLDOWN_DURATION = 1000

# Player colors supported by the game
COLORS = ("w", "b")

# Row delta a pawn advances by on a single step, per color.
# The double-step home rank is not configured here: it is derived from the
# board height in PawnMovement (1 for a downward color, height-2 for an
# upward one - one row in front of the back rank, as in standard chess),
# so the rule works for any board size.
PAWN_DIRECTION = {"w": -1, "b": 1}

# Token used to represent an empty cell on the board
EMPTY_CELL = "."

# Gameplay policy: may several moves be in flight at the same time?
# The real-time variant resolves a contested route in favour of whoever
# started first. Set False to force only one move in flight at a time.
ALLOW_CONCURRENT_MOVES = True

# Score value awarded to whichever color captures a piece of this kind.
# Kings are excluded (0) since a king capture already ends the game via
# KingCaptureWinCondition rather than scoring it.
PIECE_VALUES = {"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9, "K": 0}

# SQLite file backing server/user_store.py's persisted accounts (username,
# password hash, rating). Server-only: local hotseat play (main_gui.py)
# never touches this.
USER_DB_PATH = "kf_chess_users.db"
