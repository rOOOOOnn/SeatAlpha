from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import DB_PATH, SYMBOL_META
from core.db import is_empty, query
from dashboard_views import (
    BLUE,
    GOLD,
    GRID,
    INK,
    ROSE,
    TEAL,
    build_snapshot,
    key_change_cards,
    panorama_table,
    section_title,
    sector_cards,
)
from i18n import (
    behavior_name,
    instrument_name,
    log_message,
    sector_name,
    signal_name,
    tr,
    update_message,
)
from pipeline.clean import classify_behavior
from pipeline.seed_demo import seed
from pipeline.update import update

st.set_page_config(page_title="SeatAlpha · Futures Positioning Atlas / 机构期货持仓全景", page_icon="◇", layout="wide")
st.markdown("""
<style>
:root{--ink:#17222b;--muted:#73808a;--line:#dfe5e7;--paper:#fff;--wash:#f3f5f5;--blue:#426b88;--gold:#a78331;--teal:#2b7d75;--rose:#b45f6a}
html,body,[class*="css"]{font-family:"Microsoft YaHei","PingFang SC","Noto Sans CJK SC",sans-serif;color:var(--ink)}
.stApp{background:var(--wash)}.block-container{max-width:1540px;padding:2.2rem 2.3rem 5rem}
[data-testid="stSidebar"]{background:#f8f9f9;border-right:1px solid var(--line)}
[data-testid="stSidebar"] .block-container{padding:2rem 1.25rem}.sidebar-brand{padding:.15rem 0 1.4rem;border-bottom:1px solid var(--line);margin-bottom:1.2rem}
.sidebar-brand b{font-size:1.18rem;letter-spacing:.08em}.sidebar-brand span{display:block;color:var(--muted);font-size:.74rem;margin-top:.32rem}
.stButton>button{border-radius:2px;border:1px solid #26333b;background:#26333b;color:#fff;font-weight:700}
.stButton>button:hover{border-color:var(--gold);color:#fff}.stSelectbox label,.stMultiSelect label{font-weight:700;color:#42515b}
[data-baseweb="select"]>div{border-radius:2px!important;background:#fff}.stMultiSelect span[data-baseweb="tag"]{background:#edf1f2;color:#26333b}
.report-head{display:flex;justify-content:space-between;gap:2rem;align-items:flex-start;padding:0 0 1.3rem;border-bottom:2px solid #202b32;margin-bottom:1rem}
.report-kicker{color:var(--gold);font-size:.72rem;font-weight:800;letter-spacing:.13em}.report-head h1{font-size:2.15rem;line-height:1.08;margin:.5rem 0 .35rem;letter-spacing:.02em}
.report-head p{color:var(--muted);margin:0;font-size:.86rem}.report-meta{text-align:right;color:var(--muted);font-size:.73rem;line-height:1.75;white-space:nowrap}.report-meta b{color:var(--ink);font-size:.9rem}
.hero-grid{display:grid;grid-template-columns:repeat(5,1fr);background:#fff;border:1px solid var(--line);margin:1rem 0 1.3rem}
.hero-card{padding:1rem 1.15rem;border-right:1px solid var(--line);min-height:92px}.hero-card:last-child{border-right:0}.hero-card span{font-size:.72rem;color:var(--muted)}
.hero-card b{display:block;font-size:1.42rem;margin:.35rem 0 .2rem}.hero-card small{color:var(--muted);font-size:.68rem}.hero-card.accent{background:#f7f1df;border-top:3px solid var(--gold)}
.section-head{display:flex;align-items:center;border-bottom:1px solid #202b32;padding:1.6rem 0 .7rem;margin-bottom:0}.section-no{font:800 .72rem monospace;color:var(--gold);width:48px}.section-head h2{font-size:1.26rem;margin:0}.section-note{margin-left:auto;color:var(--muted);font-size:.7rem}
.sector-grid{display:grid;grid-template-columns:repeat(2,1fr);background:#fff;border-left:1px solid var(--line)}.sector-card{padding:1rem 1.1rem;border-right:1px solid var(--line);border-bottom:1px solid var(--line);min-height:130px}
.sector-card h3{font-size:1.02rem;margin:0}.sector-card small{color:var(--gold);font-size:.67rem}.sector-values{display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;margin:.65rem 0 .45rem;padding-left:28%}
.sector-values span{font-size:.65rem;color:var(--muted)}.sector-values b{display:block;color:var(--ink);font-size:.82rem;margin-top:.15rem}.direction-scale{position:relative;height:13px;background:#eef1f2;border-radius:8px;margin-left:28%}
.direction-scale i{position:absolute;left:50%;top:0;height:100%;border-left:2px solid #8c969c}.scale-dot{position:absolute;top:2px;width:9px;height:9px;border-radius:50%;border:1px solid #fff;box-shadow:0 0 0 1px #58636a;transform:translateX(-50%)}
.scale-legend{display:flex;gap:1rem;justify-content:flex-end;color:var(--muted);font-size:.61rem;margin-top:.35rem}.scale-legend span:before{content:"";display:inline-block;width:5px;height:5px;border-radius:50%;background:#777;margin-right:4px}
[data-testid="stTabs"]{margin-top:.2rem}[data-baseweb="tab-list"]{gap:1.8rem;border-bottom:1px solid var(--line)}[data-baseweb="tab"]{padding:.7rem .1rem;color:#6f7c84;font-weight:700}[aria-selected="true"]{color:var(--ink)!important}
.signal-summary{display:grid;grid-template-columns:repeat(2,1fr);background:#fff;border:1px solid var(--line)}.signal-box{padding:1rem;border-right:1px solid var(--line);border-bottom:1px solid var(--line)}
.signal-box span{color:var(--muted);font-size:.68rem}.signal-box b{display:block;font-size:1.35rem;margin-top:.25rem}.signal-box.wide{grid-column:span 2}
.panorama{background:#fff;border-left:1px solid var(--line);overflow-x:auto}.pano-head,.pano-row{display:grid;grid-template-columns:150px 190px 95px minmax(190px,1.4fr) 135px 135px 120px;align-items:center;min-width:1050px}
.pano-head{background:#edf1f2;border-bottom:1px solid #25323a;min-height:42px;font-size:.68rem;font-weight:700;color:#42515b}.pano-head span,.pano-row>div{padding:.7rem .85rem}
.pano-row{border-bottom:1px solid var(--line);min-height:86px}.pano-row:hover{background:#faf8f2}.instrument b{display:block;font-size:1rem}.instrument>span{display:block;color:var(--muted);font-size:.65rem;margin-top:.18rem}
.instrument .stale{display:inline-block;color:#8d6330;background:#f6edd9;padding:2px 5px;margin-top:5px}.spark{display:block;width:150px;height:34px}.spark-key{color:var(--muted);font-size:.56rem}
.gross b{font:700 .94rem monospace}.gross span,.consensus span{display:block;color:var(--muted);font-size:.62rem}.ratio-gauge{position:relative;background:#f4e9ea;height:14px;border-radius:9px;margin:0 1rem!important;padding:0!important}
.ratio-gauge i{position:absolute;left:50%;height:14px;border-left:2px solid #7d878d}.ratio-gauge>span{position:absolute;top:2px;width:10px;height:10px;border-radius:50%;background:var(--gold);border:2px solid #fff;box-shadow:0 0 0 1px #78672f;transform:translateX(-50%)}
.ratio-gauge b{position:absolute;right:-1px;top:-22px;font:.73rem monospace}.bar-cell b{display:block;text-align:right;font:.72rem monospace}.microbar{position:relative;height:9px;background:#eef1f2;padding:0!important;margin-bottom:4px}
.microbar i{position:absolute;left:50%;height:100%;border-left:1px solid #9ba4a9}.microbar span{position:absolute;height:100%}.consensus b{font:.85rem monospace;color:var(--teal)}
.change-grid{display:grid;grid-template-columns:repeat(4,1fr);background:#fff;border-left:1px solid var(--line)}.change-card{padding:1rem;border-right:1px solid var(--line);border-bottom:1px solid var(--line);min-height:165px}
.change-card h3{font-size:.94rem;margin:0}.change-card h3 small{font:.65rem monospace;color:var(--muted)}.change-card p{font-size:.64rem;color:var(--muted);padding-bottom:.55rem;border-bottom:1px solid var(--line)}
.change-line{display:grid;grid-template-columns:54px 1fr 54px;align-items:center;gap:.45rem;margin:.48rem 0;font-size:.62rem}.change-line b{text-align:right;font:.68rem monospace}.change-line .microbar{margin:0}
.source-note{margin-top:1rem;padding:.75rem 1rem;border-left:3px solid var(--gold);background:#f7f1df;color:#615b4b;font-size:.68rem}
[data-testid="stMetric"]{background:#fff;border:1px solid var(--line);padding:.8rem 1rem}[data-testid="stMetricLabel"]{color:var(--muted)}
.stDataFrame{border:1px solid var(--line)}.muted{color:var(--muted);font-size:.65rem}
@media(max-width:1000px){.hero-grid{grid-template-columns:repeat(2,1fr)}.sector-grid,.change-grid{grid-template-columns:1fr}.report-meta{display:none}.section-note{display:none}.block-container{padding:1.2rem}.hero-card{border-bottom:1px solid var(--line)}}
</style>
""", unsafe_allow_html=True)

