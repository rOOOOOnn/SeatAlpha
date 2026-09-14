import json
from pathlib import Path

from streamlit.testing.v1 import AppTest
from streamlit.util import calc_hash


def test_top_navigation_renders_separate_localized_pages():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=40).run()
    assert not app.exception
    for language, titles in (
        ("中文", ["商品品种详情", "商品席位画像", "商品数据状态"]),
        ("English", ["Commodities Instrument detail", "Commodities Broker profile", "Commodities Data status"]),
    ):
        app.radio[0].set_value(language).run()
        for route, title in zip(
            ("commodity-instrument", "commodity-brokers", "commodity-data-status"),
            titles,
        ):
            # AppTest.switch_page supports files only; callable pages use the URL hash.
            app._page_hash = calc_hash(route)
            app.run()
            assert not app.exception
            assert [heading.value for heading in app.header] == [title]
            assert not any('class="change-grid"' in item.value for item in app.markdown)

    # Operational status must remain accessible with an empty dashboard filter.
    app.multiselect[0].set_value([]).run()
    assert not app.exception
    assert [heading.value for heading in app.header] == ["Commodities Data status"]


def test_instrument_page_lists_every_product_and_keeps_unavailable_products_visible():
    app = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=40
    ).run()
    app._page_hash = calc_hash("commodity-instrument")
    app.run()

    instrument_picker = next(item for item in app.selectbox if item.label == "品种")
    assert len(instrument_picker.options) == 82

    instrument_picker.select("LMAF").run()
    assert not app.exception
    assert any("聚乙烯月均价：暂无数据" in item.value for item in app.warning)


def test_financial_market_pages_keep_equity_and_treasury_products_separate():
    app = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=40
    ).run()

    app._page_hash = calc_hash("equity-instrument")
    app.run()
    equity_picker = next(item for item in app.selectbox if item.label == "品种")
    assert set(equity_picker.options) == {
        "沪深300股指", "上证50股指", "中证500股指", "中证1000股指"
    }
    assert [heading.value for heading in app.header] == ["股指品种详情"]

    app._page_hash = calc_hash("treasury-instrument")
    app.run()
    treasury_picker = next(item for item in app.selectbox if item.label == "品种")
    assert set(treasury_picker.options) == {
        "10年期国债", "5年期国债", "2年期国债", "30年期国债"
    }
    assert [heading.value for heading in app.header] == ["国债期货品种详情"]


def test_overview_maps_default_to_sector_leaders_instead_of_all_products():
    app = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=40
    ).run()

    scope_picker = next(item for item in app.segmented_control if item.label == "图表范围")
    assert scope_picker.value == "leaders"
    assert set(scope_picker.options) == {"各板块代表", "单一板块", "全市场"}
    top_n = next(item for item in app.slider if item.label == "每个板块显示品种数")
    assert top_n.value == 2
    assert any("当前图表展示" in item.value for item in app.caption)
    assert any(item.label == "显示全部品种标签" for item in app.toggle)

    first_map = json.loads(app.get("plotly_chart")[0].proto.spec)
    direct_labels = [
        label
        for trace in first_map["data"]
        for label in trace.get("text", [])
        if label
    ]
    assert len(direct_labels) <= 12
    assert any(
        position != "middle right"
        for trace in first_map["data"]
        for position in trace.get("textposition", [])
    )
    download_buttons = app.get("download_button")
    assert len(download_buttons) == 1
    assert "HTML" in download_buttons[0].label


def test_data_status_shows_hot_money_research_notes_in_both_languages():
    app = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=40
    ).run()
    app._page_hash = calc_hash("commodity-data-status")
    app.run()

    note_table = next(
        item.value for item in app.dataframe
        if "市场常关联人物/资金" in item.value.columns
    )
    assert note_table.to_dict("records") == [
        {"席位": "中财期货", "市场常关联人物/资金": "边锡明 / 中财系资金"},
        {"席位": "混沌天成", "市场常关联人物/资金": "葛卫东 / 混沌系"},
        {"席位": "永安期货", "市场常关联人物/资金": "叶庆均 / 敦和、浙江系资金"},
        {"席位": "新湖期货", "市场常关联人物/资金": "浙江产业资本 / 私募资金"},
    ]

    app.radio[0].set_value("English").run()
    english_table = next(
        item.value for item in app.dataframe
        if "Common market association" in item.value.columns
    )
    assert english_table["Seat"].tolist() == ["中财期货", "混沌天成", "永安期货", "新湖期货"]
