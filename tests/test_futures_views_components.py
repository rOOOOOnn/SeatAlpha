from datetime import date

from ui.futures_views_components import (
    medium_outlook_frame,
    styled_medium_outlook,
    styled_summary,
    summary_frame,
    views_divergence_figure,
)


def _rows():
    return [
        {
            "sector": "黑色系",
            "scores": {"广发期货": -0.4, "中信期货": 0.0,
                       "国泰海通期货": -0.3, "东证期货": 1.0},
            "dates": {"广发期货": "20260916", "中信期货": "20260915"},
            "carried": {"中信期货": True},
            "average": 0.075, "divergence": 1.4,
            "consistency": "中", "judgement": "中性",
        },
        {
            "sector": "有色金属",
            "scores": {"广发期货": None, "中信期货": 1.0,
                       "国泰海通期货": -0.2, "东证期货": -1.0},
            "dates": {}, "carried": {},
            "average": -0.1, "divergence": 2.0,
            "consistency": "中", "judgement": "中性",
        },
        {"sector": "碳酸锂", "scores": {"广发期货": -1.0},
         "average": -1.0, "divergence": 0.0},
    ]


def test_summary_colors_scores_carry_missing_and_divergence():
    rows = _rows()
    frame = summary_frame(rows)
    assert list(frame.columns)[-4:] == ["板块平均", "多空分歧", "一致性", "综合判断"]
    html = styled_summary(frame, rows).to_html()
    assert "#ffeadc" in html  # negative
    assert "#e4f2df" in html  # positive
    assert "#fff0c7" in html  # carried-forward score
    assert "#edf0f2" in html  # unavailable
    assert "#f9dfe4" in html  # wide dispersion
    assert "0.1" in html


def test_divergence_chart_uses_five_major_sectors_and_source_scores():
    figure = views_divergence_figure(_rows(), date(2026, 9, 16))
    assert "2026-09-16" in figure.layout.title.text
    assert all("碳酸锂" not in trace.y for trace in figure.data)
    ranges = [trace for trace in figure.data if trace.mode == "lines"]
    assert len(ranges) == 2
    assert list(ranges[0].x) == [-0.4, 1.0]
    diamonds = [trace for trace in figure.data if "diamond" == getattr(trace.marker, "symbol", None)]
    assert [trace.x[0] for trace in diamonds] == [0.075, -0.1]
    carried = [trace for trace in figure.data if getattr(trace.marker, "symbol", None) == "circle-open"]
    assert len(carried) == 1
    assert carried[0].customdata[0][1] == "2026-09-15"


def test_medium_outlook_matches_workbook_columns_order_and_color_rules():
    rows = [
        {"commodity": "锌", "sector": "有色金属", "direction": "偏空", "score": -0.6,
         "supply": "供应宽松", "demand": "", "inventory": "", "core_logic": "库存增加",
         "medium_outlook": "偏弱", "last_update": "2026-09-08", "age_days": 8,
         "sources": "广发期货", "field_sources": {
             "supply": {"view_date": "2026-09-10"},
             "core_logic": {"view_date": "2026-09-01"},
         }},
        {"commodity": "焦煤", "sector": "黑色系", "direction": "偏多", "score": 0.7,
         "supply": "减产", "demand": "平稳", "inventory": "低位", "core_logic": "供需偏紧",
         "medium_outlook": "震荡偏强", "last_update": "2026-09-16", "age_days": 0,
         "sources": "中信期货", "field_sources": {}},
    ]
    frame = medium_outlook_frame(rows)
    assert list(frame.columns) == [
        "品种", "供给", "需求", "库存", "核心逻辑", "中期展望", "方向", "更新时间", "数据年龄", "观点来源",
    ]
    assert list(frame["品种"]) == ["焦煤", "锌"]
    assert list(frame["方向"]) == ["偏多 (+0.7)", "偏空 (-0.6)"]
    html = styled_medium_outlook(frame, rows, date(2026, 9, 16)).to_html()
    assert "#d9ead3" in html  # bullish
    assert "#f4cccc" in html  # bearish and 15-day-old source
    assert "#fff2cc" in html  # 6-day-old supply source
    assert "#fce5cd" in html  # 8-day-old summary