if is_empty(DB_PATH):
    seed(DB_PATH)


@st.cache_data(ttl=60)
def load_data():
    return (
        query("""SELECT m.*, c.source FROM daily_metrics m JOIN contracts c
                 USING (trade_date, exchange, symbol, contract) ORDER BY m.trade_date""", path=DB_PATH),
        query("SELECT * FROM broker_positions ORDER BY trade_date", path=DB_PATH),
        query("SELECT * FROM contracts ORDER BY trade_date", path=DB_PATH),
        query("SELECT * FROM update_log ORDER BY attempted_at DESC", path=DB_PATH),
        query("SELECT * FROM position_history ORDER BY trade_date", path=DB_PATH),
    )


def light_layout(fig: go.Figure, height: int, **kwargs) -> go.Figure:
    fig.update_layout(height=height, paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
                      font={"color": INK, "size": 12}, margin={"l": 50, "r": 35, "t": 45, "b": 45},
                      hoverlabel={"bgcolor": "#ffffff", "font_color": INK}, **kwargs)
    fig.update_xaxes(gridcolor=GRID, zerolinecolor="#8b959b")
    fig.update_yaxes(gridcolor=GRID, zerolinecolor="#8b959b")
    return fig


metrics, positions, contracts, logs, position_history = load_data()
for frame in (metrics, positions, contracts, position_history):
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])

