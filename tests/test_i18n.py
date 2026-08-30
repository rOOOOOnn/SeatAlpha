from i18n import (
    behavior_name,
    instrument_name,
    sector_name,
    signal_name,
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
