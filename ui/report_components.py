from __future__ import annotations

from html import escape

import pandas as pd

from i18n import instrument_name, sector_name
from services.signal_engine import signal_label
from settings.broker_classification import CATEGORY_LABELS, CATEGORY_ORDER

CATEGORY_COLORS = {
    "qian_kun": "#a78331",
    "hot_money": "#c36f34",
    "institution": "#315f78",
    "retail": "#8a6670",
}
SIGNAL_COPY = {
    "zh": {"strong_long": "强多", "long": "偏多", "neutral": "中性", "short": "偏空", "strong_short": "强空"},
    "en": {"strong_long": "Strong long", "long": "Long", "neutral": "Neutral", "short": "Short", "strong_short": "Strong short"},
}
STATE_COPY = {
    "zh": {"three_long": "核心三方多头共振", "three_short": "核心三方空头共振", "qk_inst_vs_retail": "外资与机构同向、散户反向",
           "qk_retail_vs_inst": "外资与散户同向、机构反向", "inst_retail_vs_qk": "机构与散户同向、外资反向",
           "high_divergence": "核心三方高度分歧", "neutral": "方向中性"},
    "en": {"three_long": "Core three-way long resonance", "three_short": "Core three-way short resonance", "qk_inst_vs_retail": "Foreign + institution vs retail",
           "qk_retail_vs_inst": "Foreign + retail vs institution", "inst_retail_vs_qk": "Institution + retail vs foreign",
           "high_divergence": "High three-way divergence", "neutral": "Neutral"},
}


def section_header(number: str, title: str, note: str) -> str:
    return f'<div class="section-head"><span>{escape(number)}</span><h2>{escape(title)}</h2><p>{escape(note)}</p></div>'


def _fmt_lots(value: float, lang: str) -> str:
    return f"{value / 10_000:+,.1f}{'万' if lang == 'zh' else '×10k'}"


def _bar(value: float, scale: float, color: str) -> str:
    width = min(abs(value) / max(scale, 1) * 48, 48)
    side = "left:50%" if value >= 0 else "right:50%"
    return f'<div class="hbar"><i></i><b style="{side};width:{width:.1f}%;background:{color}"></b></div>'


def overview_cards(
    category_rows: pd.DataFrame, wide: pd.DataFrame, lang: str,
    categories: tuple[str, ...] | list[str] = CATEGORY_ORDER,
) -> str:
    cards = []
    labels = CATEGORY_LABELS[lang]
    for category in categories:
        group = category_rows[category_rows["broker_category"].eq(category)]
        net, change = group["net_position"].sum(), group["net_change"].sum()
        long_count, short_count = int((group["signal_score"] > .25).sum()), int((group["signal_score"] < -.25).sum())
        strongest = group.loc[group["signal_score"].idxmax(), "symbol"] if not group.empty else "—"
        weakest = group.loc[group["signal_score"].idxmin(), "symbol"] if not group.empty else "—"
        strongest = escape(instrument_name(strongest, lang))
        weakest = escape(instrument_name(weakest, lang))
        cards.append(f'''<div class="atlas-card {category}"><header><span class="shape"></span><b>{labels[category]}</b></header>
        <div class="big">{_fmt_lots(net, lang)}</div><small>{'净仓' if lang=='zh' else 'Net position'}</small>
        <div class="delta">{_fmt_lots(change, lang)} <em>{'今日变化' if lang=='zh' else 'Today'}</em></div>
        <footer><span>{'多头' if lang=='zh' else 'Long'} <b>{long_count}</b></span><span>{'空头' if lang=='zh' else 'Short'} <b>{short_count}</b></span><span>{'强' if lang=='zh' else 'High'} <b>{strongest}</b></span><span>{'弱' if lang=='zh' else 'Low'} <b>{weakest}</b></span></footer></div>''')
    if wide.empty:
        divergence = "—"
    else:
        row = wide.loc[wide["divergence_score"].idxmax()]
        divergence = f"{escape(instrument_name(row['symbol'], lang))} · {row['divergence_score']:.2f}σ"
    cards.append(f'''<div class="atlas-card divergence"><header><span class="cross">×</span><b>{'最大分歧' if lang=='zh' else 'Max divergence'}</b></header>
    <div class="big">{divergence}</div><small>{'四类标准化信号最大距离' if lang=='zh' else 'Maximum standardized signal distance across four categories'}</small>
    <div class="delta">{len(wide[wide['divergence_score'].ge(1.5)]) if not wide.empty else 0} <em>{'个高分歧品种' if lang=='zh' else 'high-divergence instruments'}</em></div></div>''')
    return '<div class="overview-grid">' + "".join(cards) + "</div>"