with st.sidebar:
    language_choice = st.radio("Language / 语言", ["中文", "English"], horizontal=True)
    lang = "en" if language_choice == "English" else "zh"
    st.markdown(
        f'<div class="sidebar-brand"><b>◇ SeatAlpha</b><span>{tr(lang, "sidebar_subtitle")}</span></div>',
        unsafe_allow_html=True,
    )
    if st.button(tr(lang, "update"), width="stretch", type="primary"):
        with st.spinner(tr(lang, "updating")):
            st.session_state["last_update_result"] = update(force=False)
        load_data.clear()
        st.rerun()
    real_dates = sorted(metrics.loc[metrics["source"].ne("demo"), "trade_date"].dt.date.unique(), reverse=True)
    selected_date = st.selectbox(tr(lang, "date"), real_dates, index=0) if real_dates else None
    sectors = sorted({meta[1] for meta in SYMBOL_META.values()})
    selected_sectors = st.multiselect(
        tr(lang, "sectors"), sectors, default=sectors, format_func=lambda value: sector_name(value, lang)
    )
    st.caption(tr(lang, "scope_caption"))
    for exchange, message in st.session_state.get("last_update_result", {}).items():
        st.caption(f"{exchange} · {update_message(message, lang)}")

if selected_date is None:
    st.error(tr(lang, "no_real_data"))
    st.stop()

