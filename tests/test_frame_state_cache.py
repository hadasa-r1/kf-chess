from concurrent.futures import ThreadPoolExecutor

from client_net.frame_state_cache import FrameStateCache


def test_latest_returns_none_before_any_update():
    cache = FrameStateCache()

    assert cache.latest() is None


def test_latest_returns_the_most_recent_update():
    cache = FrameStateCache()

    cache.update("frame-1")
    cache.update("frame-2")

    assert cache.latest() == "frame-2"


def test_concurrent_update_and_read_does_not_crash():
    cache = FrameStateCache()

    def update_and_read(i):
        cache.update(f"frame-{i}")
        return cache.latest()

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(update_and_read, range(200)))

    assert len(results) == 200
    assert cache.latest() is not None
