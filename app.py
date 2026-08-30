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
from pipeline.clean import classify_behavior
from pipeline.seed_demo import seed
from pipeline.update import update

st.set_page_config(page_title="SeatAlpha · 机构期货持仓全景", page_icon="◇", layout="wide")
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
    st.markdown('<div class="sidebar-brand"><b>◇ SeatAlpha</b><span>机构期货持仓研究终端</span></div>', unsafe_allow_html=True)
    if st.button("↻ 更新公开数据", width="stretch", type="primary"):
        with st.spinner("正在逐所更新与校验…"):
            st.session_state["last_update_result"] = update(force=False)
        load_data.clear()
        st.rerun()
    real_dates = sorted(metrics.loc[metrics["source"].ne("demo"), "trade_date"].dt.date.unique(), reverse=True)
    selected_date = st.selectbox("观察日期", real_dates, index=0) if real_dates else None
    sectors = sorted({meta[1] for meta in SYMBOL_META.values()})
    selected_sectors = st.multiselect("品种板块", sectors, default=sectors)
    st.caption("口径：各品种截至观察日的最新可用 Top20 席位数据。")
    for exchange, message in st.session_state.get("last_update_result", {}).items():
        st.caption(f"{exchange} · {message}")

if selected_date is None:
    st.error("没有真实数据可展示，请先更新公开数据。")
    st.stop()

snapshot = build_snapshot(metrics, positions, position_history, selected_date, selected_sectors)
if snapshot.empty:
    st.warning("当前日期与板块筛选下没有真实席位数据。")
    st.stop()

st.markdown(f"""
<div class="report-head">
  <div><span class="report-kicker">INSTITUTIONAL POSITIONING · FUTURES ATLAS</span>
  <h1>机构期货持仓全景</h1><p>Top20 净仓、席位一致性与关键变化的结构化扫描</p></div>
  <div class="report-meta"><b>{selected_date:%Y.%m.%d}</b><br>品种口径：各自最新可用交易日<br>数据源：交易所公开数据 / 合规备用源</div>
</div>
""", unsafe_allow_html=True)

strongest = snapshot.nlargest(1, "bull_score").iloc[0]
largest_change = snapshot.loc[snapshot["delta_net_1d"].abs().idxmax()]
stale_count = int(snapshot["stale_days"].gt(0).sum())
total_net = float(snapshot["net_position"].sum())
st.markdown(f"""
<div class="hero-grid">
  <div class="hero-card"><span>覆盖品种</span><b>{len(snapshot)} 个</b><small>{snapshot['sector'].nunique()} 个板块</small></div>
  <div class="hero-card"><span>Top20 合计净仓</span><b>{total_net / 10000:+,.1f} 万手</b><small>跨品种直接加总，仅作方向观察</small></div>
  <div class="hero-card"><span>最强综合信号</span><b>{strongest['symbol']}</b><small>{strongest['name']} · {strongest['signal']}</small></div>
  <div class="hero-card"><span>最大单日变化</span><b>{largest_change['symbol']}</b><small>{largest_change['delta_net_1d'] / 10000:+,.1f} 万手</small></div>
  <div class="hero-card accent"><span>数据新鲜度</span><b>{len(snapshot)-stale_count} / {len(snapshot)}</b><small>当日品种 · {stale_count} 个滞后</small></div>
</div>
""", unsafe_allow_html=True)

overview_tab, detail_tab, broker_tab, status_tab = st.tabs(["全景日报", "品种详情", "席位画像", "数据状态"])

