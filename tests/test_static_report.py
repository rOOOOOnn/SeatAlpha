from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from services.static_report import build_static_daily_report
from settings.broker_classification import CATEGORY_ORDER


def _report_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    category_rows = []
    category_values = {
        "qian_kun": (120, 20, 0.6),
        "hot_money": (80, -10, 0.2),
        "institution": (-150, 30, -0.3),
        "retail": (-40, -5, -0.5),
    }
    for category, (net_position, net_change, consistency) in category_values.items():
        category_rows.append({
            "symbol": "CU", "sector": "有色", "broker_category": category,
            "net_position": net_position, "net_change": net_change,
            "long_position": 300 + max(net_position, 0),
            "short_position": 300 + max(-net_position, 0),
            "long_change": max(net_change, 0), "short_change": max(-net_change, 0),
            "consistency": consistency, "signal_score": consistency,
        })
    category_frame = pd.DataFrame(category_rows)
    wide_row = {
        "symbol": "CU", "name": "沪铜", "sector": "有色",
        "price_date": pd.Timestamp("2026-09-10"), "divergence_score": 2.1,
        "three_way_state": "high_divergence", "three_way_consensus": 0,
    }
    for category, (net_position, net_change, consistency) in category_values.items():
        wide_row[f"{category}_net_position"] = net_position
        wide_row[f"{category}_net_change"] = net_change
        wide_row[f"{category}_consistency"] = consistency
        wide_row[f"{category}_signal"] = consistency
        wide_row[f"{category}_long_position"] = 300 + max(net_position, 0)
        wide_row[f"{category}_short_position"] = 300 + max(-net_position, 0)
    wide = pd.DataFrame([wide_row])
    coverage = pd.DataFrame([{
        "symbol": "CU", "status": "最新", "reason": "行情与席位均达到数据基准日",
        "price_date": pd.Timestamp("2026-09-10"),
        "position_date": pd.Timestamp("2026-09-10"),
        "price_source": "ifind-price-history",
        "position_source": "ifind-member-ranking",
    }])
    return category_frame, wide, coverage


def test_static_daily_report_is_self_contained_and_scoped():
    category_rows, wide, coverage = _report_frames()

    report = build_static_daily_report(
        category_rows,
        wide,
        coverage,
        pd.Timestamp("2026-09-10").date(),
        "商品",
        "zh",
        CATEGORY_ORDER,
        updated_at=pd.Timestamp("2026-09-10 17:30"),
        generated_at=datetime(2026, 9, 11, 9, 15, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert report.startswith("<!doctype html>")
    assert "商品期货持仓日报" in report
    assert "2026-09-10" in report
    assert "沪铜" in report
    assert "iFinD 历史行情" in report
    assert "iFinD 会员持仓排名" in report
    assert "本文件的数据不会自动更新" in report
    assert '<svg viewBox="0 0 1200 500"' in report
    assert 'aria-label="四类席位一致性地图"' in report
    assert 'aria-label="机构与散户代理分歧地图"' in report
    assert "快速说明" in report
    assert report.count('class="quick-guide"') == 2
    assert "外资偏多" not in report
    assert 'class="tri-bar"' in report
    assert "<script" not in report


def test_static_daily_report_localizes_english_copy():
    category_rows, wide, coverage = _report_frames()

    report = build_static_daily_report(
        category_rows,
        wide,
        coverage,
        pd.Timestamp("2026-09-10").date(),
        "Commodities",
        "en",
        generated_at=datetime(2026, 9, 11, 9, 15, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert "Commodities Positioning Daily" in report
    assert "Static data snapshot" in report
    assert "Copper" in report
    assert "iFinD Price History" in report
    assert "Institution–retail divergence map" in report
