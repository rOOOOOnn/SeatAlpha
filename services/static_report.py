from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from dashboard_views import select_sector_leaders
from i18n import instrument_name, source_name
from settings.broker_classification import CATEGORY_LABELS, CATEGORY_ORDER
from ui.copy import cp
from ui.report_components import (
    CATEGORY_COLORS,
    change_column,
    executive_read,
    monitor_cards,
    overview_cards,
    panorama_rows,
    section_header,
    sector_matrix,
)

REPORT_CSS = """
:root{--ink:#19242c;--muted:#74818a;--line:#dfe4e6;--paper:#f4f5f4;--qk:#a78331;--hot:#c36f34;--inst:#315f78;--retail:#8a6670}
*{box-sizing:border-box}html{background:var(--paper)}body{margin:0;color:var(--ink);font-family:Inter,"Microsoft YaHei","PingFang SC",Arial,sans-serif;background:var(--paper)}
.page{max-width:1500px;margin:0 auto;padding:36px 42px 70px}.snapshot-banner{display:flex;justify-content:space-between;gap:20px;align-items:center;background:#f7f1df;border-left:4px solid var(--qk);padding:12px 16px;margin-bottom:22px;font-size:12px}
.snapshot-banner b{font-size:13px}.print-button{border:1px solid #b89a4b;background:#fff;color:var(--ink);padding:8px 13px;border-radius:3px;cursor:pointer}.report-head{display:grid;grid-template-columns:1fr auto;gap:2rem;border-bottom:2px solid var(--ink);padding:0 0 1.5rem;margin-bottom:1.5rem}
.kicker{font:700 .68rem monospace;color:var(--qk);letter-spacing:.14em}.report-head h1{font-size:2.35rem;margin:.45rem 0 .5rem;letter-spacing:-.04em}.report-head p{color:var(--muted);margin:0;font-size:.82rem}.meta{text-align:right;font-size:.7rem;line-height:1.8;color:var(--muted)}.meta b{font:700 .94rem monospace;color:var(--ink)}
.coverage-grid{display:grid;grid-template-columns:repeat(4,1fr);background:#fff;border:1px solid var(--line)}.coverage-card{padding:16px;border-right:1px solid var(--line)}.coverage-card:last-child{border:0}.coverage-card span{display:block;color:var(--muted);font-size:11px}.coverage-card b{display:block;font:700 22px monospace;margin:8px 0 3px}.coverage-card small{color:var(--muted);font-size:10px;line-height:1.5}
.section-head{display:grid;grid-template-columns:42px auto 1fr;align-items:end;gap:.65rem;border-bottom:1px solid var(--ink);padding:2.2rem 0 .75rem;margin-bottom:1rem}.section-head>span{font:700 .66rem monospace;color:var(--qk)}.section-head h2{font-size:1.25rem;margin:0}.section-head p{text-align:right;margin:0;color:var(--muted);font-size:.65rem}
.overview-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));background:#fff;border:1px solid var(--line)}.atlas-card{padding:1rem 1.15rem;border-right:1px solid var(--line);min-height:165px;border-top:3px solid var(--inst)}.atlas-card:last-child{border-right:0}.atlas-card.qian_kun{border-top-color:var(--qk)}.atlas-card.hot_money{border-top-color:var(--hot)}.atlas-card.retail{border-top-color:var(--retail)}.atlas-card.divergence{background:#f7f1df;border-top-color:var(--qk)}
.atlas-card header{display:flex;align-items:center;gap:.5rem;font-size:.75rem}.shape{width:9px;height:9px;background:var(--inst);border-radius:50%}.qian_kun .shape{background:var(--qk);transform:rotate(45deg);border-radius:0}.hot_money .shape{background:var(--hot);border-radius:1px}.retail .shape{background:var(--retail);clip-path:polygon(50% 0,100% 100%,0 100%)}.atlas-card .big{font:700 1.55rem monospace;margin:1rem 0 .05rem}.atlas-card>small{color:var(--muted);font-size:.62rem}.atlas-card .delta{font:700 .82rem monospace;margin:.7rem 0}.atlas-card .delta em{font:400 .6rem sans-serif;color:var(--muted)}.atlas-card footer{display:grid;grid-template-columns:repeat(4,1fr);gap:.3rem;border-top:1px solid var(--line);padding-top:.55rem}.atlas-card footer span{font-size:.58rem;color:var(--muted)}.atlas-card footer b{display:block;font:700 .67rem monospace;color:var(--ink)}
.sector-matrix{border:1px solid var(--line);background:#fff}.sector-row{display:grid;border-bottom:1px solid var(--line);min-height:94px}.sector-row:last-child{border:0}.sector-row h3{font-size:.88rem;margin:0;padding:1.1rem;border-right:1px solid var(--line)}.sector-signal{padding:.75rem 1rem;border-right:1px solid var(--line)}.sector-signal:last-child{border:0}.sector-signal strong{font-size:.62rem}.sector-signal>span.signal{float:right}.sector-signal small{display:block;font:600 .59rem monospace;color:var(--muted);margin-top:.25rem}.signal{font-size:.53rem;padding:.16rem .38rem;border-radius:2px;background:#eef1f2;color:#58656e}.signal.strong_long,.signal.long{background:#e1efeb;color:#20685f}.signal.strong_short,.signal.short{background:#f4e5e6;color:#974d56}
.hbar{height:6px;background:#edf0f1;position:relative;margin:.65rem 0}.hbar i{position:absolute;left:50%;height:100%;border-left:1px solid #929da3}.hbar b{position:absolute;height:100%}.chart-card{background:#fff;border:1px solid var(--line);padding:8px 12px 0;margin-bottom:14px}.chart-note{color:var(--muted);font-size:10px;padding:0 10px 8px}
.instrument-table{background:#fff;border:1px solid var(--line)}.instrument-head,.instrument-row{display:grid}.instrument-head{background:#edf0f1;border-bottom:1px solid var(--line)}.instrument-head span{padding:.55rem .8rem;font-size:.58rem;color:var(--muted)}.instrument-row{border-bottom:1px solid var(--line);min-height:88px}.instrument-row:last-child{border:0}.instrument-id,.tri-cell,.div-score{padding:.75rem .8rem;border-right:1px solid var(--line)}.instrument-id b{display:block;font-size:.78rem}.instrument-id span,.instrument-id small{display:block;color:var(--muted);font-size:.55rem;margin-top:.15rem}.tri-cell{display:grid;grid-template-columns:1fr auto;gap:.2rem}.tri-cell strong{font-size:.55rem;color:var(--muted)}.tri-cell b{font:700 .78rem monospace}.tri-cell span,.tri-cell em{font:500 .58rem monospace;color:var(--muted)}.tri-cell small{grid-column:1/3;width:max-content}.div-score{border:0}.div-score b{font:700 1rem monospace}.div-score span{display:block;font-size:.58rem;color:var(--muted);margin-top:.35rem}
.change-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:1px;background:var(--line);border:1px solid var(--line)}.change-panel{background:#fff;padding:1rem;border-top:3px solid var(--inst)}.change-panel.qian_kun{border-top-color:var(--qk)}.change-panel.hot_money{border-top-color:var(--hot)}.change-panel.retail{border-top-color:var(--retail)}.change-panel h3{font-size:.82rem;margin:0 0 .8rem}.change-rank{border-top:1px solid var(--line);padding:.65rem 0 .25rem}.change-rank h4{font-size:.58rem;color:var(--muted);font-weight:600;margin:0 0 .35rem}.change-rank>small{font-size:.6rem;color:var(--muted)}.change-item{display:grid;grid-template-columns:minmax(76px,28%) minmax(0,1fr) 65px;gap:.5rem;align-items:center;margin:.6rem 0}.change-item b{font-size:.72rem;line-height:1.4;overflow-wrap:break-word}.change-item span{text-align:right;font:.62rem monospace}
.monitor-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--line);border:1px solid var(--line)}.monitor-card{background:#fff;padding:1rem;min-height:85px}.monitor-card span,.monitor-card small{display:block;color:var(--muted);font-size:.6rem}.monitor-card b{display:block;font:.75rem monospace;margin:.65rem 0}.executive-box{background:#f7f1df;border-left:4px solid var(--qk);padding:1rem 1.25rem}.executive-box p{font-size:.75rem;line-height:1.65;margin:.4rem 0}
.status-table{width:100%;border-collapse:collapse;background:#fff;font-size:11px}.status-table th,.status-table td{border:1px solid var(--line);padding:8px;text-align:left}.status-table th{background:#edf0f1;color:var(--muted)}.caveat{font-size:.64rem;color:var(--muted);border-top:1px solid var(--line);padding-top:.8rem;margin-top:1rem;line-height:1.7}.footer{margin-top:28px;text-align:center;color:var(--muted);font-size:10px}
@media(max-width:900px){.page{padding:22px 18px}.coverage-grid{grid-template-columns:repeat(2,1fr)}.overview-grid{grid-template-columns:repeat(2,1fr)}.sector-row{overflow-x:auto}.monitor-grid{grid-template-columns:1fr}.report-head{grid-template-columns:1fr}.meta{text-align:left}.instrument-table{overflow-x:auto}.instrument-head,.instrument-row{min-width:850px}}
@media print{html,body{background:#fff}.page{max-width:none;padding:0}.print-button{display:none}.chart-card,.atlas-card,.change-panel,.instrument-row,.monitor-card{break-inside:avoid}.section-head{break-after:avoid}.snapshot-banner{margin-top:0}}
"""


