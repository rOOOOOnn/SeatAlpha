from pathlib import Path

import pandas as pd

from services.win_rate import (
    calculate_win_rates,
    parse_manual_ranking_frame,
    ranking_file_for_symbol,
)


def _raw_export_rows(days: int = 30) -> pd.DataFrame:
    rows = []
    dates = pd.bdate_range("2026-01-05", periods=days)
    for index, trade_date in enumerate(dates):
        row = [None] * 29
        row[0] = trade_date
        row[7], row[8] = "中信期货有限公司", 100
        row[12], row[13] = "乾坤期货有限公司", 80
        row[26] = 100 + index
        rows.append(row)
    return pd.DataFrame(rows)


def test_manual_export_parser_builds_net_positions_from_independent_lists():
    result = parse_manual_ranking_frame(_raw_export_rows(2))

    first_day = result[result["trade_date"].eq(pd.Timestamp("2026-01-05"))]
    assert first_day.set_index("broker")["net_position"].to_dict() == {
        "中信期货": 100,
        "乾坤期货": -80,
    }
    assert first_day["close"].unique().tolist() == [100]


def test_win_rate_ranking_uses_future_trading_days_and_minimum_sample():
    history = parse_manual_ranking_frame(_raw_export_rows(30))
    result = calculate_win_rates(
        history,
        pd.Timestamp("2026-02-28"),
        min_sample_days=20,
    )

    assert result["broker"].tolist() == ["中信期货", "乾坤期货"]
    long_row = result[result["broker"].eq("中信期货")].iloc[0]
    short_row = result[result["broker"].eq("乾坤期货")].iloc[0]
    assert long_row["win_rate"] == 1.0
    assert long_row["win_rate_5d"] == 1.0
    assert long_row["samples_20d"] == 10
    assert long_row["sample_days"] == 25
    assert long_row["current_long_position"] == 100
    assert long_row["current_short_position"] == 0
    assert short_row["win_rate"] == 0.0
    assert short_row["current_long_position"] == 0
    assert short_row["current_short_position"] == 80


def test_win_rate_excludes_short_sample_brokers():
    history = parse_manual_ranking_frame(_raw_export_rows(19))
    result = calculate_win_rates(
        history,
        pd.Timestamp("2026-02-28"),
        min_sample_days=20,
    )

    assert result.empty


def test_ranking_file_lookup_ignores_nested_failed_exports(tmp_path: Path):
    base = tmp_path / "data" / "ifind_manual" / "raw" / "member_rankings" / "交易所"
    failed = base / "needs_reexport"
    failed.mkdir(parents=True)
    (failed / "RB.xlsx").touch()
    good = base / "RB_ALL_20250818_20260916.xlsx"
    good.touch()

    assert ranking_file_for_symbol(tmp_path, "RB") == good
