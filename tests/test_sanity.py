from src.sim.sanity import label_check, mirror_check, null_check, positive_check


def test_mirror():
    ok, detail = mirror_check(20, workers=4)
    assert ok, detail


def test_labels():
    ok, detail = label_check(15, workers=4)
    assert ok, detail


def test_null():
    ok, detail = null_check(150, workers=4)
    assert ok, detail


def test_positive():
    ok, detail = positive_check(20, workers=4)
    assert ok, detail


def test_mirror_catches_seat_leak(monkeypatch):
    import src.sim.match as match

    real = match.play_game

    def leaky(a, b, seed, swap_order=False, **kw):
        log = real(a, b, seed, swap_order=swap_order, **kw)
        log["winner"] = "a"
        return log

    monkeypatch.setattr(match, "play_game", leaky)
    ok, _ = mirror_check(5, workers=1)
    assert not ok