def sector_matrix(
    category_rows: pd.DataFrame, lang: str,
    categories: tuple[str, ...] | list[str] = CATEGORY_ORDER,
) -> str:
    labels = CATEGORY_LABELS[lang]
    scale = max(float(category_rows["net_position"].abs().max()), 1)
    sections = []
    for sector, block in category_rows.groupby("sector", sort=True):
        cells = []
        for category in categories:
            group = block[block["broker_category"].eq(category)]
            net = float(group["net_position"].sum())
            change = float(group["net_change"].sum())
            consistency = float(group["consistency"].mean()) if not group.empty else 0
            score = float(group["signal_score"].mean()) if not group.empty else 0
            signal = SIGNAL_COPY[lang][signal_label(score)]
            cells.append(f'''<div class="sector-signal"><strong>{labels[category]}</strong><span class="signal {signal_label(score)}">{signal}</span>
            {_bar(net, scale, CATEGORY_COLORS[category])}<small>{_fmt_lots(net, lang)} · Δ {_fmt_lots(change, lang)} · {consistency:+.0%}</small></div>''')
        style = f"grid-template-columns:155px repeat({len(categories)},1fr)"
        sections.append(f'<div class="sector-row" style="{style}"><h3>{escape(sector_name(sector, lang))}</h3>{"".join(cells)}</div>')
    return '<div class="sector-matrix">' + "".join(sections) + "</div>"


def panorama_rows(
    wide: pd.DataFrame, lang: str,
    categories: tuple[str, ...] | list[str] = CATEGORY_ORDER,
) -> str:
    labels = CATEGORY_LABELS[lang]
    if wide.empty:
        return ""
    rows = []
    for row in wide.sort_values("divergence_score", ascending=False).itertuples(index=False):
        cells = []
        for category in categories:
            signal = float(getattr(row, f"{category}_signal", 0) or 0)
            cells.append(f'''<div class="tri-cell"><strong>{labels[category]}</strong><b>{_fmt_lots(getattr(row, f'{category}_net_position', 0), lang)}</b>
            <span>Δ {_fmt_lots(getattr(row, f'{category}_net_change', 0), lang)}</span><em>{getattr(row, f'{category}_consistency', 0):+.0%}</em>
            <small class="signal {signal_label(signal)}">{SIGNAL_COPY[lang][signal_label(signal)]}</small></div>''')
        name = instrument_name(row.symbol, lang, row.name)
        state = STATE_COPY[lang].get(row.three_way_state, row.three_way_state)
        instrument_meta = escape(sector_name(row.sector, lang)) if lang == "zh" else f"{row.symbol} · {escape(sector_name(row.sector, lang))}"
        rows.append(f'''<div class="instrument-row"><div class="instrument-id"><b>{escape(name)}</b><span>{instrument_meta}</span><small>{row.price_date:%Y-%m-%d}</small></div>
        {"".join(cells)}<div class="div-score"><b>{row.divergence_score:.2f}</b><span>{state}</span></div></div>''')
    headings = (["品种"] + [CATEGORY_LABELS[lang][c] for c in categories] + ["分歧 / 状态"])
    if lang == "en": headings[0], headings[-1] = "Instrument", "Divergence / state"
    style = f"grid-template-columns:145px repeat({len(categories)},1fr) 165px"
    header = f'<div class="instrument-head" style="{style}">' + "".join(f"<span>{x}</span>" for x in headings) + '</div>'
    body = "".join(row.replace('<div class="instrument-row">', f'<div class="instrument-row" style="{style}">', 1) for row in rows)
    return '<div class="instrument-table">' + header + body + '</div>'


