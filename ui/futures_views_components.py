"""Presentation helpers for the optional futures-company views page."""

from __future__ import annotations

from datetime import date
from math import ceil, floor, isfinite

import pandas as pd
import plotly.graph_objects as go

COMPANIES = ("广发期货", "中信期货", "国泰海通期货", "东证期货")
CHART_SECTORS = ("黑色系", "贵金属", "农产品", "有色金属", "能化板块")
SCORE_COLUMNS = (*COMPANIES, "板块平均")
OUTLOOK_FIELDS = (
    ("commodity", "品种"),
    ("supply", "供给"),
    ("demand", "需求"),
    ("inventory", "库存"),
    ("core_logic", "核心逻辑"),
    ("medium_outlook", "中期展望"),
    ("direction_score", "方向"),
    ("last_update", "更新时间"),
    ("age_days", "数据年龄"),
    ("sources", "观点来源"),
)
OUTLOOK_SECTORS = (*CHART_SECTORS, "碳酸锂", "多晶硅")
_OUTLOOK_SOURCE_FIELDS = {"供给": "supply", "需求": "demand", "库存": "inventory",
                          "核心逻辑": "core_logic", "中期展望": "medium_outlook"}


def medium_outlook_frame(rows: list[dict]) -> pd.DataFrame:
    """Match the source workbook's ten visible columns and sector/item order."""
    sector_rank = {sector: index for index, sector in enumerate(OUTLOOK_SECTORS)}
    ordered = sorted(rows, key=lambda row: (
        sector_rank.get(str(row.get("sector")), 999), str(row.get("commodity") or ""),
    ))
    records = []
    for row in ordered:
        score = row.get("score")
        direction = row.get("direction") or "无数据"
        record = {key: row.get(key) for key, _ in OUTLOOK_FIELDS if key != "direction_score"}
        record["direction_score"] = (
            f"{direction} ({float(score):+.1f})" if score is not None else direction
        )
        records.append({label: record.get(key) for key, label in OUTLOOK_FIELDS})
    return pd.DataFrame(records, columns=[label for _, label in OUTLOOK_FIELDS])


def _age_style(age: int | None) -> str:
    if age is None or age <= 3:
        return ""
    if age <= 7:
        return "background-color:#fff2cc;color:#66520b"
    if age <= 14:
        return "background-color:#fce5cd;color:#77431b"
    return "background-color:#f4cccc;color:#792b2b"


def styled_medium_outlook(frame: pd.DataFrame, rows: list[dict], target: date) -> pd.io.formats.style.Styler:
    """Apply the workbook's field-age and direction-score color semantics."""
    sector_rank = {sector: index for index, sector in enumerate(OUTLOOK_SECTORS)}
    ordered = sorted(rows, key=lambda row: (
        sector_rank.get(str(row.get("sector")), 999), str(row.get("commodity") or ""),
    ))
    styles = pd.DataFrame("", index=frame.index, columns=frame.columns)
    for index, row in enumerate(ordered):
        for label, field in _OUTLOOK_SOURCE_FIELDS.items():
            source_date = ((row.get("field_sources") or {}).get(field) or {}).get("view_date")
            try:
                age = (target - date.fromisoformat(str(source_date))).days if source_date else None
            except ValueError:
                age = None
            styles.loc[index, label] = _age_style(age)
        styles.loc[index, "数据年龄"] = _age_style(row.get("age_days"))
        score = row.get("score")
        if score is not None:
            color = "#d9ead3" if float(score) >= 0.5 else "#f4cccc" if float(score) <= -0.5 else "#fff2cc"
            styles.loc[index, "方向"] = f"background-color:{color};color:#27313b;font-weight:600"
    return frame.style.apply(lambda _: styles, axis=None).format(na_rep="")


def summary_frame(rows: list[dict]) -> pd.DataFrame:
    records = []
    for row in rows:
        records.append({
            "板块": row.get("sector"),
            **{company: (row.get("scores") or {}).get(company) for company in COMPANIES},
            "板块平均": row.get("average"),
            "多空分歧": row.get("divergence"),
            "一致性": row.get("consistency"),
            "综合判断": row.get("judgement"),
        })
    return pd.DataFrame(records)


