from bus.event_bus import EventBus
from bus.events import GameEndedEvent, GameStartedEvent, InvalidMoveEvent, MoveMadeEvent, ScoreChangedEvent
from bus_handlers.move_log_display_state import MoveLogDisplayState
from bus_handlers.score_display_state import ScoreDisplayState
from client_net.remote_event_source import RemoteEventSource


def test_score_changed_message_publishes_a_real_score_changed_event():
    bus = EventBus()
    received = []
    bus.subscribe(ScoreChangedEvent, received.append)
    source = RemoteEventSource(bus)

    source.handle_message({"type": "score_changed", "player": "w", "new_score": 4})

    assert received == [ScoreChangedEvent(player="w", new_score=4)]


def test_move_made_message_publishes_a_real_move_made_event():
    bus = EventBus()
    received = []
    bus.subscribe(MoveMadeEvent, received.append)
    source = RemoteEventSource(bus)

    source.handle_message({
        "type": "move_made", "color": "w", "piece": "wR",
        "start": [0, 0], "end": [0, 2], "timestamp": 1000,
    })

    assert received == [MoveMadeEvent(color="w", piece="wR", start=(0, 0), end=(0, 2), timestamp=1000)]


def test_invalid_move_message_publishes_a_real_invalid_move_event():
    bus = EventBus()
    received = []
    bus.subscribe(InvalidMoveEvent, received.append)
    source = RemoteEventSource(bus)

    source.handle_message({
        "type": "invalid_move", "reason": "on_cooldown", "start": [0, 0], "end": [0, 1],
    })

    assert received == [InvalidMoveEvent(reason="on_cooldown", start=(0, 0), end=(0, 1))]


def test_game_started_message_publishes_a_real_game_started_event():
    bus = EventBus()
    received = []
    bus.subscribe(GameStartedEvent, received.append)
    source = RemoteEventSource(bus)

    source.handle_message({"type": "game_started", "white_player": "w", "black_player": "b"})

    assert received == [GameStartedEvent(white_player="w", black_player="b")]


def test_game_ended_message_publishes_a_real_game_ended_event():
    bus = EventBus()
    received = []
    bus.subscribe(GameEndedEvent, received.append)
    source = RemoteEventSource(bus)

    source.handle_message({"type": "game_ended", "winner": "w", "reason": "king_captured"})

    assert received == [GameEndedEvent(winner="w", reason="king_captured")]


def test_unrecognized_type_does_not_publish_and_does_not_raise():
    bus = EventBus()
    received = []
    bus.subscribe(ScoreChangedEvent, received.append)
    bus.subscribe(MoveMadeEvent, received.append)
    source = RemoteEventSource(bus)

    source.handle_message({"type": "some_future_message_type"})  # must not raise

    assert received == []


def test_malformed_score_changed_message_does_not_publish_and_does_not_raise():
    bus = EventBus()
    received = []
    bus.subscribe(ScoreChangedEvent, received.append)
    source = RemoteEventSource(bus)

    source.handle_message({"type": "score_changed", "player": "w"})  # missing new_score - must not raise

    assert received == []


def test_malformed_move_made_message_does_not_publish_and_does_not_raise():
    bus = EventBus()
    received = []
    bus.subscribe(MoveMadeEvent, received.append)
    source = RemoteEventSource(bus)

    source.handle_message({"type": "move_made", "color": "w", "piece": "wR"})  # missing fields - must not raise

    assert received == []


def test_score_display_state_reflects_a_remote_originated_event():
    # End-to-end-ish: a real EventBus + the EXISTING, unmodified
    # ScoreDisplayState on the "client" side, fed purely through
    # RemoteEventSource - proving the display-state class needs no
    # awareness that this event came over the network rather than from a
    # live engine.
    client_bus = EventBus()
    source = RemoteEventSource(client_bus)
    score_state = ScoreDisplayState(client_bus)

    source.handle_message({"type": "score_changed", "player": "b", "new_score": 9})

    assert score_state.score_for("b") == 9
    assert score_state.score_for("w") == 0


def test_move_log_display_state_reflects_a_remote_originated_event():
    # Same proof for MoveLogDisplayState - both existing read models work
    # unmodified with network-originated events.
    client_bus = EventBus()
    source = RemoteEventSource(client_bus)
    move_log_state = MoveLogDisplayState(client_bus)

    source.handle_message({
        "type": "move_made", "color": "w", "piece": "wR",
        "start": [0, 0], "end": [0, 2], "timestamp": 1000,
    })

    entries = move_log_state.entries_for("w")
    assert len(entries) == 1
    assert entries[0].piece == "wR"
    assert entries[0].start == (0, 0)
    assert entries[0].end == (0, 2)
    assert entries[0].timestamp == 1000
    assert move_log_state.entries_for("b") == ()
