import time

import cv2

WINDOW_NAME = "KungFu Chess"


def run_gui(engine, controller, renderer):
    """Owns the cv2 window, mouse handling, and the frame-timing loop.
    Drawing itself is delegated to `renderer` (a GraphicsRenderer) - this
    function only translates clicks to controller commands, advances time,
    and shows each rendered frame.
    """
    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            controller.click(x, y)
        elif event == cv2.EVENT_RBUTTONDOWN:
            controller.jump(x, y)

    cv2.namedWindow(WINDOW_NAME)
    cv2.setMouseCallback(WINDOW_NAME, on_mouse)

    last_frame = time.time()
    while True:
        now = time.time()
        elapsed_ms = int((now - last_frame) * 1000)
        last_frame = now

        engine.wait(elapsed_ms)
        active_by_start = {move.start: move for move in engine.active_moves()}
        active_by_cell = {jump.cell: jump for jump in engine.active_jumps()}
        snapshot = engine.snapshot(selected=controller.selected)
        renderer.advance(elapsed_ms)

        frame = renderer.render(snapshot, active_by_start, active_by_cell)

        if snapshot.game_over:
            cv2.imshow(WINDOW_NAME, frame.img)
            cv2.waitKey(0)
            break

        cv2.imshow(WINDOW_NAME, frame.img)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break

    cv2.destroyAllWindows()
