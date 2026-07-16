import numpy as np

from UI.img import Img


def _cell_label(cell):
    row, col = cell
    return f"{chr(ord('a') + col)}{row + 1}"


class SidePanelRenderer:
    """Renders one player's score + move-list panel as a standalone Img,
    reusing Img.put_text the same way GraphicsRenderer draws everything
    else. Height/channel-count are passed in per-call so the panel always
    matches the current board canvas exactly (the board image's real pixel
    size can differ slightly from cell_size * board_height/width - see
    GraphicsRenderer's own display-scaling comment - and its channel count
    depends on whether board.png has an alpha channel).
    """

    HEADER_Y = 30
    COLUMN_HEADER_Y_OFFSET = 26
    LINE_HEIGHT = 24
    TOP_MARGIN = 60

    def __init__(self, width, background_color, text_color):
        self._width = width
        self._background_color = background_color
        self._text_color = text_color

    def render(self, height, channels, label, score, entries):
        panel = Img()
        panel.img = np.full((height, self._width, channels), self._background_color[:channels], dtype=np.uint8)

        text_color = self._text_color[:channels]
        panel.put_text(f"{label}  Score: {score}", 10, self.HEADER_Y,
                        font_size=0.7, color=text_color, thickness=2)
        panel.put_text("Time    Move", 10, self.HEADER_Y + self.COLUMN_HEADER_Y_OFFSET,
                        font_size=0.5, color=text_color, thickness=1)

        max_rows = max(0, (height - self.TOP_MARGIN) // self.LINE_HEIGHT)
        visible = entries[-max_rows:] if max_rows else ()

        y = self.TOP_MARGIN
        for entry in visible:
            text = f"{entry.timestamp:>6}  {entry.piece} {_cell_label(entry.start)}-{_cell_label(entry.end)}"
            panel.put_text(text, 10, y, font_size=0.5, color=text_color, thickness=1)
            y += self.LINE_HEIGHT

        return panel
