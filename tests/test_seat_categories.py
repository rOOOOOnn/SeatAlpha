import pandas as pd

from services.broker_classifier import classify_broker, enrich_broker_classification
from services.broker_normalizer import normalize_broker_name
from services.position_aggregator import (
    aggregate_category_positions,
    build_three_category_snapshot,
)


def test_aliases_and_qian_kun_are_normalized_once():
    assert normalize_broker_name(" 高盛期货（深圳） ") == "乾坤期货"
    assert normalize_broker_name("中信期货有限公司") == "中信期货"
    assert normalize_broker_name("国泰君安期货(上海)") == "国泰君安"
    assert classify_broker("高盛期货") == "qian_kun"


def test_unknown_broker_is_retained_as_other():
    frame = pd.DataFrame([{"broker": "示例未知席位"}])
    result = enrich_broker_classification(frame)
    assert result.iloc[0]["broker_category"] == "other"


def test_category_aggregation_uses_identical_contract_population():
    rows = [
        ("高盛期货", 120, 60, 12, 2),
        ("中信期货", 300, 200, 20, 5),
        ("方正中期", 100, 180, -4, 10),
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
    assert set(result["broker_category"]) == {"qian_kun", "institution", "retail", "other"}
    qk = result[result["broker_category"].eq("qian_kun")].iloc[0]
    assert qk["net_position"] == 60
    assert qk["net_change"] == 10


def test_three_way_snapshot_builds_divergence_and_consensus():
    positions = pd.DataFrame([
        {"trade_date": "2026-09-01", "exchange": "SHFE", "symbol": symbol, "contract": f"{symbol}2610",
         "broker": broker, "long_position": lp, "short_position": sp,
         "long_change": lc, "short_change": sc, "source": "official"}
        for symbol, scale in (("CU", 1), ("AL", -1))
        for broker, lp, sp, lc, sc in (
            ("高盛期货", 120 + 30 * scale, 100, 8 * scale, 0),
            ("中信期货", 220 + 40 * scale, 200, 10 * scale, 0),
            ("方正中期", 100, 140 + 20 * scale, 0, 7 * scale),
        )
    ])
    positions["trade_date"] = pd.to_datetime(positions["trade_date"])
    base = pd.DataFrame([
        {"symbol": symbol, "contract": f"{symbol}2610", "sector": "有色", "name": symbol,
         "close": 100, "price_date": pd.Timestamp("2026-09-01")}
        for symbol in ("CU", "AL")
    ])
    category, wide = build_three_category_snapshot(positions, base, pd.Timestamp("2026-09-01").date())
    assert len(category) == 6
    assert {"qk_inst_divergence", "qk_retail_divergence", "inst_retail_divergence",
            "three_way_consensus", "three_way_state"}.issubset(wide.columns)
    assert set(category["contract"].dropna()) == {"CU2610", "AL2610"}
