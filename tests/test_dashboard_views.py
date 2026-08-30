import pandas as pd

from dashboard_views import build_snapshot


def test_snapshot_keeps_latest_contract_and_aggregate_history():
    metrics = pd.DataFrame([
        {"trade_date": "2026-08-28", "exchange": "SHFE", "symbol": "RB", "contract": "RB2609",
         "open_interest": 10, "source": "official", "top20_long": 10, "top20_short": 5,
         "net_position": 5, "net_position_ratio": 1 / 3, "delta_net_1d": 0, "consensus": .2, "bull_score": 1},
        {"trade_date": "2026-08-28", "exchange": "SHFE", "symbol": "RB", "contract": "RB2701",
         "open_interest": 20, "source": "official", "top20_long": 20, "top20_short": 10,
         "net_position": 10, "net_position_ratio": 1 / 3, "delta_net_1d": 0, "consensus": .2, "bull_score": 1},
    ])
    positions = pd.DataFrame([
        {"trade_date": "2026-08-28", "symbol": "RB", "source": "official", "broker": "A",
         "long_change": 3, "short_change": 1},
    ])
    history = pd.DataFrame([
        {"trade_date": "2026-08-27", "symbol": "RB", "contract": "RB", "source": "aggregate",
         "top20_long": 100, "top20_short": 80, "net_position": 20, "net_position_ratio": .1},
        {"trade_date": "2026-08-28", "symbol": "RB", "contract": "RB", "source": "official-aggregate-via-akshare",
         "top20_long": 110, "top20_short": 85, "net_position": 25, "net_position_ratio": .12},
    ])
    for frame in (metrics, positions, history):
        frame["trade_date"] = pd.to_datetime(frame["trade_date"])

    result = build_snapshot(metrics, positions, history, pd.Timestamp("2026-08-28").date(), ["黑色"])

    assert len(result) == 1
    assert result.iloc[0]["contract"] == "RB2701"
    assert result.iloc[0]["net_position"] == 25
    assert result.iloc[0]["delta_net_1d"] == 5
    assert result.iloc[0]["net_change"] == 2