def _domain(values, *, symmetric: bool = False) -> tuple[float, float]:
    numeric = pd.to_numeric(pd.Series(values), errors="coerce").dropna()
    if numeric.empty:
        return (-1.0, 1.0)
    low, high = min(float(numeric.min()), 0.0), max(float(numeric.max()), 0.0)
    if symmetric:
        extent = max(abs(low), abs(high), 1.0) * 1.15
        return (-extent, extent)
    padding = max((high - low) * 0.1, 1.0)
    return (low - padding, high + padding)


def _project(value: float, low: float, high: float, start: float, end: float) -> float:
    return start + (float(value) - low) / max(high - low, 1e-9) * (end - start)


def _svg_marker(category: str, x: float, y: float, size: float, color: str) -> str:
    if category == "qian_kun":
        points = f"{x},{y-size} {x+size},{y} {x},{y+size} {x-size},{y}"
        return f'<polygon points="{points}" fill="{color}" stroke="#fff" stroke-width="1.5"/>'
    if category == "hot_money":
        return f'<rect x="{x-size*.72:.1f}" y="{y-size*.72:.1f}" width="{size*1.44:.1f}" height="{size*1.44:.1f}" rx="2" fill="{color}" stroke="#fff" stroke-width="1.5"/>'
    if category == "retail":
        points = f"{x},{y-size} {x+size},{y+size*.8} {x-size},{y+size*.8}"
        return f'<polygon points="{points}" fill="{color}" stroke="#fff" stroke-width="1.5"/>'
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{size:.1f}" fill="{color}" stroke="#fff" stroke-width="1.5"/>'


