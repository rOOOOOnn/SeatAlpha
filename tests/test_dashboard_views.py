import pandas as pd

from dashboard_views import broker_profile_rows, build_broker_profiles, build_snapshot


def test_broker_profiles_remove_placeholders_and_prefer_largest_seat():
    positions = pd.DataFrame([
        {"trade_date": "2026-09-01", "source": "official", "symbol": "CF", "broker": "-",
         "long_position": 0, "short_position": 0, "long_change": 0, "short_change": 0},
        {"trade_date": "2026-09-01", "source": "official", "symbol": "CF", "broker": "Small",
         "long_position": 20, "short_position": 10, "long_change": 1, "short_change": -1},
        {"trade_date": "2026-09-01", "source": "official", "symbol": "MA", "broker": "Large",
         "long_position": 100, "short_position": 80, "long_change": 4, "short_change": 2},
        {"trade_date": "2026-08-28", "source": "official", "symbol": "MA", "broker": "Old",
         "long_position": 999, "short_position": 999, "long_change": 0, "short_change": 0},
    ])
    positions["trade_date"] = pd.to_datetime(positions["trade_date"])

    latest, options = build_broker_profiles(positions, pd.Timestamp("2026-09-02").date())
    profile = broker_profile_rows(latest, options[0])

    assert options == ["Large", "Small"]
    assert "-" not in latest["broker"].tolist()
    assert profile.iloc[0]["net_position"] == 20


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


def test_snapshot_uses_aggregate_history_before_first_full_metric():
    metrics = pd.DataFrame(columns=["trade_date", "source", "symbol"])
    positions = pd.DataFrame(columns=["trade_date", "source", "symbol"])
    history = pd.DataFrame([
        {"trade_date": "2026-08-20", "exchange": "SHFE", "symbol": "RB", "contract": "RB",
         "source": "official-aggregate-via-akshare", "top20_long": 120, "top20_short": 100,
         "net_position": 20, "net_position_ratio": 20 / 220},
        {"trade_date": "2026-08-21", "exchange": "SHFE", "symbol": "RB", "contract": "RB",
         "source": "official-aggregate-via-akshare", "top20_long": 130, "top20_short": 105,
         "net_position": 25, "net_position_ratio": 25 / 235},
    ])
    contracts = pd.DataFrame([
        {"trade_date": "2026-08-21", "exchange": "SHFE", "symbol": "RB", "contract": "RB2701",
         "source": "ifind-price-history", "close": 3150, "open_interest": 1000},
    ])
    for frame in (metrics, positions, history, contracts):
        frame["trade_date"] = pd.to_datetime(frame["trade_date"])

    result = build_snapshot(
        metrics, positions, history, pd.Timestamp("2026-08-21").date(), ["黑色"], contracts
    )

    assert result.iloc[0]["contract"] == "RB2701"
    assert result.iloc[0]["net_position"] == 25
    assert result.iloc[0]["delta_net_1d"] == 5
    assert result.iloc[0]["price_date"] == pd.Timestamp("2026-08-21")
    assert pd.isna(result.iloc[0]["consensus"])
    assert result.iloc[0]["signal"] == "仅汇总数据"


def test_snapshot_keeps_price_and_position_dates_independent():
    metrics = pd.DataFrame([{
        "trade_date": "2026-08-21", "exchange": "DCE", "symbol": "P", "contract": "P2701",
        "open_interest": 30, "close": 10160, "source": "sina-fallback", "price_source": "ifind-http",
        "top20_long": 100, "top20_short": 120, "net_position": -20, "net_position_ratio": -20 / 220,
        "delta_net_1d": 0, "consensus": -.2, "bull_score": -1,
    }])
    positions = pd.DataFrame([{
        "trade_date": "2026-08-21", "source": "sina-fallback", "symbol": "P", "broker": "A",
        "long_change": 1, "short_change": 2,
    }])
    history = pd.DataFrame([{
        "trade_date": "2026-08-21", "exchange": "DCE", "symbol": "P", "contract": "P2701",
        "source": "sina-fallback", "top20_long": 100, "top20_short": 120,
        "net_position": -20, "net_position_ratio": -20 / 220,
    }])
    contracts = pd.DataFrame([
        {"trade_date": "2026-08-21", "exchange": "DCE", "symbol": "P", "contract": "P2701",
         "source": "ifind-http", "close": 10160, "open_interest": 30},
        {"trade_date": "2026-09-01", "exchange": "DCE", "symbol": "P", "contract": "P2701",
         "source": "ifind-http", "close": 10220, "open_interest": 40},
    ])
    for frame in (metrics, positions, history, contracts):
        frame["trade_date"] = pd.to_datetime(frame["trade_date"])

    result = build_snapshot(metrics, positions, history, pd.Timestamp("2026-09-02").date(), ["油脂油料"], contracts)

    assert result.iloc[0]["asof_date"] == pd.Timestamp("2026-08-21")
    assert result.iloc[0]["price_date"] == pd.Timestamp("2026-09-01")
    assert result.iloc[0]["close"] == 10220