snapshot = build_snapshot(metrics, positions, position_history, selected_date, selected_sectors)
if snapshot.empty:
    st.warning(tr(lang, "no_filter_data"))
    st.stop()

st.markdown(f"""
<div class="report-head">
  <div><span class="report-kicker">INSTITUTIONAL POSITIONING · FUTURES ATLAS</span>
  <h1>{tr(lang, 'report_title')}</h1><p>{tr(lang, 'report_subtitle')}</p></div>
  <div class="report-meta"><b>{selected_date:%Y.%m.%d}</b><br>{tr(lang, 'instrument_basis')}<br>{tr(lang, 'data_source')}</div>
</div>
""", unsafe_allow_html=True)

strongest = snapshot.nlargest(1, "bull_score").iloc[0]
largest_change = snapshot.loc[snapshot["delta_net_1d"].abs().idxmax()]
stale_count = int(snapshot["stale_days"].gt(0).sum())
total_net = float(snapshot["net_position"].sum())
strongest_name = instrument_name(strongest["symbol"], lang, strongest["name"])
strongest_signal = signal_name(strongest["signal"], lang)
st.markdown(f"""
<div class="hero-grid">
  <div class="hero-card"><span>{tr(lang, 'covered')}</span><b>{len(snapshot)} {tr(lang, 'instruments')}</b><small>{snapshot['sector'].nunique()} {tr(lang, 'sector_count')}</small></div>
  <div class="hero-card"><span>{tr(lang, 'total_net')}</span><b>{total_net / 10000:+,.1f} {tr(lang, 'ten_thousand_lots')}</b><small>{tr(lang, 'total_note')}</small></div>
  <div class="hero-card"><span>{tr(lang, 'strongest')}</span><b>{strongest['symbol']}</b><small>{strongest_name} · {strongest_signal}</small></div>
  <div class="hero-card"><span>{tr(lang, 'largest_change')}</span><b>{largest_change['symbol']}</b><small>{largest_change['delta_net_1d'] / 10000:+,.1f} {tr(lang, 'ten_thousand_lots')}</small></div>
  <div class="hero-card accent"><span>{tr(lang, 'freshness')}</span><b>{len(snapshot)-stale_count} / {len(snapshot)}</b><small>{tr(lang, 'current_count')} · {stale_count} {tr(lang, 'stale_count')}</small></div>
</div>
""", unsafe_allow_html=True)

overview_tab, detail_tab, broker_tab, status_tab = st.tabs(
    [tr(lang, "tab_overview"), tr(lang, "tab_detail"), tr(lang, "tab_broker"), tr(lang, "tab_status")]
)

