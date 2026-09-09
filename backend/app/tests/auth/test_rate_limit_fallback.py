from app.core import rate_limit


def test_local_rate_limit_blocks_after_window_quota(monkeypatch):
    rate_limit._fallback_windows.clear()
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: 100.0)

    assert rate_limit._check_local_limit("auth:test", 2, 60)
    assert rate_limit._check_local_limit("auth:test", 2, 60)
    assert not rate_limit._check_local_limit("auth:test", 2, 60)


def test_local_rate_limit_recovers_after_window(monkeypatch):
    rate_limit._fallback_windows.clear()
    clock = [100.0]
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: clock[0])

    assert rate_limit._check_local_limit("auth:test", 1, 60)
    assert not rate_limit._check_local_limit("auth:test", 1, 60)
    clock[0] = 161.0
    assert rate_limit._check_local_limit("auth:test", 1, 60)