def _svg_grid(
    x_domain: tuple[float, float], y_domain: tuple[float, float],
    x_label: str, y_label: str,
) -> str:
    left, right, top, bottom = 88.0, 1160.0, 58.0, 430.0
    elements = []
    for index in range(5):
        fraction = index / 4
        x = left + (right - left) * fraction
        y = top + (bottom - top) * fraction
        x_value = x_domain[0] + (x_domain[1] - x_domain[0]) * fraction
        y_value = y_domain[1] - (y_domain[1] - y_domain[0]) * fraction
        elements.extend([
            f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{bottom}" stroke="#e5e9ea"/>',
            f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" stroke="#e5e9ea"/>',
            f'<text x="{x:.1f}" y="452" text-anchor="middle" font-size="11" fill="#74818a">{x_value:,.1f}</text>',
            f'<text x="76" y="{y+4:.1f}" text-anchor="end" font-size="11" fill="#74818a">{y_value:,.1f}</text>',
        ])
    if x_domain[0] <= 0 <= x_domain[1]:
        zero_x = _project(0, *x_domain, left, right)
        elements.append(f'<line x1="{zero_x:.1f}" y1="{top}" x2="{zero_x:.1f}" y2="{bottom}" stroke="#8b959b" stroke-dasharray="4 4"/>')
    if y_domain[0] <= 0 <= y_domain[1]:
        zero_y = _project(0, y_domain[1], y_domain[0], top, bottom)
        elements.append(f'<line x1="{left}" y1="{zero_y:.1f}" x2="{right}" y2="{zero_y:.1f}" stroke="#8b959b" stroke-dasharray="4 4"/>')
    elements.extend([
        f'<text x="624" y="482" text-anchor="middle" font-size="13" fill="#19242c">{escape(x_label)}</text>',
        f'<text x="20" y="244" text-anchor="middle" font-size="13" fill="#19242c" transform="rotate(-90 20 244)">{escape(y_label)}</text>',
    ])
    return "".join(elements)


