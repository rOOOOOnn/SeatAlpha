import json
from pathlib import Path

from streamlit.testing.v1 import AppTest
from streamlit.util import calc_hash


def test_top_navigation_renders_separate_localized_pages():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=40).run()
    assert not app.exception
    for language, titles in (
        ("中文", ["品种详情", "席位画像", "数据状态"]),
        ("English", ["Instrument detail", "Broker profile", "Data status"]),
    ):
        app.radio[0].set_value(language).run()
        for route, title in zip(("instrument", "brokers", "data-status"), titles):
            # AppTest.switch_page supports files only; callable pages use the URL hash.
            app._page_hash = calc_hash(route)
            app.run()
            assert not app.exception
            assert [heading.value for heading in app.header] == [title]
            assert not any('class="change-grid"' in item.value for item in app.markdown)

    # Operational status must remain accessible with an empty dashboard filter.
    app.multiselect[0].set_value([]).run()
    assert not app.exception
    assert [heading.value for heading in app.header] == ["Data status"]


def test_instrument_page_lists_every_product_and_keeps_unavailable_products_visible():
    app = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=40
    ).run()
    app._page_hash = calc_hash("instrument")
    app.run()

    instrument_picker = next(item for item in app.selectbox if item.label == "品种")
    assert len(instrument_picker.options) == 90

    instrument_picker.select("LMAF").run()
    assert not app.exception
    assert any("聚乙烯月均价：暂无数据" in item.value for item in app.warning)


def test_overview_maps_default_to_one_sector_instead_of_all_products():
    app = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=40
    ).run()

    sector_picker = next(item for item in app.selectbox if item.label == "图表板块")
    assert sector_picker.value == "黑色"
    assert "全市场（悬浮查看品种）" in sector_picker.options
    assert any("当前图表展示" in item.value for item in app.caption)
    assert any(item.label == "显示全部品种标签" for item in app.toggle)

    first_map = json.loads(app.get("plotly_chart")[0].proto.spec)
    direct_labels = [
        label
        for trace in first_map["data"]
        for label in trace.get("text", [])
        if label
    ]
    assert len(direct_labels) <= 6
    assert any(
        position != "middle right"
        for trace in first_map["data"]
        for position in trace.get("textposition", [])
    )
