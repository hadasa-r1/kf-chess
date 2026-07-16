import main_gui


def test_main_builds_and_launches_the_gui(monkeypatch):
    calls = []
    monkeypatch.setattr(main_gui, "_run_loop", lambda engine, controller, renderer: calls.append((engine, controller, renderer)))
    main_gui.main()
    assert len(calls) == 1
    engine, controller, renderer = calls[0]
    assert engine is not None and controller is not None and renderer is not None
