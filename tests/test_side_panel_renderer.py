from game.move_history import MoveRecord
from UI.rendering.side_panel_renderer import SidePanelRenderer


def _entries(n):
    return [
        MoveRecord(color="w", piece="wP", start=(1, i % 8), end=(2, i % 8), timestamp=i * 100)
        for i in range(n)
    ]


def test_render_returns_canvas_of_requested_shape():
    renderer = SidePanelRenderer(200, (30, 30, 30, 255), (255, 255, 255, 255))
    panel = renderer.render(400, 4, "White", 5, _entries(3))

    assert panel.img.shape == (400, 200, 4)


def test_render_supports_three_channel_frames():
    renderer = SidePanelRenderer(200, (30, 30, 30, 255), (255, 255, 255, 255))
    panel = renderer.render(400, 3, "Black", 0, _entries(0))

    assert panel.img.shape == (400, 200, 3)


def test_render_with_more_entries_than_fit_keeps_same_shape():
    renderer = SidePanelRenderer(200, (30, 30, 30, 255), (255, 255, 255, 255))
    panel = renderer.render(150, 4, "White", 12, _entries(50))

    assert panel.img.shape == (150, 200, 4)