def change_column(category_rows: pd.DataFrame, category: str, lang: str, limit: int = 5) -> str:
    labels = CATEGORY_LABELS[lang]
    block = category_rows[category_rows["broker_category"].eq(category)].copy()
    rankings = [
        ("加多最大" if lang == "zh" else "Largest long additions", "long_change", False),
        ("加空最大" if lang == "zh" else "Largest short additions", "short_change", False),
        ("净仓变化最大" if lang == "zh" else "Largest net changes", "net_change", True),
        # Category consistency history is not persisted yet. Show the current,
        # directly observed breadth instead of inventing a daily change.
        ("当前一致性强度" if lang == "zh" else "Current consensus strength", "consistency", True),
    ]
    sections = []
    for title, metric, absolute in rankings:
        ranked = block.copy()
        if metric in ("long_change", "short_change"):
            ranked = ranked[ranked[metric].gt(0)]
        order = ranked[metric].abs() if absolute else ranked[metric]
        ranked = ranked.reindex(order.sort_values(ascending=False).index).head(limit)
        scale = max(float(ranked[metric].abs().max()), 1e-9) if not ranked.empty else 1
        lines = []
        for row in ranked.itertuples(index=False):
            value = float(getattr(row, metric))
            formatted = f"{value:+.0%}" if metric == "consistency" else _fmt_lots(value, lang)
            lines.append(
                f'<div class="change-item"><b>{escape(instrument_name(row.symbol, lang))}</b>'
                f'{_bar(value, scale, CATEGORY_COLORS[category])}<span>{formatted}</span></div>'
            )
        sections.append(
            f'<div class="change-rank"><h4>{title} · {f"前 {limit} 名" if lang == "zh" else f"Top {limit}"}</h4>'
            f'{"".join(lines) or "<small>—</small>"}</div>'
        )
    return f'<div class="change-panel {category}"><h3>{labels[category]}</h3>{"".join(sections)}</div>'


def monitor_cards(wide: pd.DataFrame, lang: str) -> str:
    cards = []
    for state in ("qk_inst_vs_retail", "qk_retail_vs_inst", "inst_retail_vs_qk", "three_long", "three_short", "high_divergence"):
        symbols = wide.loc[wide["three_way_state"].eq(state)].nlargest(6, "divergence_score")["symbol"].tolist()
        symbols = [escape(instrument_name(symbol, lang)) for symbol in symbols]
        cards.append(f'<div class="monitor-card"><span>{escape(STATE_COPY[lang][state])}</span><b>{" · ".join(symbols) or "—"}</b><small>{len(symbols)} {"个品种" if lang=="zh" else "instruments"}</small></div>')
    return '<div class="monitor-grid">' + "".join(cards) + '</div>'


def executive_read(category_rows: pd.DataFrame, wide: pd.DataFrame, lang: str) -> list[str]:
    if wide.empty:
        return []
    lines = []
    top = wide.nlargest(1, "divergence_score").iloc[0]
    state = STATE_COPY[lang].get(top["three_way_state"], top["three_way_state"])
    top_name = instrument_name(top['symbol'], lang)
    lines.append(f"{top_name} 为当前最大分歧品种（{top['divergence_score']:.2f}σ），结构为“{state}”。"
                  if lang == "zh" else f"{top_name} has the widest current divergence ({top['divergence_score']:.2f}σ): {state}.")
    for category in CATEGORY_ORDER:
        block = category_rows[category_rows["broker_category"].eq(category)]
        if block.empty:
            continue
        leader = block.loc[block["net_change"].abs().idxmax()]
        direction = ("增加净多" if leader["net_change"] > 0 else "增加净空") if lang == "zh" else ("added net longs" if leader["net_change"] > 0 else "added net shorts")
        name = CATEGORY_LABELS[lang][category]
        leader_name = instrument_name(leader['symbol'], lang)
        lines.append(f"{name}席位在 {leader_name} {direction} {_fmt_lots(abs(leader['net_change']), lang)}。" if lang == "zh" else f"{name} seats {direction} in {leader_name} by {_fmt_lots(abs(leader['net_change']), lang)}.")
    resonant = wide[wide["three_way_consensus"].abs().gt(0)]
    if not resonant.empty:
        symbols = ("、" if lang == "zh" else ", ").join(instrument_name(symbol, lang) for symbol in resonant["symbol"].head(5))
        lines.append(f"外资、机构与散户代理同向共振品种包括：{symbols}。" if lang == "zh" else f"Foreign, institution and retail-aligned instruments include {symbols}.")
    return lines[:5]
