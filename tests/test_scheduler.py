from scheduler import runner

def test_get_due_sites_respects_per_site_interval(monkeypatch):
    monkeypatch.setattr(runner, "DEFAULT_INTERVAL_MINUTES", 10)
    runner._last_run.clear()
    fast = {"id": "fast", "check_interval_minutes": 5}
    slow = {"id": "slow", "check_interval_minutes": 30}
    default = {"id": "default", "check_interval_minutes": None}

    # Never-run sites are always due
    assert runner.get_due_sites([fast, slow, default], now=0) == [fast, slow, default]

    for s in (fast, slow, default):
        runner._last_run[s["id"]] = 0
    assert runner.get_due_sites([fast, slow, default], now=4 * 60) == []
    assert runner.get_due_sites([fast, slow, default], now=5 * 60) == [fast]
    assert runner.get_due_sites([fast, slow, default], now=10 * 60) == [fast, default]
    assert runner.get_due_sites([fast, slow, default], now=30 * 60) == [fast, slow, default]
    runner._last_run.clear()
