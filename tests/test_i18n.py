from i18n import (
    behavior_name,
    instrument_name,
    sector_name,
    signal_name,
    source_name,
    tr,
    update_message,
)


def test_english_translations_cover_dashboard_entities():
    assert tr("en", "tab_overview") == "Positioning Atlas"
    assert instrument_name("AU", "en", "黄金") == "Gold"
    assert sector_name("贵金属", "en") == "Precious Metals"
    assert signal_name("共同净多", "en") == "Consensus Net Long"
    assert behavior_name("强加多", "en") == "Strong Long Build"
    assert update_message("备用数据 · 截至 2026-08-21", "en") == "Fallback data · as of 2026-08-21"


def test_chinese_mode_preserves_source_labels():
    assert instrument_name("AU", "zh", "黄金") == "黄金"
    assert sector_name("贵金属", "zh") == "贵金属"
    assert signal_name("共同净多", "zh") == "共同净多"


def test_rankings_show_full_instrument_names_in_both_languages():
    import pandas as pd

    from ui.report_components import change_column

    frame = pd.DataFrame([{"symbol": "M", "broker_category": "institution",
                           "long_change": 100, "short_change": 50,
                           "net_change": 50, "consistency": 0.5}])
    assert instrument_name("I", "zh") == "铁矿石"
    assert instrument_name("P", "zh") == "棕榈油"
    assert "<b>豆粕</b>" in change_column(frame, "institution", "zh")
    assert "<b>Soybean Meal</b>" in change_column(frame, "institution", "en")
    assert "<b>M</b>" not in change_column(frame, "institution", "zh")


def test_combined_source_lineage_is_localized():
    value = source_name("price=ifind-http|positions=official-via-akshare", "en")
    assert value == "Price Source: iFinD HTTP · Position Source: Exchange Public Data via AKShare"