with overview_tab:
    st.markdown(
        section_title("01", tr(lang, "section_sector"), tr(lang, "section_sector_note")),
        unsafe_allow_html=True,
    )
    st.markdown(sector_cards(snapshot, lang), unsafe_allow_html=True)

    st.markdown(
        section_title("02", tr(lang, "section_map"), tr(lang, "section_map_note")),
        unsafe_allow_html=True,
    )
    left, right = st.columns([4.5, 1.25], gap="medium")
    with left:
        chart = snapshot.copy()
        x_label, y_label = tr(lang, "net_strength"), tr(lang, "consistency")
        chart[x_label] = chart["net_position_ratio"] * 100
        chart[y_label] = chart["consensus"] * 100
        chart["display_name"] = [instrument_name(s, lang, n) for s, n in zip(chart["symbol"], chart["name"])]
        chart["sector_label"] = chart["sector"].map(lambda value: sector_name(value, lang))
        chart["signal_label"] = chart["signal"].map(lambda value: signal_name(value, lang))
        signal_colors = {
            signal_name("共同净多", lang): TEAL,
            signal_name("共同净空", lang): ROSE,
            signal_name("机构分歧", lang): BLUE,
        }
        fig = px.scatter(
            chart, x=x_label, y=y_label, size="gross_position", color="signal_label", text="symbol",
            hover_name="display_name", hover_data={"sector_label": True, "gross_position": ":,.0f", "asof_date": True,
                                                     x_label: ":+.1f", y_label: ":+.1f", "signal_label": False},
            color_discrete_map=signal_colors, size_max=52,
        )
        x_max = max(float(chart[x_label].abs().max()) * 1.25, 5)
        y_max = max(float(chart[y_label].abs().max()) * 1.25, 15)
        for x0, x1, y0, y1, color in ((0, x_max, 0, y_max, TEAL), (-x_max, 0, -y_max, 0, ROSE),
                                      (-x_max, 0, 0, y_max, GOLD), (0, x_max, -y_max, 0, BLUE)):
            fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1, fillcolor=color, opacity=.055, line_width=0, layer="below")
        fig.add_hline(y=0, line_dash="dot", line_color="#7b858b")
        fig.add_vline(x=0, line_dash="dot", line_color="#7b858b")
        fig.update_traces(textposition="middle right", marker={"line": {"color": "#ffffff", "width": 1.5}})
        light_layout(fig, 520, legend={"orientation": "h", "y": 1.08, "title": None},
                     xaxis_title=tr(lang, "net_strength_axis"), yaxis_title=tr(lang, "consistency_axis"))
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    with right:
        signal_counts = snapshot["signal"].value_counts()
        st.markdown(f"""<div class="signal-summary">
        <div class="signal-box"><span>{signal_name('共同净多', lang)}</span><b>{signal_counts.get('共同净多', 0)} {tr(lang, 'instruments')}</b></div>
        <div class="signal-box"><span>{signal_name('共同净空', lang)}</span><b>{signal_counts.get('共同净空', 0)} {tr(lang, 'instruments')}</b></div>
        <div class="signal-box wide"><span>{signal_name('机构分歧', lang)}</span><b>{signal_counts.get('机构分歧', 0)} {tr(lang, 'instruments')}</b></div>
        <div class="signal-box wide"><span>{tr(lang, 'max_gross')}</span><b>{snapshot.loc[snapshot['gross_position'].idxmax(),'symbol']} {snapshot['gross_position'].max()/10000:,.1f} {tr(lang, 'ten_thousand_lots')}</b></div>
        </div>""", unsafe_allow_html=True)

    st.markdown(
        section_title("03", tr(lang, "section_panorama"), tr(lang, "section_panorama_note")),
        unsafe_allow_html=True,
    )
    st.markdown(panorama_table(snapshot, position_history, contracts, lang), unsafe_allow_html=True)

    st.markdown(
        section_title("04", tr(lang, "section_changes"), tr(lang, "section_changes_note")),
        unsafe_allow_html=True,
    )
    st.markdown(key_change_cards(snapshot, lang=lang), unsafe_allow_html=True)
    stale_separator = ", " if lang == "en" else "、"
    stale_names = stale_separator.join(
        f"{r.symbol}({r.asof_date:%m-%d})" for r in snapshot[snapshot["stale_days"].gt(0)].itertuples()
    )
    note = tr(lang, "dce_note") if stale_names else tr(lang, "fresh_note")
    separator = "; " if lang == "en" else "。"
    st.markdown(
        f'<div class="source-note">{tr(lang, "data_note")}: {note} {tr(lang, "stale_instruments")}: '
        f'{stale_names or tr(lang, "none")}{separator}{tr(lang, "no_demo_mix")}</div>',
        unsafe_allow_html=True,
    )

