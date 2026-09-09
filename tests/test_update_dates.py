from datetime import date, datetime
from zoneinfo import ZoneInfo

import pipeline.update as update_module
from pipeline.update import latest_weekday

SHANGHAI = ZoneInfo("Asia/Shanghai")


def test_current_trade_day_waits_for_evening_publication_window():
    monday = date(2026, 9, 7)

    assert latest_weekday(
        monday, now=datetime(2026, 9, 7, 17, tzinfo=SHANGHAI)
    ) == date(2026, 9, 4)
    assert latest_weekday(
        monday, now=datetime(2026, 9, 7, 20, tzinfo=SHANGHAI)
    ) == monday


def test_weekend_observation_date_uses_previous_friday():
    assert latest_weekday(
        date(2026, 9, 6), now=datetime(2026, 9, 6, 21, tzinfo=SHANGHAI)
    ) == date(2026, 9, 4)


def test_fast_daily_update_skips_slow_history_backfills(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(update_module, "EXCHANGES", ())
    monkeypatch.setattr(
        update_module, "_backfill_main_prices", lambda path: calls.append("prices")
    )
    monkeypatch.setattr(
        update_module,
        "_backfill_position_history",
        lambda target, path: calls.append("positions"),
    )

    result = update_module.update(
        date(2026, 9, 8),
        path=tmp_path / "fast-update.duckdb",
        backfill_history=False,
    )

    assert result == {}
    assert calls == []