with overview_tab:
    st.markdown(section_title("01", "分类方向速览", "按板块汇总净仓强度、净仓变化和席位一致性"), unsafe_allow_html=True)
    st.markdown(sector_cards(snapshot), unsafe_allow_html=True)

    st.markdown(section_title("02", "机构一致性地图", "横轴为 Top20 净仓强度，纵轴为席位方向一致性；气泡为持仓体量"), unsafe_allow_html=True)
    left, right = st.columns([4.5, 1.25], gap="medium")
    with left:
        chart = snapshot.copy()
        chart["净仓强度"] = chart["net_position_ratio"] * 100
        chart["席位一致性"] = chart["consensus"] * 100
        fig = px.scatter(chart, x="净仓强度", y="席位一致性", size="gross_position", color="signal", text="symbol",
                         hover_name="name", hover_data={"sector": True, "gross_position": ":,.0f", "asof_date": True,
                                                        "净仓强度": ":+.1f", "席位一致性": ":+.1f"},
                         color_discrete_map={"共同净多": TEAL, "共同净空": ROSE, "机构分歧": BLUE}, size_max=52)
        x_max = max(float(chart["净仓强度"].abs().max()) * 1.25, 5)
        y_max = max(float(chart["席位一致性"].abs().max()) * 1.25, 15)
        for x0, x1, y0, y1, color in ((0, x_max, 0, y_max, TEAL), (-x_max, 0, -y_max, 0, ROSE),
                                      (-x_max, 0, 0, y_max, GOLD), (0, x_max, -y_max, 0, BLUE)):
            fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1, fillcolor=color, opacity=.055, line_width=0, layer="below")
        fig.add_hline(y=0, line_dash="dot", line_color="#7b858b")
        fig.add_vline(x=0, line_dash="dot", line_color="#7b858b")
        fig.update_traces(textposition="middle right", marker={"line": {"color": "#ffffff", "width": 1.5}})
        light_layout(fig, 520, legend={"orientation": "h", "y": 1.08, "title": None},
                     xaxis_title="Top20 净持仓强度（%）", yaxis_title="席位一致性（%）")
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    with right:
        signal_counts = snapshot["signal"].value_counts()
        st.markdown(f"""<div class="signal-summary">
        <div class="signal-box"><span>共同净多</span><b>{signal_counts.get('共同净多', 0)} 个</b></div>
        <div class="signal-box"><span>共同净空</span><b>{signal_counts.get('共同净空', 0)} 个</b></div>
        <div class="signal-box wide"><span>机构分歧</span><b>{signal_counts.get('机构分歧', 0)} 个</b></div>
        <div class="signal-box wide"><span>最大持仓体量</span><b>{snapshot.loc[snapshot['gross_position'].idxmax(),'symbol']} {snapshot['gross_position'].max()/10000:,.1f} 万手</b></div>
        </div>""", unsafe_allow_html=True)

    st.markdown(section_title("03", "核心品种全景", "蓝线为净仓强度，金线为价格；数值单位为手，按综合信号排序"), unsafe_allow_html=True)
    st.markdown(panorama_table(snapshot, position_history, contracts), unsafe_allow_html=True)

    st.markdown(section_title("04", "今日关键变化", "按席位净变化绝对值筛选，展示多头、空头与净变化"), unsafe_allow_html=True)
    st.markdown(key_change_cards(snapshot), unsafe_allow_html=True)
    stale_names = "、".join(f"{r.symbol}({r.asof_date:%m-%d})" for r in snapshot[snapshot["stale_days"].gt(0)].itertuples())
    note = "大商所官方旧下载接口异常，DCE 使用备用源并保留真实数据日期。" if stale_names else "所有品种席位数据均为观察日当日。"
    st.markdown(f'<div class="source-note">数据说明：{note} 滞后品种：{stale_names or "无"}。不与演示数据拼接。</div>', unsafe_allow_html=True)