with detail_tab:
    symbol = st.selectbox(
        tr(lang, "select_instrument"), snapshot["symbol"].tolist(),
        format_func=lambda s: f"{s} · {instrument_name(s, lang, SYMBOL_META.get(s, (s,))[0])}",
    )
    row = snapshot[snapshot["symbol"].eq(symbol)].iloc[0]
    ph = position_history[(position_history["symbol"].eq(symbol)) & (position_history["trade_date"].dt.date.le(selected_date))].copy()
    ph["priority"] = ph["source"].eq("official-aggregate-via-akshare").astype(int)
    ph = ph.sort_values(["trade_date", "priority"]).drop_duplicates("trade_date", keep="last")
    px_history = contracts[(contracts["symbol"].eq(symbol)) & contracts["source"].ne("demo") & contracts["close"].gt(0)].copy()
    px_history = px_history.sort_values(["trade_date", "open_interest"]).drop_duplicates("trade_date", keep="last")
    a, b, c, d = st.columns(4)
    a.metric(tr(lang, "current_strength"), f"{row['net_position_ratio']:+.1%}")
    b.metric(tr(lang, "top20_net"), f"{row['net_position']:+,.0f} {tr(lang, 'lots')}")
    c.metric(tr(lang, "consistency"), f"{row['consensus']:+.0%}")
    d.metric(tr(lang, "position_date"), f"{row['asof_date']:%Y-%m-%d}")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=px_history["trade_date"], y=px_history["close"], name=tr(lang, "main_close"),
        line={"color": GOLD, "width": 2},
    ))
    mode = "lines+markers" if len(ph) >= 2 else "markers"
    fig.add_trace(go.Scatter(x=ph["trade_date"], y=ph["net_position_ratio"], name=tr(lang, "top20_strength"), mode=mode,
                             yaxis="y2", line={"color": BLUE, "width": 2}, marker={"size": 8}))
    light_layout(fig, 410, legend={"orientation": "h", "y": 1.1}, yaxis={"title": tr(lang, "close")},
                 yaxis2={"title": tr(lang, "net_strength"), "overlaying": "y", "side": "right", "tickformat": ".1%", "showgrid": False})
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    if len(ph) < 2:
        st.info(tr(lang, "one_point"))
    pos = positions[(positions["symbol"].eq(symbol)) & positions["source"].ne("demo") &
                    (positions["trade_date"].dt.date.le(selected_date))].copy()
    if not pos.empty:
        pos = pos[pos["trade_date"].eq(pos["trade_date"].max())]
        pos["net_position"] = pos["long_position"] - pos["short_position"]
        pos["behavior"] = [classify_behavior(a, b) for a, b in zip(pos["long_change"], pos["short_change"])]
        pos["behavior"] = pos["behavior"].map(lambda value: behavior_name(value, lang))
        x, y, z = st.columns(3)
        detail_columns = {
            "broker": "Broker" if lang == "en" else "席位",
            "net_position": tr(lang, "net_position"),
            "long_change": "Long Change" if lang == "en" else "多头增减",
            "short_change": "Short Change" if lang == "en" else "空头增减",
            "behavior": "Behavior" if lang == "en" else "行为",
        }
        with x:
            st.markdown(f"#### {tr(lang, 'net_long_top')}")
            st.dataframe(
                pos.nlargest(8, "net_position")[["broker", "net_position", "long_change"]].rename(columns=detail_columns),
                hide_index=True, width="stretch",
            )
        with y:
            st.markdown(f"#### {tr(lang, 'net_short_top')}")
            st.dataframe(
                pos.nsmallest(8, "net_position")[["broker", "net_position", "short_change"]].rename(columns=detail_columns),
                hide_index=True, width="stretch",
            )
        pos["activity"] = pos["long_change"].abs() + pos["short_change"].abs()
        with z:
            st.markdown(f"#### {tr(lang, 'today_behavior')}")
            st.dataframe(
                pos.nlargest(8, "activity")[["broker", "behavior", "long_change", "short_change"]].rename(columns=detail_columns),
                hide_index=True, width="stretch",
            )

