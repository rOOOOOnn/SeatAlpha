import pandas as pd

from services.broker_classifier import classify_broker, enrich_broker_classification
from services.broker_normalizer import normalize_broker_name
from services.position_aggregator import (
    aggregate_category_positions,
    build_three_category_snapshot,
)
from services.signal_engine import direction_label, direction_score
from settings.broker_classification import SEAT_CLASSIFICATION


def test_aliases_and_research_categories_are_normalized_once():
    assert normalize_broker_name(" 高盛期货（深圳） ") == "乾坤期货"
    assert normalize_broker_name("中信期货有限公司") == "中信期货"
    assert normalize_broker_name("国泰君安期货(上海)") == "国泰君安"
    assert classify_broker("高盛期货") == "qian_kun"
    assert classify_broker("摩根大通期货有限公司") == "qian_kun"
    assert classify_broker("瑞银期货") == "qian_kun"
    assert classify_broker("混沌天成期货") == "hot_money"
    assert classify_broker("永安期货") == "hot_money"
    assert classify_broker("中财期货") == "hot_money"
    assert classify_broker("新湖期货") == "hot_money"
    assert classify_broker("方正中期") == "institution"
    assert classify_broker("国元") == "institution"
    assert classify_broker("平安期货") == "institution"
    assert classify_broker("东方财富期货") == "retail"
    assert classify_broker("徽商期货") == "retail"
    assert classify_broker("弘业期货") == "retail"
    assert classify_broker("瑞达期货") == "retail"
    assert classify_broker("国贸期货") == "other"


def test_unknown_broker_is_retained_as_other():
    frame = pd.DataFrame([{"broker": "示例未知席位"}])
    result = enrich_broker_classification(frame)
    assert result.iloc[0]["broker_category"] == "other"


def test_institution_and_retail_baskets_match_configured_scope():
    assert {"方正中期", "国元期货", "平安期货"}.issubset(
        SEAT_CLASSIFICATION["institution"]
    )
    assert SEAT_CLASSIFICATION["retail"] == {
        "东方财富", "徽商期货", "弘业期货", "瑞达期货",
    }
    configured = [
        broker
        for brokers in SEAT_CLASSIFICATION.values()
        for broker in brokers
    ]
    assert len(configured) == len(set(configured))


def test_category_aggregation_uses_identical_contract_population():
    rows = [
        ("高盛期货", 120, 60, 12, 2),
        ("中信期货", 300, 200, 20, 5),
        ("东方财富", 100, 180, -4, 10),
        ("永安期货", 90, 70, 6, 1),
        ("未知席位", 50, 50, 0, 0),
    ]
    positions = pd.DataFrame([
        {"trade_date": "2026-09-01", "exchange": "SHFE", "symbol": "CU", "contract": "CU2610",
         "broker": broker, "long_position": lp, "short_position": sp,
         "long_change": lc, "short_change": sc, "source": "official"}
        for broker, lp, sp, lc, sc in rows
    ])
    positions["trade_date"] = pd.to_datetime(positions["trade_date"])
    result = aggregate_category_positions(positions)
    assert set(result["broker_category"]) == {
        "qian_kun", "hot_money", "institution", "retail", "other"
    }
    qk = result[result["broker_category"].eq("qian_kun")].iloc[0]
    assert qk["net_position"] == 60
    assert qk["net_change"] == 10
    hot_money = result[result["broker_category"].eq("hot_money")].iloc[0]
    assert hot_money["net_position"] == 20
    assert hot_money["net_change"] == 5