def _consensus_svg(category_rows: pd.DataFrame, categories: list[str], lang: str) -> str:
    x_domain, y_domain = _domain(category_rows["net_change"]), (-100.0, 100.0)
    left, right, top, bottom = 88.0, 1160.0, 58.0, 430.0
    candidates = category_rows[category_rows["broker_category"].isin(categories)].copy()
    candidates["priority"] = candidates["net_change"].abs()
    top_labels = candidates.nlargest(12, "priority")
    label_keys = set(zip(top_labels["symbol"], top_labels["broker_category"]))
    points = []
    legend = []
    offsets = [(11, -10), (11, 18), (-11, -10), (-11, 18)]
    for category_index, category in enumerate(categories):
        block = category_rows[category_rows["broker_category"].eq(category)].copy()
        if block.empty:
            continue
        gross = block["long_position"] + block["short_position"]
        max_gross = max(float(gross.max()), 1.0)
        legend_x = 90 + category_index * 185
        legend.append(_svg_marker(category, legend_x, 24, 7, CATEGORY_COLORS[category]))
        legend.append(f'<text x="{legend_x+14}" y="28" font-size="12" fill="#19242c">{escape(CATEGORY_LABELS[lang][category])}</text>')
        for index, row in enumerate(block.itertuples(index=False)):
            x = _project(row.net_change, *x_domain, left, right)
            y = _project(row.consistency * 100, y_domain[1], y_domain[0], top, bottom)
            size = 5 + 9 * np.sqrt((row.long_position + row.short_position) / max_gross)
            name = instrument_name(row.symbol, lang)
            tooltip = (
                f"{name}｜净仓变化 {row.net_change:+,.0f}｜一致性 {row.consistency:+.0%}｜净持仓 {row.net_position:+,.0f}"
                if lang == "zh" else
                f"{name} | Net change {row.net_change:+,.0f} | Consensus {row.consistency:+.0%} | Net {row.net_position:+,.0f}"
            )
            marker = _svg_marker(category, x, y, size, CATEGORY_COLORS[category])
            label = ""
            if (row.symbol, category) in label_keys:
                dx, dy = offsets[(index + category_index) % len(offsets)]
                anchor = "start" if dx > 0 else "end"
                label = f'<text x="{x+dx:.1f}" y="{y+dy:.1f}" text-anchor="{anchor}" font-size="10" fill="#19242c">{escape(name)}</text>'
            points.append(f"<g><title>{escape(tooltip)}</title>{marker}{label}</g>")
    grid = _svg_grid(
        x_domain, y_domain,
        "净仓变化" if lang == "zh" else "Net change",
        "一致性 (%)" if lang == "zh" else "Consensus (%)",
    )
    aria = "四类席位一致性地图" if lang == "zh" else "Four-category consensus map"
    return f'<svg viewBox="0 0 1200 500" role="img" aria-label="{aria}" style="width:100%;height:auto">{grid}{"".join(legend)}{"".join(points)}</svg>'


def _divergence_svg(wide: pd.DataFrame, lang: str) -> str:
    x_domain = _domain(wide["institution_signal"], symmetric=True)
    y_domain = _domain(wide["retail_signal"], symmetric=True)
    left, right, top, bottom = 88.0, 1160.0, 58.0, 430.0
    label_symbols = set(wide.nlargest(min(8, len(wide)), "divergence_score")["symbol"])
    points = []
    offsets = [(11, -10), (11, 18), (-11, -10), (-11, 18)]
    for index, row in enumerate(wide.itertuples(index=False)):
        x = _project(row.institution_signal, *x_domain, left, right)
        y = _project(row.retail_signal, y_domain[1], y_domain[0], top, bottom)
        foreign = float(row.qian_kun_signal)
        color = "#29756c" if foreign > 0.25 else "#a85d65" if foreign < -0.25 else "#b8b39f"
        size = 7 + min(float(row.divergence_score), 3.0) * 4
        name = instrument_name(row.symbol, lang)
        tooltip = (
            f"{name}｜机构 {row.institution_signal:+.2f}｜散户代理 {row.retail_signal:+.2f}｜外资 {foreign:+.2f}｜分歧 {row.divergence_score:.2f}σ"
            if lang == "zh" else
            f"{name} | Institution {row.institution_signal:+.2f} | Retail proxy {row.retail_signal:+.2f} | Foreign {foreign:+.2f} | Divergence {row.divergence_score:.2f}σ"
        )
        marker = _svg_marker("qian_kun", x, y, size, color)
        label = ""
        if row.symbol in label_symbols:
            dx, dy = offsets[index % len(offsets)]
            anchor = "start" if dx > 0 else "end"
            label = f'<text x="{x+dx:.1f}" y="{y+dy:.1f}" text-anchor="{anchor}" font-size="10" fill="#19242c">{escape(name)}</text>'
        points.append(f"<g><title>{escape(tooltip)}</title>{marker}{label}</g>")
    legend = (
        '<circle cx="95" cy="25" r="6" fill="#29756c"/><text x="108" y="29" font-size="11">外资偏多</text>'
        '<circle cx="200" cy="25" r="6" fill="#a85d65"/><text x="213" y="29" font-size="11">外资偏空</text>'
        if lang == "zh" else
        '<circle cx="95" cy="25" r="6" fill="#29756c"/><text x="108" y="29" font-size="11">Foreign long</text>'
        '<circle cx="220" cy="25" r="6" fill="#a85d65"/><text x="233" y="29" font-size="11">Foreign short</text>'
    )
    grid = _svg_grid(
        x_domain, y_domain,
        "机构信号" if lang == "zh" else "Institution signal",
        "散户代理信号" if lang == "zh" else "Retail proxy signal",
    )
    aria = "核心三方分歧地图" if lang == "zh" else "Core three-way divergence map"
    return f'<svg viewBox="0 0 1200 500" role="img" aria-label="{aria}" style="width:100%;height:auto">{grid}{legend}{"".join(points)}</svg>'