with detail_tab:
    symbol = st.selectbox("选择品种", snapshot["symbol"].tolist(), format_func=lambda s: f"{s} · {SYMBOL_META.get(s, (s,))[0]}")
    row = snapshot[snapshot["symbol"].eq(symbol)].iloc[0]
    ph = position_history[(position_history["symbol"].eq(symbol)) & (position_history["trade_date"].dt.date.le(selected_date))].copy()
    ph["priority"] = ph["source"].eq("official-aggregate-via-akshare").astype(int)
    ph = ph.sort_values(["trade_date", "priority"]).drop_duplicates("trade_date", keep="last")
    px_history = contracts[(contracts["symbol"].eq(symbol)) & contracts["source"].ne("demo") & contracts["close"].gt(0)].copy()
    px_history = px_history.sort_values(["trade_date", "open_interest"]).drop_duplicates("trade_date", keep="last")
    a, b, c, d = st.columns(4)
    a.metric("当前净仓强度", f"{row['net_position_ratio']:+.1%}")
    b.metric("Top20 净持仓", f"{row['net_position']:+,.0f} 手")
    c.metric("席位一致性", f"{row['consensus']:+.0%}")
    d.metric("席位数据日期", f"{row['asof_date']:%Y-%m-%d}")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=px_history["trade_date"], y=px_history["close"], name="主力收盘价", line={"color": GOLD, "width": 2}))
    mode = "lines+markers" if len(ph) >= 2 else "markers"
    fig.add_trace(go.Scatter(x=ph["trade_date"], y=ph["net_position_ratio"], name="Top20 净仓强度", mode=mode,
                             yaxis="y2", line={"color": BLUE, "width": 2}, marker={"size": 8}))
    light_layout(fig, 410, legend={"orientation": "h", "y": 1.1}, yaxis={"title": "收盘价"},
                 yaxis2={"title": "净仓强度", "overlaying": "y", "side": "right", "tickformat": ".1%", "showgrid": False})
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    if len(ph) < 2:
        st.info("该品种目前只有一个真实席位历史点，因此用指标和散点展示，不绘制虚假趋势线。")
    pos = positions[(positions["symbol"].eq(symbol)) & positions["source"].ne("demo") &
                    (positions["trade_date"].dt.date.le(selected_date))].copy()
    if not pos.empty:
        pos = pos[pos["trade_date"].eq(pos["trade_date"].max())]
        pos["net_position"] = pos["long_position"] - pos["short_position"]
        pos["behavior"] = [classify_behavior(a, b) for a, b in zip(pos["long_change"], pos["short_change"])]
        x, y, z = st.columns(3)
        x.dataframe(pos.nlargest(8, "net_position")[["broker", "net_position", "long_change"]], hide_index=True, width="stretch")
        y.dataframe(pos.nsmallest(8, "net_position")[["broker", "net_position", "short_change"]], hide_index=True, width="stretch")
        pos["activity"] = pos["long_change"].abs() + pos["short_change"].abs()
        z.dataframe(pos.nlargest(8, "activity")[["broker", "behavior", "long_change", "short_change"]], hide_index=True, width="stretch")

with broker_tab:
    real_positions = positions[(positions["source"].ne("demo")) & (positions["trade_date"].dt.date.le(selected_date))].copy()
    real_positions["latest"] = real_positions.groupby("symbol")["trade_date"].transform("max")
    real_positions = real_positions[real_positions["trade_date"].eq(real_positions["latest"])]
    broker = st.selectbox("选择席位", sorted(real_positions["broker"].unique()))
    bp = real_positions[real_positions["broker"].eq(broker)].groupby("symbol", as_index=False).agg(
        long_position=("long_position", "sum"), short_position=("short_position", "sum"),
        long_change=("long_change", "sum"), short_change=("short_change", "sum"))
    bp["net_position"] = bp["long_position"] - bp["short_position"]
    bp["net_change"] = bp["long_change"] - bp["short_change"]
    fig = px.bar(bp.sort_values("net_position"), x="net_position", y="symbol", orientation="h",
                 color_discrete_sequence=[BLUE], text_auto=",.0f", labels={"net_position": "净持仓", "symbol": "品种"})
    light_layout(fig, max(380, len(bp) * 38), showlegend=False)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.dataframe(bp.sort_values("net_position", ascending=False), hide_index=True, width="stretch")

with status_tab:
    st.markdown(section_title("DATA", "数据血缘与更新状态", "逐交易所隔离更新，失败不会阻塞其他市场"), unsafe_allow_html=True)
    if logs.empty:
        st.info("尚无更新日志。")
    else:
        st.dataframe(logs.sort_values("attempted_at", ascending=False).drop_duplicates("exchange"), hide_index=True, width="stretch")
        with st.expander("完整更新日志"):
            st.dataframe(logs, hide_index=True, width="stretch")
    coverage = position_history.groupby(["exchange", "source"]).agg(
        first_date=("trade_date", "min"), last_date=("trade_date", "max"), symbols=("symbol", "nunique"), rows=("symbol", "size")).reset_index()
    st.dataframe(coverage, hide_index=True, width="stretch")