def styled_summary(frame: pd.DataFrame, rows: list[dict]) -> pd.io.formats.style.Styler:
    """Color cells like the source workbook, with carried scores visibly muted."""
    carried = {
        (index, company): bool((row.get("carried") or {}).get(company))
        for index, row in enumerate(rows)
        for company in COMPANIES
    }

    def cell_style(value: object, row_index: int, column: str) -> str:
        if column in SCORE_COLUMNS:
            if pd.isna(value):
                return "background-color:#edf0f2;color:#697780"
            if carried.get((row_index, column), False):
                return "background-color:#fff0c7;color:#745517"
            if float(value) > 0:
                return "background-color:#e4f2df;color:#245635"
            if float(value) < 0:
                return "background-color:#ffeadc;color:#854329"
            return "background-color:#fff8e5;color:#665820"
        if column == "多空分歧":
            if pd.isna(value):
                return "background-color:#edf0f2;color:#697780"
            if float(value) >= 1.5:
                return "background-color:#f9dfe4;color:#882d48"
            if float(value) <= 1.0:
                return "background-color:#e5f2e0;color:#245635"
            return "background-color:#fff1d7;color:#71551c"
        return ""

    styles = pd.DataFrame("", index=frame.index, columns=frame.columns)
    for index in frame.index:
        for column in frame.columns:
            styles.loc[index, column] = cell_style(frame.loc[index, column], index, column)
    return frame.style.apply(lambda _: styles, axis=None).format(
        {column: "{:.1f}" for column in (*SCORE_COLUMNS, "多空分歧")},
        na_rep="—",
    )


def views_divergence_figure(rows: list[dict], target: date, *, language: str = "zh") -> go.Figure:
    """Show institution scores, their observed range, and the supplied mean."""
    chart_rows = [row for sector in CHART_SECTORS for row in rows if row.get("sector") == sector]
    figure = go.Figure()
    all_scores: list[float] = []
    for row in chart_rows:
        sector = row["sector"]
        points = [
            (company, float(score))
            for company in COMPANIES
            if (score := (row.get("scores") or {}).get(company)) is not None
            and isfinite(float(score))
        ]
        if not points:
            continue
        values = [score for _, score in points]
        all_scores.extend(values)
        figure.add_trace(go.Scatter(
            x=[min(values), max(values)], y=[sector, sector],
            mode="lines", line={"color": "#aeb9c3", "width": 2},
            showlegend=False, hoverinfo="skip",
        ))
        for company, score in points:
            raw_date = (row.get("dates") or {}).get(company) or "—"
            source_date = (
                f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
                if isinstance(raw_date, str) and len(raw_date) == 8 and raw_date.isdigit()
                else raw_date
            )
            carried = bool((row.get("carried") or {}).get(company))
            figure.add_trace(go.Scatter(
                x=[score], y=[sector], mode="markers", name=company,
                marker={"symbol": "circle-open" if carried else "circle", "size": 10,
                        "color": "#66737d", "line": {"width": 2, "color": "#66737d"}},
                showlegend=False,
                customdata=[[company, source_date, "历史沿用" if carried else "当日观点"]],
                hovertemplate=("%{y} · %{customdata[0]}<br>评分 %{x:.2f}<br>"
                               "来源日期 %{customdata[1]} · %{customdata[2]}<extra></extra>"),
            ))
        mean = row.get("average")
        if mean is not None and isfinite(float(mean)):
            mean = float(mean)
            all_scores.append(mean)
            figure.add_trace(go.Scatter(
                x=[mean], y=[sector], mode="markers+text", name="板块平均",
                marker={"symbol": "diamond", "size": 12, "color": "#2868bf"},
                text=[f"{mean:.1f}"], textposition="top center",
                textfont={"color": "#1d4c8c", "size": 12}, showlegend=False,
                hovertemplate="%{y} · 板块平均 %{x:.2f}<extra></extra>",
            ))

    if all_scores:
        lower = floor((min(all_scores) - 0.2) * 2) / 2
        upper = ceil((max(all_scores) + 0.2) * 2) / 2
        figure.update_xaxes(range=[min(lower, 0), max(upper, 0)])
    figure.update_layout(
        title={"text": (f"机构观点与分歧 | {target.isoformat()}" if language == "zh"
                        else f"Institution views and dispersion | {target.isoformat()}"),
               "font": {"size": 17, "color": "#19334c"}},
        height=510, margin={"l": 18, "r": 35, "t": 65, "b": 65},
        paper_bgcolor="white", plot_bgcolor="white", showlegend=False,
        font={"family": "Microsoft YaHei, sans-serif", "color": "#263847"},
    )
    figure.update_xaxes(
        title_text="观点评分（越高越偏多，0 为中性）" if language == "zh" else "View score (higher = more bullish; 0 = neutral)",
        gridcolor="#edf0f2", zeroline=True, zerolinecolor="#8798a5",
        zerolinewidth=1.5, dtick=0.5,
    )
    figure.update_yaxes(
        categoryorder="array", categoryarray=list(reversed(CHART_SECTORS)),
        gridcolor="#f1f3f5", tickfont={"size": 13},
    )
    return figure