with broker_tab:
    real_positions = positions[(positions["source"].ne("demo")) & (positions["trade_date"].dt.date.le(selected_date))].copy()
    real_positions["latest"] = real_positions.groupby("symbol")["trade_date"].transform("max")
    real_positions = real_positions[real_positions["trade_date"].eq(real_positions["latest"])]
    broker = st.selectbox(tr(lang, "select_broker"), sorted(real_positions["broker"].unique()))
    bp = real_positions[real_positions["broker"].eq(broker)].groupby("symbol", as_index=False).agg(
        long_position=("long_position", "sum"), short_position=("short_position", "sum"),
        long_change=("long_change", "sum"), short_change=("short_change", "sum"))
    bp["net_position"] = bp["long_position"] - bp["short_position"]
    bp["net_change"] = bp["long_change"] - bp["short_change"]
    fig = px.bar(bp.sort_values("net_position"), x="net_position", y="symbol", orientation="h",
                 color_discrete_sequence=[BLUE], text_auto=",.0f",
                 labels={"net_position": tr(lang, "net_position"), "symbol": tr(lang, "instrument")})
    light_layout(fig, max(380, len(bp) * 38), showlegend=False)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    broker_columns = {
        "symbol": tr(lang, "instrument"),
        "long_position": "Long Position" if lang == "en" else "多头持仓",
        "short_position": "Short Position" if lang == "en" else "空头持仓",
        "long_change": "Long Change" if lang == "en" else "多头增减",
        "short_change": "Short Change" if lang == "en" else "空头增减",
        "net_position": tr(lang, "net_position"),
        "net_change": "Net Change" if lang == "en" else "净变化",
    }
    st.dataframe(bp.sort_values("net_position", ascending=False).rename(columns=broker_columns), hide_index=True, width="stretch")

with status_tab:
    st.markdown(
        section_title("DATA", tr(lang, "status_title"), tr(lang, "status_note")),
        unsafe_allow_html=True,
    )
    if logs.empty:
        st.info(tr(lang, "no_logs"))
    else:
        display_logs = logs.copy()
        if lang == "en":
            display_logs["status"] = display_logs["status"].map(
                {"success": "Success", "failed": "Failed", "stale": "Stale"}
            ).fillna(display_logs["status"])
            display_logs["message"] = display_logs["message"].map(lambda value: log_message(value, lang))
        log_columns = {
            "attempted_at": "Attempted At" if lang == "en" else "尝试时间",
            "trade_date": "Trade Date" if lang == "en" else "交易日",
            "exchange": "Exchange" if lang == "en" else "交易所",
            "status": "Status" if lang == "en" else "状态",
            "rows_written": "Rows Written" if lang == "en" else "写入行数",
            "message": "Message" if lang == "en" else "消息",
            "source": "Source" if lang == "en" else "来源",
        }
        display_logs = display_logs.rename(columns=log_columns)
        exchange_column = log_columns["exchange"]
        attempted_column = log_columns["attempted_at"]
        st.dataframe(
            display_logs.sort_values(attempted_column, ascending=False).drop_duplicates(exchange_column),
            hide_index=True, width="stretch",
        )
        with st.expander(tr(lang, "full_logs")):
            st.dataframe(display_logs, hide_index=True, width="stretch")
    coverage = position_history.groupby(["exchange", "source"]).agg(
        first_date=("trade_date", "min"), last_date=("trade_date", "max"), symbols=("symbol", "nunique"), rows=("symbol", "size")).reset_index()
    coverage_columns = {
        "exchange": "Exchange" if lang == "en" else "交易所",
        "source": "Source" if lang == "en" else "来源",
        "first_date": "First Date" if lang == "en" else "最早日期",
        "last_date": "Last Date" if lang == "en" else "最新日期",
        "symbols": "Instruments" if lang == "en" else "品种数",
        "rows": "Rows" if lang == "en" else "行数",
    }
    st.dataframe(coverage.rename(columns=coverage_columns), hide_index=True, width="stretch")