def test_three_way_snapshot_builds_divergence_and_consensus():
    positions = pd.DataFrame([
        {"trade_date": "2026-09-01", "exchange": "SHFE", "symbol": symbol, "contract": f"{symbol}2610",
         "broker": broker, "long_position": lp, "short_position": sp,
         "long_change": lc, "short_change": sc, "source": "official"}
        for symbol, scale in (("CU", 1), ("AL", -1))
        for broker, lp, sp, lc, sc in (
            ("高盛期货", 120 + 30 * scale, 100, 8 * scale, 0),
            ("中信期货", 220 + 40 * scale, 200, 10 * scale, 0),
            ("东方财富", 100, 140 + 20 * scale, 0, 7 * scale),
            ("中财期货", 90 + 20 * scale, 80, 5 * scale, 0),
        )
    ])
    positions["trade_date"] = pd.to_datetime(positions["trade_date"])
    base = pd.DataFrame([
        {"symbol": symbol, "contract": f"{symbol}2610", "sector": "有色", "name": symbol,
         "close": 100, "price_date": pd.Timestamp("2026-09-01")}
        for symbol in ("CU", "AL")
    ])
    category, wide = build_three_category_snapshot(positions, base, pd.Timestamp("2026-09-01").date())
    assert len(category) == 8
    assert set(category["broker_category"]) == {
        "qian_kun", "hot_money", "institution", "retail"
    }
    assert {"qk_inst_divergence", "qk_retail_divergence", "inst_retail_divergence",
            "three_way_consensus", "three_way_state"}.issubset(wide.columns)
    assert set(category["contract"].dropna()) == {"CU2610", "AL2610"}


def test_snapshot_supports_same_contract_weekly_change_and_marks_missing_month():
    positions = pd.DataFrame([
        {"trade_date": day, "exchange": "SHFE", "symbol": "CU", "contract": "CU2610",
         "broker": broker, "long_position": long_position, "short_position": short_position,
         "long_change": 0, "short_change": 0, "source": "official"}
        for day, values in (
            ("2026-09-01", (("高盛期货", 120, 100), ("中信期货", 200, 180))),
            ("2026-09-08", (("高盛期货", 150, 100), ("中信期货", 190, 200))),
        )
        for broker, long_position, short_position in values
    ])
    positions["trade_date"] = pd.to_datetime(positions["trade_date"])
    base = pd.DataFrame([{
        "symbol": "CU", "contract": "CU2610", "sector": "有色", "name": "沪铜",
        "close": 100, "price_date": pd.Timestamp("2026-09-08"),
    }])

    weekly, _ = build_three_category_snapshot(
        positions, base, pd.Timestamp("2026-09-08").date(), change_period=5
    )
    foreign = weekly[weekly["broker_category"].eq("qian_kun")].iloc[0]
    assert foreign["change_available"]
    assert foreign["net_change"] == 30
    assert foreign["change_baseline_date"] == pd.Timestamp("2026-09-01")

    monthly, _ = build_three_category_snapshot(
        positions, base, pd.Timestamp("2026-09-08").date(), change_period=20
    )
    assert not monthly["change_available"].any()
    assert monthly["net_change"].isna().all()


def test_direction_labels_use_absolute_bounded_signal_not_cross_section_rank():
    # A tiny current gross position must not let a large historical change
    # produce an unbounded score or reverse an aggregate direction label.
    assert direction_score(-4, 5, 303, -1 / 3) <= 0.25
    assert direction_label(direction_score(-40_665, 100_000, -19_231, -1 / 3)) == "strong_short"
    assert direction_label(direction_score(-394_772, 8_000_000, -93_125, .02)) == "short"


def test_snapshot_keeps_direction_score_separate_from_relative_z_score():
    positions = pd.DataFrame([
        {"trade_date": "2026-09-01", "exchange": "SHFE", "symbol": symbol,
         "contract": f"{symbol}2610", "broker": "方正中期",
         "long_position": long_position, "short_position": short_position,
         "long_change": 0, "short_change": 0, "source": "official"}
        for symbol, long_position, short_position in (("CU", 90, 110), ("AL", 10, 190))
    ])
    positions["trade_date"] = pd.to_datetime(positions["trade_date"])
    base = pd.DataFrame([
        {"symbol": symbol, "contract": f"{symbol}2610", "sector": "有色", "name": symbol,
         "close": 100, "price_date": pd.Timestamp("2026-09-01")}
        for symbol in ("CU", "AL")
    ])
    category, wide = build_three_category_snapshot(positions, base, pd.Timestamp("2026-09-01").date())
    institution = category[category["broker_category"].eq("institution")]
    assert set(institution["signal_label"]) == {"short", "strong_short"}
    assert {"institution_direction", "institution_signal"}.issubset(wide.columns)