def _coverage_table(coverage: pd.DataFrame, lang: str) -> str:
    unavailable = coverage[coverage["status"].ne("最新")].copy()
    if unavailable.empty:
        return "<p>全部品种的数据均达到当前基准日。</p>" if lang == "zh" else "<p>All instruments match the current benchmark date.</p>"
    rows = []
    for row in unavailable.itertuples(index=False):
        price_date = "—" if pd.isna(row.price_date) else pd.Timestamp(row.price_date).strftime("%Y-%m-%d")
        position_date = "—" if pd.isna(row.position_date) else pd.Timestamp(row.position_date).strftime("%Y-%m-%d")
        rows.append(
            "<tr>"
            f"<td>{escape(instrument_name(row.symbol, lang))}</td>"
            f"<td>{escape(str(row.status))}</td>"
            f"<td>{price_date}</td><td>{position_date}</td>"
            f"<td>{escape(str(row.reason))}</td>"
            "</tr>"
        )
    headings = (
        ("品种", "状态", "行情日期", "席位日期", "原因")
        if lang == "zh" else
        ("Instrument", "Status", "Price date", "Position date", "Reason")
    )
    return (
        '<table class="status-table"><thead><tr>'
        + "".join(f"<th>{heading}</th>" for heading in headings)
        + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def build_static_daily_report(
    category_rows: pd.DataFrame,
    wide: pd.DataFrame,
    coverage: pd.DataFrame,
    selected_date,
    market_label: str,
    lang: str,
    categories: list[str] | tuple[str, ...] = CATEGORY_ORDER,
    updated_at=None,
    generated_at: datetime | None = None,
) -> str:
    """Build a self-contained, offline HTML snapshot of the visible daily report."""
    categories = [category for category in CATEGORY_ORDER if category in categories]
    generated_at = generated_at or datetime.now(ZoneInfo("Asia/Shanghai"))
    report_date = pd.Timestamp(selected_date).strftime("%Y-%m-%d")
    updated_text = "—" if pd.isna(updated_at) else pd.Timestamp(updated_at).strftime("%Y-%m-%d %H:%M")
    generated_text = generated_at.strftime("%Y-%m-%d %H:%M")
    ready_count = int(coverage["status"].eq("最新").sum())
    source_values = sorted({
        source_name(value, lang)
        for column in ("price_source", "position_source")
        if column in coverage
        for value in coverage[column].dropna().unique()
        if str(value).strip()
    })
    source_text = ("、" if lang == "zh" else ", ").join(source_values) or "—"
    map_wide = select_sector_leaders(wide, 2) if len(wide) > 20 else wide.copy()
    map_rows = category_rows[category_rows["symbol"].isin(map_wide["symbol"])]
    core_wide = wide.nlargest(min(20, len(wide)), "divergence_score").copy()

    consensus_html = _consensus_svg(map_rows, categories, lang)
    divergence_html = _divergence_svg(map_wide, lang)
    title = (
        f"{market_label}期货持仓日报" if lang == "zh" and market_label != "国债期货"
        else f"{market_label}持仓日报" if lang == "zh"
        else f"{market_label} Positioning Daily"
    )
    static_label = "静态数据快照" if lang == "zh" else "Static data snapshot"
    snapshot_note = (
        "本文件的数据不会自动更新；如需最新数据，请回到 SeatAlpha 刷新后重新导出。"
        if lang == "zh" else
        "This file does not update automatically. Refresh SeatAlpha and export again for newer data."
    )
    print_label = "打印 / 保存为 PDF" if lang == "zh" else "Print / Save as PDF"
    overview_note = "与导出时页面筛选完全一致" if lang == "zh" else "Matches the filters active at export"
    core_note = "按四类席位分歧程度选取前 20 个品种" if lang == "zh" else "Top 20 instruments by four-category divergence"
    unavailable_count = len(coverage) - ready_count
    summary_lines = executive_read(category_rows, wide, lang)
    executive_html = "".join(f"<p>• {escape(line)}</p>" for line in summary_lines)

    return f"""<!doctype html>
<html lang="{'zh-CN' if lang == 'zh' else 'en'}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)} · {report_date}</title><style>{REPORT_CSS}</style></head>
<body><main class="page">
<div class="snapshot-banner"><div><b>{static_label}</b><br>{snapshot_note}</div><button class="print-button" onclick="window.print()">{print_label}</button></div>
<header class="report-head"><div><span class="kicker">SEATALPHA · FUTURES POSITIONING</span><h1>{escape(title)}</h1><p>{escape(cp(lang, 'tagline'))}</p></div>
<div class="meta"><b>{report_date}</b><br>{'页面数据更新时间' if lang == 'zh' else 'Dashboard data updated'}: {updated_text}<br>{'报告生成时间' if lang == 'zh' else 'Report generated'}: {generated_text}</div></header>
<section class="coverage-grid">
<div class="coverage-card"><span>{'当前市场' if lang == 'zh' else 'Market'}</span><b>{escape(market_label)}</b><small>{overview_note}</small></div>
<div class="coverage-card"><span>{'纳入品种' if lang == 'zh' else 'Instruments'}</span><b>{len(coverage)}</b><small>{'当前筛选范围' if lang == 'zh' else 'Current filtered population'}</small></div>
<div class="coverage-card"><span>{'可计算 / 暂不可计算' if lang == 'zh' else 'Available / unavailable'}</span><b>{ready_count} / {unavailable_count}</b><small>{'以席位与行情基准日判断' if lang == 'zh' else 'Based on ranking and price dates'}</small></div>
<div class="coverage-card"><span>{'数据来源' if lang == 'zh' else 'Data sources'}</span><b>{len(source_values)}</b><small>{escape(source_text)}</small></div>
</section>
{section_header('01', cp(lang, 'overview'), cp(lang, 'overview_note'))}
{overview_cards(category_rows, wide, lang, categories)}
{section_header('02', cp(lang, 'sector'), cp(lang, 'sector_note'))}
{sector_matrix(category_rows, lang, categories)}
{section_header('03', cp(lang, 'map'), cp(lang, 'map_note'))}
<div class="chart-card">{consensus_html}<div class="chart-note">{'品种较多时，每个板块选取两项代表品种；悬浮数据点可查看完整数值。' if lang == 'zh' else 'For larger universes, two representative instruments are selected per sector; hover for exact values.'}</div></div>
{section_header('03B', cp(lang, 'div_map'), cp(lang, 'div_note'))}
<div class="chart-card">{divergence_html}</div>
{section_header('04', cp(lang, 'panorama'), core_note)}
{panorama_rows(core_wide, lang, categories)}
{section_header('05', cp(lang, 'changes'), cp(lang, 'changes_note'))}
<div class="change-grid">{''.join(change_column(category_rows, category, lang) for category in categories)}</div>
{section_header('06', cp(lang, 'monitor'), cp(lang, 'monitor_note'))}
{monitor_cards(wide, lang)}
{section_header('07', cp(lang, 'executive'), cp(lang, 'executive_note'))}
<div class="executive-box">{executive_html}</div>
{section_header('08', '数据覆盖说明' if lang == 'zh' else 'Data coverage', '仅列出未达到当前基准日的品种' if lang == 'zh' else 'Only instruments not matching the benchmark date')}
{_coverage_table(coverage, lang)}
<div class="caveat">{escape(cp(lang, 'data_limit'))}<br>{escape(snapshot_note)}<br>{'数据来源' if lang == 'zh' else 'Sources'}: {escape(source_text)}</div>
<footer class="footer">SeatAlpha · {escape(static_label)} · {report_date}</footer>
</main></body></html>"""
