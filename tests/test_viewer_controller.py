from server.viewer_controller import ViewerController


def test_selected_is_always_none():
    viewer = ViewerController()

    assert viewer.selected is None


def test_click_never_raises_and_changes_nothing():
    viewer = ViewerController()

    viewer.click(0, 0)  # must not raise

    assert viewer.selected is None


def test_jump_never_raises_and_changes_nothing():
    viewer = ViewerController()

    viewer.jump(0, 0)  # must not raise

    assert viewer.selected is None
