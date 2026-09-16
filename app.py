from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import DB_PATH, EXCHANGES, ROOT, SYMBOL_META
from core.db import is_empty, query
from dashboard_views import (
    broker_profile_rows,
    build_broker_profiles,
    build_snapshot,
    select_sector_leaders,
)
from i18n import instrument_name, log_message, sector_name, source_name
from pipeline.seed_demo import seed
from pipeline.update import latest_weekday, update
from services.broker_classifier import classify_broker, enrich_broker_classification
from services.data_status import build_current_coverage, historical_source_coverage
from services.futures_views import (
    available_view_dates,
    load_futures_view_bundle,
    load_futures_view_settings,
    update_futures_views,
)
from services.position_aggregator import build_three_category_snapshot
from services.static_report import build_static_daily_report
from settings.broker_classification import (
    CATEGORY_LABELS,
    CATEGORY_ORDER,
    SEAT_CLASSIFICATION,
    SEAT_RESEARCH_NOTES,
)
from settings.signal_thresholds import SIGNAL_THRESHOLDS
from ui.copy import cp
from ui.report_components import (
    CATEGORY_COLORS,
    change_column,
    executive_read,
    monitor_cards,
    metric_quick_guide,
    overview_cards,
    panorama_rows,
    section_header,
    sector_matrix,
)

st.set_page_config(page_title="SeatAlpha", page_icon="◇", layout="wide", initial_sidebar_state="expanded")

EXCHANGE_NAMES_ZH = {
    "SHFE": "上期所及上期能源",
    "DCE": "大商所",
    "CZCE": "郑商所",
    "GFEX": "广期所",
    "CFFEX": "中金所",
}

MARKET_SYMBOLS = {
    "commodity": tuple(symbol for symbol, meta in SYMBOL_META.items() if meta[2] != "CFFEX"),
    "equity": ("IF", "IH", "IC", "IM"),
    "treasury": ("T", "TF", "TS", "TL"),
}
MARKET_LABELS = {
    "zh": {"commodity": "商品", "equity": "股指", "treasury": "国债期货"},
    "en": {"commodity": "Commodities", "equity": "Equity Index", "treasury": "Treasury Futures"},
}

st.markdown("""
<style>
:root{--ink:#19242c;--muted:#74818a;--line:#dfe4e6;--paper:#f4f5f4;--qk:#a78331;--hot:#c36f34;--inst:#315f78;--retail:#8a6670}
html,body,[class*="css"]{font-family:Inter,"Microsoft YaHei",sans-serif;color:var(--ink)}
.stApp,.stApp p,.stApp span,.stApp label,.stApp h1,.stApp h2,.stApp h3{color:var(--ink)}
.stApp{background:var(--paper)}.block-container{max-width:1740px;padding:2.1rem 2.7rem 5rem}
[data-testid="stSidebar"]{width:285px!important;background:#f8f9f8;border-right:1px solid var(--line)}
[data-testid="stSidebar"] .block-container{padding:1.7rem 1.25rem}.sidebar-brand{border-bottom:1px solid var(--line);padding:.5rem 0 1.1rem;margin-bottom:1rem}
.sidebar-brand b{font:700 1.18rem monospace;letter-spacing:.06em}.sidebar-brand span{display:block;color:var(--muted);font-size:.7rem;margin-top:.35rem}
.report-head{display:grid;grid-template-columns:1fr auto;gap:2rem;border-bottom:2px solid var(--ink);padding:0 0 1.5rem;margin-bottom:1.5rem}
.kicker{font:700 .64rem monospace;color:var(--qk);letter-spacing:.14em}.report-head h1{font-size:2.35rem;margin:.45rem 0 .5rem;letter-spacing:-.04em}.report-head p{color:var(--muted);margin:0;font-size:.82rem}
.meta{text-align:right;font-size:.68rem;line-height:1.75;color:var(--muted)}.meta b{font:700 .9rem monospace;color:var(--ink)}
.section-head{display:grid;grid-template-columns:42px auto 1fr;align-items:end;gap:.65rem;border-bottom:1px solid var(--ink);padding:2.2rem 0 .75rem;margin-bottom:1rem}
.section-head>span{font:700 .66rem monospace;color:var(--qk)}.section-head h2{font-size:1.25rem;margin:0}.section-head p{text-align:right;margin:0;color:var(--muted);font-size:.65rem}
.metric-help{color:inherit!important;text-decoration:none;border-bottom:1px dotted #9aa3a8}.metric-help sup{color:var(--qk);font-weight:700}
.quick-guide{background:#fff;border:1px solid var(--line);border-left:3px solid var(--qk);padding:.75rem 1rem;margin:0 0 .85rem;font-size:.69rem;line-height:1.75;color:#46545d}
.formula-box{background:#fff;border:1px solid var(--line);padding:1.1rem 1.3rem;line-height:1.75;font-size:.78rem}.formula-box code{color:#704f12}.formula-box h4{margin:.7rem 0 .2rem}.formula-box p{margin:.15rem 0;color:#46545d}
.overview-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));background:#fff;border:1px solid var(--line)}
.atlas-card{padding:1rem 1.15rem;border-right:1px solid var(--line);min-height:165px;border-top:3px solid var(--inst)}.atlas-card:last-child{border-right:0}
.atlas-card.qian_kun{border-top-color:var(--qk)}.atlas-card.hot_money{border-top-color:var(--hot)}.atlas-card.retail{border-top-color:var(--retail)}.atlas-card.divergence{background:#f7f1df;border-top-color:var(--qk)}
.atlas-card header{display:flex;align-items:center;gap:.5rem;font-size:.75rem}.shape{width:9px;height:9px;background:var(--inst);border-radius:50%}.qian_kun .shape{background:var(--qk);transform:rotate(45deg);border-radius:0}.hot_money .shape{background:var(--hot);border-radius:1px}.retail .shape{background:var(--retail);clip-path:polygon(50% 0,100% 100%,0 100%)}
.atlas-card .big{font:700 1.55rem monospace;margin:1rem 0 .05rem}.atlas-card>small{color:var(--muted);font-size:.62rem}.atlas-card .delta{font:700 .82rem monospace;margin:.7rem 0}.atlas-card .delta em{font:400 .6rem sans-serif;color:var(--muted)}
.atlas-card footer{display:grid;grid-template-columns:repeat(4,1fr);gap:.3rem;border-top:1px solid var(--line);padding-top:.55rem}.atlas-card footer span{font-size:.58rem;color:var(--muted)}.atlas-card footer b{display:block;font:700 .67rem monospace;color:var(--ink)}
.sector-matrix{border:1px solid var(--line);background:#fff}.sector-row{display:grid;grid-template-columns:155px repeat(3,1fr);border-bottom:1px solid var(--line);min-height:94px}.sector-row:last-child{border:0}.sector-row h3{font-size:.88rem;margin:0;padding:1.1rem;border-right:1px solid var(--line)}
.sector-signal{padding:.75rem 1rem;border-right:1px solid var(--line)}.sector-signal:last-child{border:0}.sector-signal strong{font-size:.62rem}.sector-signal>span.signal{float:right}.sector-signal small{display:block;font:600 .59rem monospace;color:var(--muted);margin-top:.25rem}
.signal{font-size:.53rem;padding:.16rem .38rem;border-radius:2px;background:#eef1f2;color:#58656e}.signal.strong_long,.signal.long{background:#e1efeb;color:#20685f}.signal.strong_short,.signal.short{background:#f4e5e6;color:#974d56}
.hbar{height:6px;background:#edf0f1;position:relative;margin:.65rem 0}.hbar i{position:absolute;left:50%;height:100%;border-left:1px solid #929da3}.hbar b{position:absolute;height:100%}
.instrument-table{background:#fff;border:1px solid var(--line)}.instrument-head,.instrument-row{display:grid;grid-template-columns:145px repeat(3,1fr) 165px}.instrument-head{background:#edf0f1;border-bottom:1px solid var(--line)}.instrument-head span{padding:.55rem .8rem;font-size:.58rem;color:var(--muted)}
.instrument-row{border-bottom:1px solid var(--line);min-height:88px}.instrument-row:last-child{border:0}.instrument-id,.tri-cell,.div-score{padding:.75rem .8rem;border-right:1px solid var(--line)}.instrument-id b{display:block;font-size:.78rem}.instrument-id span,.instrument-id small{display:block;color:var(--muted);font-size:.55rem;margin-top:.15rem}
.tri-cell{display:grid;grid-template-columns:1fr auto;gap:.2rem}.tri-cell strong{font-size:.55rem;color:var(--muted)}.tri-cell b{font:700 .78rem monospace}.tri-cell span,.tri-cell em{font:500 .58rem monospace;color:var(--muted)}.tri-cell .tri-bar{grid-column:1/3}.tri-cell .tri-bar .hbar{margin:.22rem 0 .32rem}.tri-cell small{grid-column:1/3;width:max-content}.div-score{border:0}.div-score b{font:700 1rem monospace}.div-score span{display:block;font-size:.58rem;color:var(--muted);margin-top:.35rem}
.change-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:1px;background:var(--line);border:1px solid var(--line)}.change-panel{background:#fff;padding:1rem;border-top:3px solid var(--inst)}.change-panel.qian_kun{border-top-color:var(--qk)}.change-panel.hot_money{border-top-color:var(--hot)}.change-panel.retail{border-top-color:var(--retail)}.change-panel h3{font-size:.82rem;margin:0 0 .8rem}
.change-rank{border-top:1px solid var(--line);padding:.65rem 0 .25rem}.change-rank h4{font-size:.58rem;color:var(--muted);font-weight:600;margin:0 0 .35rem}.change-rank>small{font-size:.6rem;color:var(--muted)}
.change-item{display:grid;grid-template-columns:minmax(76px,28%) minmax(0,1fr) 65px;gap:.5rem;align-items:center;margin:.6rem 0}.change-item b{font-size:.78rem;line-height:1.4;overflow-wrap:break-word}.change-item span{text-align:right;font:.62rem monospace}
.monitor-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--line);border:1px solid var(--line)}.monitor-card{background:#fff;padding:1rem;min-height:85px}.monitor-card span,.monitor-card small{display:block;color:var(--muted);font-size:.6rem}.monitor-card b{display:block;font:.82rem monospace;margin:.65rem 0}
.executive-box{background:#f7f1df;border-left:4px solid var(--qk);padding:1rem 1.25rem}.executive-box p{font-size:.72rem;line-height:1.65;margin:.4rem 0}.caveat{font-size:.63rem;color:var(--muted);border-top:1px solid var(--line);padding-top:.75rem;margin-top:1rem}
[data-testid="stMetric"]{background:#fff;border:1px solid var(--line);padding:.7rem}.stDataFrame{border:1px solid var(--line)}
[data-testid="stToolbar"]{display:flex!important}
[data-testid="stAppDeployButton"],[data-testid="stMainMenu"],[data-testid="stDecoration"],[data-testid="stStatusWidget"]{display:none!important}
@media(max-width:1100px){.overview-grid{grid-template-columns:repeat(2,1fr)}.sector-row{grid-template-columns:110px repeat(3,1fr)}.instrument-head,.instrument-row{grid-template-columns:110px repeat(3,1fr) 130px}.block-container{padding:1.3rem}.report-head{grid-template-columns:1fr}.meta{display:none}}
</style>
""", unsafe_allow_html=True)


def radial_text_positions(x_values, y_values) -> list[str]:
    """Place labels around their points, pointing away from the chart centre."""
    x = np.asarray(x_values, dtype=float)
    y = np.asarray(y_values, dtype=float)
    if not len(x):
        return []
    x_scale = max(float(np.nanmax(x) - np.nanmin(x)), 1.0)
    y_scale = max(float(np.nanmax(y) - np.nanmin(y)), 1.0)
    x_norm = (x - float(np.nanmedian(x))) / x_scale
    y_norm = (y - float(np.nanmedian(y))) / y_scale
    directions = (
        "middle right", "top right", "top center", "top left",
        "middle left", "bottom left", "bottom center", "bottom right",
    )
    positions: list[str] = []
    for index, (x_point, y_point) in enumerate(zip(x_norm, y_norm)):
        # Use eight directions around the marker. A deterministic nudge prevents
        # coincident/near-centre points from all choosing the same side.
        if abs(x_point) + abs(y_point) < 0.08:
            sector = index % len(directions)
        else:
            angle = np.arctan2(y_point, x_point)
            sector = int(np.floor((angle + np.pi / 8) / (np.pi / 4))) % 8
        positions.append(directions[sector])
    return positions

if is_empty(DB_PATH):
    seed(DB_PATH)


@st.cache_data(ttl=60)
def load_data():
    metrics = query("""
        WITH ps AS (SELECT trade_date, exchange, symbol, contract, max(source) AS source
        FROM broker_positions GROUP BY trade_date, exchange, symbol, contract)
        SELECT m.*, ps.source, c.source price_source FROM daily_metrics m
        JOIN contracts c USING (trade_date, exchange, symbol, contract)
        JOIN ps USING (trade_date, exchange, symbol, contract) ORDER BY m.trade_date
    """, path=DB_PATH)
    return (metrics, query("SELECT * FROM broker_positions ORDER BY trade_date", path=DB_PATH),
            query("SELECT * FROM contracts ORDER BY trade_date", path=DB_PATH),
            query("SELECT * FROM update_log ORDER BY attempted_at DESC", path=DB_PATH),
            query("SELECT * FROM position_history ORDER BY trade_date", path=DB_PATH))


def source_refresh_is_current(target) -> bool:
    """Return whether every exchange completed its daily catalogue refresh."""
    completed = query(
        """SELECT DISTINCT exchange FROM update_log
        WHERE trade_date=? AND status IN ('success', 'partial')
        AND message LIKE '%全品种目录%'""",
        [target],
        DB_PATH,
    )
    return set(completed["exchange"]) >= set(EXCHANGES)


# A browser reload creates a new Streamlit session. Always invalidate the local
# read cache, then contact sources only when the latest publishable partition is
# not already complete. Navigation/widget reruns must not trigger API storms.
if not st.session_state.get("startup_refresh_done"):
    st.session_state["startup_refresh_done"] = True
    load_data.clear()
    startup_target = latest_weekday()
    if not source_refresh_is_current(startup_target):
        try:
            with st.spinner("正在检查并获取最新交易日数据…"):
                st.session_state["last_update_result"] = update(
                    startup_target, force=False, backfill_history=False
                )
        except Exception as exc:  # noqa: BLE001 - keep the last valid local snapshot visible.
            st.session_state["startup_refresh_error"] = str(exc)
    load_data.clear()


metrics, positions, contracts, logs, position_history = load_data()
for frame in (metrics, positions, contracts, position_history):
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])

try:
    external_view_values = dict(st.secrets.get("external_views", {}))
except (FileNotFoundError, KeyError, TypeError):
    external_view_values = {}
external_view_defaults = load_futures_view_settings(ROOT, external_view_values)
if "external_views_enabled" not in st.session_state:
    st.session_state["external_views_enabled"] = external_view_defaults.enabled
external_view_settings = load_futures_view_settings(
    ROOT,
    {**external_view_values, "enabled": st.session_state["external_views_enabled"]},
)

if (
    external_view_settings.enabled
    and external_view_settings.project_available
    and external_view_settings.auto_update
):
    external_target = latest_weekday()
    refresh_key = f"external_views_refresh_{external_target.isoformat()}"
    if not st.session_state.get(refresh_key):
        with st.spinner("正在检查国内大型期货公司观点…"):
            st.session_state["external_views_update_result"] = update_futures_views(
                external_view_settings, external_target
            )
        st.session_state[refresh_key] = True

lang = "en" if st.session_state.get("language_choice") == "English" else "zh"
commodity_pages = [
    st.Page(lambda: render_dashboard("overview"), title="商品日报" if lang == "zh" else "Commodity Daily", url_path="commodity-overview", default=True),
    st.Page(lambda: render_dashboard("detail"), title=cp(lang, "detail"), url_path="commodity-instrument"),
    st.Page(lambda: render_broker_page(), title=cp(lang, "broker"), url_path="commodity-brokers"),
]
if external_view_settings.enabled and external_view_settings.project_available:
    commodity_pages.append(
        st.Page(
            lambda: render_futures_view_page(),
            title="国内大型期货公司观点" if lang == "zh" else "Major futures-company views",
            url_path="commodity-company-views",
        )
    )
commodity_pages.append(
    st.Page(lambda: render_status_page(), title=cp(lang, "status"), url_path="commodity-data-status")
)
market_pages = {
    MARKET_LABELS[lang]["commodity"]: commodity_pages,
    MARKET_LABELS[lang]["equity"]: [
        st.Page(lambda: render_dashboard("overview"), title="股指日报" if lang == "zh" else "Equity Index Daily", url_path="equity-overview"),
        st.Page(lambda: render_dashboard("detail"), title=cp(lang, "detail"), url_path="equity-instrument"),
        st.Page(lambda: render_broker_page(), title=cp(lang, "broker"), url_path="equity-brokers"),
        st.Page(lambda: render_status_page(), title=cp(lang, "status"), url_path="equity-data-status"),
    ],
    MARKET_LABELS[lang]["treasury"]: [
        st.Page(lambda: render_dashboard("overview"), title="国债期货日报" if lang == "zh" else "Treasury Futures Daily", url_path="treasury-overview"),
        st.Page(lambda: render_dashboard("detail"), title=cp(lang, "detail"), url_path="treasury-instrument"),
        st.Page(lambda: render_broker_page(), title=cp(lang, "broker"), url_path="treasury-brokers"),
        st.Page(lambda: render_status_page(), title=cp(lang, "status"), url_path="treasury-data-status"),
    ],
}
navigation = st.navigation(market_pages, position="top")
active_route = navigation.url_path or "commodity-overview"
market_group = next(
    (group for group in MARKET_SYMBOLS if active_route.startswith(f"{group}-")),
    "commodity",
)
market_label = MARKET_LABELS[lang][market_group]


def market_page_title(page_title: str) -> str:
    return f"{market_label}{page_title}" if lang == "zh" else f"{market_label} {page_title}"

with st.sidebar:
    language_label = "Language" if st.session_state.get("language_choice") == "English" else "语言"
    language_choice = st.radio(
        language_label, ["中文", "English"], horizontal=True, key="language_choice"
    )
    lang = "en" if language_choice == "English" else "zh"
    st.markdown(f'<div class="sidebar-brand"><b>◇ SEATALPHA</b><span>{cp(lang,"tagline")}</span></div>', unsafe_allow_html=True)
    st.toggle(
        "接入期货公司观点" if lang == "zh" else "Connect company views",
        key="external_views_enabled",
        help=(
            "启用后自动调用 futures_view 项目并读取其 SQLite 数据库。"
            if lang == "zh" else
            "Calls the futures_view project automatically and reads its SQLite database."
        ),
    )
    if st.session_state["external_views_enabled"]:
        st.caption(str(external_view_settings.root))
        if not external_view_settings.project_available:
            st.warning(
                "未找到有效的 futures_view 项目目录。"
                if lang == "zh" else "The configured futures_view project is unavailable."
            )
    if st.button(f"↻ {cp(lang, 'update')}", width="stretch", type="primary"):
        with st.spinner(cp(lang, "updating")):
            load_data.clear()
            st.session_state["last_update_result"] = update(
                force=True, backfill_history=False, missing_only=True
            )
        load_data.clear(); st.rerun()
    if st.session_state.get("startup_refresh_error"):
        st.warning(
            "最新接口暂时不可用，当前显示上一次成功数据。"
            if lang == "zh" else
            "The latest source request is unavailable; showing the last successful snapshot."
        )
    # Before the evening publication cut-off, today's rankings are not complete.
    # Offer the latest publishable trade date instead of a misleading calendar date.
    latest_published_date = latest_weekday()
    real_dates = sorted(set(metrics.loc[metrics["source"].ne("demo"), "trade_date"].dt.date)
                        | set(position_history.loc[position_history["source"].ne("demo"), "trade_date"].dt.date)
                        | {latest_published_date}, reverse=True)
    selected_date = st.selectbox(cp(lang, "date"), real_dates)
    change_period_labels = {
        1: "1日" if lang == "zh" else "1D",
        5: "1周（5交易日）" if lang == "zh" else "1W (5 trading days)",
        20: "1月（20交易日）" if lang == "zh" else "1M (20 trading days)",
    }
    change_period = st.segmented_control(
        "变化周期" if lang == "zh" else "Change period",
        list(change_period_labels), default=1, format_func=change_period_labels.get,
        key=f"change_period_{market_group}",
        help=("周/月变化只比较同一合约；历史不足时显示为‘—’。" if lang == "zh" else
              "Weekly/monthly changes compare the same contract; insufficient history is shown as ‘—’."),
    ) or 1
    st.caption(
        f"当前市场：{market_label}" if lang == "zh" else f"Current market: {market_label}"
    )
    all_symbols = st.toggle(
        f"全部{market_label}品种" if lang == "zh" else f"All {market_label.lower()} instruments",
        value=True,
        key=f"all_symbols_{market_group}",
    )
    sectors = sorted({SYMBOL_META[symbol][1] for symbol in MARKET_SYMBOLS[market_group]})
    if all_symbols:
        selected_sectors = sectors
        selected_symbols = list(MARKET_SYMBOLS[market_group])
        st.caption(
            f"已包含{market_label}市场全部 {len(selected_symbols)} 个期货品种。"
            if lang == "zh" else
            f"All {len(selected_symbols)} {market_label.lower()} products are included."
        )
    else:
        if market_group == "commodity":
            selected_sectors = st.multiselect(
                cp(lang, "sectors"), sectors, default=sectors,
                format_func=lambda value: sector_name(value, lang),
                key="commodity_sectors",
            )
        else:
            selected_sectors = sectors
        available_symbols = [
            symbol for symbol in MARKET_SYMBOLS[market_group]
            if SYMBOL_META[symbol][1] in selected_sectors
        ]
        selected_symbols = st.multiselect(
            cp(lang, "symbols"), available_symbols, default=available_symbols,
            format_func=lambda symbol: instrument_name(symbol, lang, SYMBOL_META[symbol][0]),
            key=f"selected_symbols_{market_group}",
        )
    if st.session_state.get("category_schema_version") != 2:
        st.session_state["category_schema_version"] = 2
        st.session_state["selected_categories"] = list(CATEGORY_ORDER)
    selected_categories = st.multiselect(
        cp(lang, "categories"),
        CATEGORY_ORDER,
        format_func=lambda c: CATEGORY_LABELS[lang][c],
        key="selected_categories",
    )
    selected_categories = [category for category in CATEGORY_ORDER if category in selected_categories]
    divergence_only = st.toggle(cp(lang, "divergence_only"))
    consensus_only = st.toggle(cp(lang, "consensus_only"))
    major_only = st.toggle(cp(lang, "major_only"))


def render_futures_view_page():
    st.header(
        "国内大型期货公司观点" if lang == "zh" else "Major futures-company views"
    )
    st.caption(
        "数据由 futures_view 项目采集和校验；SeatAlpha 自动调用其更新入口，并以只读方式查询 SQLite 历史库。"
        if lang == "zh" else
        "The futures_view project collects and validates the data. SeatAlpha invokes its updater and queries its SQLite history database read-only."
    )

    update_result = st.session_state.get("external_views_update_result")
    if update_result and update_result.status == "failed":
        st.error(update_result.message)
        if update_result.output:
            with st.expander("更新日志" if lang == "zh" else "Update log"):
                st.code(update_result.output)
    elif update_result and update_result.status == "updated":
        st.success(update_result.message)

    action_col, source_col = st.columns([1, 4])
    with action_col:
        if st.button(
            "立即更新观点" if lang == "zh" else "Update views now",
            type="primary",
            width="stretch",
        ):
            with st.spinner("正在运行 futures_view…" if lang == "zh" else "Running futures_view…"):
                result = update_futures_views(
                    external_view_settings, latest_weekday(), force=True
                )
            st.session_state["external_views_update_result"] = result
            st.rerun()
    with source_col:
        st.caption(
            f"SQLite：{external_view_settings.database_path}"
            if lang == "zh" else f"SQLite: {external_view_settings.database_path}"
        )

    available_dates = available_view_dates(external_view_settings)
    if not available_dates:
        st.warning(
            "尚无通过质量门禁的观点数据。请检查更新日志或对方项目配置。"
            if lang == "zh" else
            "No views have passed the quality gate. Check the update log and source-project configuration."
        )
        return

    selected_view_date = st.selectbox(
        "观点日期" if lang == "zh" else "Views date",
        available_dates,
        key="futures_view_date",
    )
    try:
        bundle = load_futures_view_bundle(external_view_settings, selected_view_date)
    except (FileNotFoundError, OSError, ValueError) as exc:
        st.error(str(exc))
        return

    company_names = ["广发期货", "中信期货", "国泰海通期货", "东证期货"]
    summary_rows = []
    for row in bundle.summary.get("rows", []):
        summary_row = {"板块": row.get("sector")}
        summary_row.update({company: row.get("scores", {}).get(company) for company in company_names})
        summary_row.update({
            "综合得分": row.get("average"),
            "分歧": row.get("divergence"),
            "一致性": row.get("consistency"),
            "综合判断": row.get("judgement"),
        })
        summary_rows.append(summary_row)
    summary_frame = pd.DataFrame(summary_rows)
    outlook_frame = pd.DataFrame(bundle.outlook)
    daily_frame = pd.DataFrame(bundle.daily_records)
    history_frame = pd.DataFrame(bundle.history_records)

    metric_cols = st.columns(4)
    metric_cols[0].metric("观点日期" if lang == "zh" else "Views date", selected_view_date.isoformat())
    metric_cols[1].metric(
        "当日观点" if lang == "zh" else "Daily views",
        int(bundle.quality.get("total_records", len(daily_frame))),
    )
    metric_cols[2].metric(
        "覆盖品种" if lang == "zh" else "Products",
        int(bundle.summary.get("current_view_count", len(outlook_frame))),
    )
    metric_cols[3].metric(
        "质量门禁" if lang == "zh" else "Quality gate",
        "通过" if bundle.quality.get("passed") else "未通过",
    )

    if bundle.excel_path:
        st.download_button(
            "下载原始观点 Excel" if lang == "zh" else "Download source workbook",
            data=bundle.excel_path.read_bytes(),
            file_name=bundle.excel_path.name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    tab_summary, tab_outlook, tab_daily, tab_history, tab_quality = st.tabs(
        [
            "板块汇总" if lang == "zh" else "Sector summary",
            "中期展望" if lang == "zh" else "Medium-term outlook",
            "当日观点明细" if lang == "zh" else "Daily detail",
            "观点历史库" if lang == "zh" else "Views history",
            "运行与数据质量" if lang == "zh" else "Run quality",
        ]
    )
    with tab_summary:
        st.dataframe(summary_frame, hide_index=True, width="stretch")
    with tab_outlook:
        if outlook_frame.empty:
            st.info("暂无中期展望。" if lang == "zh" else "No medium-term outlook is available.")
        else:
            outlook_columns = [
                "commodity", "sector", "direction", "score", "last_update", "age_days",
                "freshness", "sources", "supply", "demand", "inventory", "core_logic",
                "medium_outlook",
            ]
            labels = {
                "commodity": "品种", "sector": "板块", "direction": "方向", "score": "得分",
                "last_update": "最近更新", "age_days": "数据年龄", "freshness": "新鲜度",
                "sources": "来源机构", "supply": "供给", "demand": "需求", "inventory": "库存",
                "core_logic": "核心逻辑", "medium_outlook": "中期展望",
            }
            st.dataframe(
                outlook_frame[[column for column in outlook_columns if column in outlook_frame]].rename(columns=labels),
                hide_index=True,
                width="stretch",
                height=620,
            )
    with tab_daily:
        if daily_frame.empty:
            st.info("数据库中没有当日新增观点。" if lang == "zh" else "No new daily views are stored in the database.")
        else:
            sectors = sorted(daily_frame["sector"].dropna().unique())
            selected_daily_sectors = st.multiselect(
                "筛选板块" if lang == "zh" else "Filter sectors",
                sectors,
                default=sectors,
                key="futures_view_daily_sectors",
            )
            filtered_daily = daily_frame[daily_frame["sector"].isin(selected_daily_sectors)]
            st.dataframe(filtered_daily, hide_index=True, width="stretch", height=620)
    with tab_history:
        if history_frame.empty:
            st.info("观点历史库为空。" if lang == "zh" else "The views history database is empty.")
        else:
            companies = sorted(history_frame["company"].dropna().unique())
            selected_companies = st.multiselect(
                "筛选公司" if lang == "zh" else "Filter companies",
                companies,
                default=companies,
                key="futures_view_history_companies",
            )
            filtered_history = history_frame[history_frame["company"].isin(selected_companies)]
            st.caption(
                f"共 {len(filtered_history):,} 条已校验历史观点。"
                if lang == "zh" else f"{len(filtered_history):,} validated historical views."
            )
            st.dataframe(filtered_history, hide_index=True, width="stretch", height=650)
    with tab_quality:
        quality_rows = [
            {"项目": key, "结果": str(value)}
            for key, value in bundle.quality.items()
            if key not in {"coverage", "issues", "warnings", "record_counts"}
        ]
        st.dataframe(pd.DataFrame(quality_rows), hide_index=True, width="stretch")
        if bundle.quality.get("record_counts"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {"公司代码": company, "观点数": count}
                        for company, count in bundle.quality["record_counts"].items()
                    ]
                ),
                hide_index=True,
                width="stretch",
            )
        for label, key in (("问题", "issues"), ("警告", "warnings")):
            values = bundle.quality.get(key) or []
            if values:
                st.warning(f"{label}：" + "；".join(map(str, values)))


def render_broker_page():
    st.header(market_page_title(cp(lang, "broker")))
    market_positions = positions[positions["symbol"].isin(selected_symbols)]
    profile_source, broker_options = build_broker_profiles(market_positions, selected_date)
    if broker_options:
        broker = st.selectbox(cp(lang, "broker"), broker_options, key=f"broker_{market_group}")
        category = classify_broker(broker)
        st.caption(
            f"席位类别：{CATEGORY_LABELS[lang].get(category, category)}；数据为交易所公布的客户持仓排名。"
            if lang == "zh" else
            f"Seat category: {CATEGORY_LABELS[lang].get(category, category)}; based on published client-position rankings."
        )
        profile = broker_profile_rows(profile_source, broker)
        profile["品种" if lang == "zh" else "Instrument"] = profile["symbol"].map(
            lambda symbol: instrument_name(symbol, lang)
        )
        chart_column = "净持仓" if lang == "zh" else "Net position"
        chart = profile.set_index("品种" if lang == "zh" else "Instrument")[["net_position"]].rename(
            columns={"net_position": chart_column}
        )
        st.bar_chart(chart, horizontal=True)
        visible = profile.drop(columns="symbol").rename(columns={
            "long_position": "多头持仓" if lang == "zh" else "Long position",
            "short_position": "空头持仓" if lang == "zh" else "Short position",
            "long_change": "多头增减" if lang == "zh" else "Long change",
            "short_change": "空头增减" if lang == "zh" else "Short change",
            "net_position": "净持仓" if lang == "zh" else "Net position",
            "net_change": "净变化" if lang == "zh" else "Net change",
        })
        st.dataframe(visible, hide_index=True, width="stretch")
    else: st.info(cp(lang, "no_category"))


def render_status_page():
    st.header(market_page_title(cp(lang, "status")))
    expected_date = latest_weekday(selected_date)
    coverage = build_current_coverage(contracts, positions, selected_date, expected_date)
    coverage = coverage[coverage["symbol"].isin(MARKET_SYMBOLS[market_group])].reset_index(drop=True)
    fresh = int(coverage["status"].eq("最新").sum())
    delayed = int(coverage["status"].str.contains("延迟").sum())
    missing = len(coverage) - fresh - delayed
    summary = st.columns(4)
    summary[0].metric("全部期货品种" if lang == "zh" else "Futures instruments", len(coverage))
    summary[1].metric("数据基准日" if lang == "zh" else "Expected date", expected_date.isoformat())
    summary[2].metric("已更新" if lang == "zh" else "Current", fresh)
    summary[3].metric("延迟 / 暂无" if lang == "zh" else "Delayed / unavailable", f"{delayed} / {missing}")
    if lang == "zh":
        st.info("状态只采用每个品种最新的一条有效记录。8 月 21 日的新浪数据是历史备用记录，若同品种已有更新的 iFinD 数据，不再计为当前延迟。")
    current = coverage.copy()
    current["name"] = current["symbol"].map(lambda symbol: instrument_name(symbol, lang))
    current["sector"] = current["sector"].map(lambda value: sector_name(value, lang))
    if lang == "zh":
        current["exchange"] = current["exchange"].map(EXCHANGE_NAMES_ZH).fillna(current["exchange"])
    else:
        current["status"] = current["status"].replace({
            "暂无数据": "No data", "暂无席位排名": "No member ranking",
            "无活跃主力合约": "No active main contract", "暂无行情": "No quote", "最新": "Current",
        }).str.replace("席位延迟", "Position delayed by", regex=False).str.replace("行情延迟", "Quote delayed by", regex=False).str.replace("个交易日", "trading days", regex=False)
        current["reason"] = current["reason"].replace({
            "目录存在，但当日未返回行情与席位记录": "Listed in the catalog, but no quote or member ranking was returned",
            "当日有活跃行情，但 iFinD/交易所未返回会员排名": "Active quote exists, but iFinD/exchange returned no member ranking",
            "当日持仓量为零，无法选取主力合约": "Open interest is zero; no main contract can be selected",
            "席位存在，但当日行情不可用": "Member ranking exists, but the daily quote is unavailable",
            "行情与席位均达到数据基准日": "Quote and ranking match the expected date",
            "存在交易日延迟": "Trading-day lag exists",
        })
    current["price_source"] = current["price_source"].map(lambda value: source_name(value, lang))
    current["position_source"] = current["position_source"].map(lambda value: source_name(value, lang))
    visible_columns = ["name", "exchange", "sector", "price_date", "price_source",
                       "position_date", "position_source", "status", "reason"]
    current = current[visible_columns].rename(columns={
        "name": "品种" if lang == "zh" else "Instrument",
        "exchange": "交易所" if lang == "zh" else "Exchange",
        "sector": "板块" if lang == "zh" else "Sector",
        "price_date": "行情日期" if lang == "zh" else "Price date",
        "price_source": "行情来源" if lang == "zh" else "Price source",
        "position_date": "席位日期" if lang == "zh" else "Position date",
        "position_source": "席位来源" if lang == "zh" else "Position source",
        "status": "当前状态" if lang == "zh" else "Current status",
        "reason": "原因" if lang == "zh" else "Reason",
    })
    st.dataframe(current, hide_index=True, width="stretch", height=560)

    st.subheader("席位分类说明" if lang == "zh" else "Seat classification")
    if lang == "zh":
        st.warning("“外资”“游资风格”“机构型席位”“散户代理席位”均为对交易所会员持仓排名的研究分类，不代表期货公司的自营观点；“散户代理席位”也不是个人账户数据。游资风格为中财、混沌天成、永安、新湖四个指定席位；散户代理席位仅包含东方财富、徽商期货、弘业期货、瑞达期货。")
    latest_real = positions[
        positions["source"].ne("demo") & positions["trade_date"].dt.date.le(selected_date)
        & positions["symbol"].isin(MARKET_SYMBOLS[market_group])
    ].copy()
    if not latest_real.empty:
        latest_real["latest"] = latest_real.groupby("symbol")["trade_date"].transform("max")
        classified = enrich_broker_classification(latest_real[latest_real["trade_date"].eq(latest_real["latest"])])
    else:
        classified = latest_real
    for category in CATEGORY_ORDER:
        configured = sorted(SEAT_CLASSIFICATION[category])
        observed = sorted(classified.loc[classified["broker_category"].eq(category), "broker_name_normalized"].unique()) if not classified.empty else []
        with st.expander(f"{CATEGORY_LABELS[lang][category]} · {'当前出现' if lang == 'zh' else 'currently observed'} {len(observed)}"):
            if lang == "zh":
                st.write("当前数据中出现：" + ("、".join(observed) if observed else "无"))
                st.caption("分类名单：" + "、".join(configured))
            else:
                st.write("Currently observed: " + (", ".join(observed) if observed else "None"))
                st.caption("Configured list: " + ", ".join(configured))
            if category == "hot_money":
                notes = pd.DataFrame(
                    [
                        {
                            ("席位" if lang == "zh" else "Seat"): broker,
                            ("市场常关联人物/资金" if lang == "zh" else "Common market association"): note,
                        }
                        for broker, note in SEAT_RESEARCH_NOTES[lang].items()
                    ]
                )
                st.dataframe(notes, hide_index=True, width="stretch")
                st.caption(
                    "以上为市场研究中的常见关联备注，仅用于识别席位，不代表账户归属、持仓归属或投资建议。"
                    if lang == "zh"
                    else "These are common market-research associations for seat identification only; they do not establish account ownership, position ownership, or investment advice."
                )

    with st.expander("历史来源覆盖（审计记录）" if lang == "zh" else "Historical source coverage (audit)"):
        st.caption(
            "这里保留旧数据源的历史记录；“最晚日期”不代表当前页面正在使用的数据日期。请以上方当前覆盖状态为准。"
            if lang == "zh" else
            "This table retains historical providers for audit. Its last date is not the active dashboard date; use the current coverage table above."
        )
        history = historical_source_coverage(
            positions[positions["symbol"].isin(MARKET_SYMBOLS[market_group])]
        )
        history["source"] = history["source"].map(lambda value: source_name(value, lang))
        if lang == "zh":
            history["exchange"] = history["exchange"].map(EXCHANGE_NAMES_ZH).fillna(history["exchange"])
            history = history.rename(columns={"exchange": "交易所", "source": "历史来源",
                "first_date": "最早日期", "last_date": "最晚日期", "rows": "记录数", "products": "品种数"})
        st.dataframe(history, hide_index=True, width="stretch")
    with st.expander("完整更新日志" if lang == "zh" else "Full update log"):
        if not logs.empty:
            market_exchanges = {
                SYMBOL_META[symbol][2] for symbol in MARKET_SYMBOLS[market_group]
            }
            display_logs = logs[logs["exchange"].isin(market_exchanges)].copy()
            display_logs["source"] = display_logs["source"].map(lambda value: source_name(value, lang))
            display_logs["message"] = display_logs["message"].map(lambda value: log_message(value, lang))
            if lang == "zh":
                display_logs["exchange"] = display_logs["exchange"].map(EXCHANGE_NAMES_ZH).fillna(display_logs["exchange"])
                display_logs = display_logs.rename(columns={"attempted_at": "更新时间", "trade_date": "数据基准日",
                    "exchange": "交易所", "status": "结果", "rows_written": "写入行数",
                    "message": "说明", "source": "来源"})
            st.dataframe(display_logs, hide_index=True, width="stretch")


def render_price_chart(price: pd.DataFrame, lang: str) -> None:
    """Render a localized price chart without Streamlit's English Vega toolbar."""
    label = "收盘价" if lang == "zh" else "Close"
    date_label = "日期" if lang == "zh" else "Date"
    figure = go.Figure(go.Scatter(
        x=price["trade_date"], y=price["close"], mode="lines+markers",
        name=label, line={"color": "#a78331", "width": 2},
        marker={"size": 4},
        hovertemplate=(
            "日期 %{x|%Y-%m-%d}<br>收盘价 %{y:,.2f}<extra></extra>"
            if lang == "zh" else
            "Date %{x|%Y-%m-%d}<br>Close %{y:,.2f}<extra></extra>"
        ),
    ))
    figure.update_layout(
        height=280, paper_bgcolor="#fff", plot_bgcolor="#fff", showlegend=False,
        margin={"l": 55, "r": 20, "t": 15, "b": 45},
        xaxis_title=date_label, yaxis_title=label,
    )
    figure.update_xaxes(gridcolor="#e5e9ea", tickformat="%m-%d" if lang == "zh" else "%b %d")
    figure.update_yaxes(gridcolor="#e5e9ea", tickformat=",.2f")
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})


def render_metric_formulas(change_period: int, lang: str) -> None:
    period = {1: "1日", 5: "1周（5交易日）", 20: "1月（20交易日）"}.get(change_period, str(change_period))
    if lang == "zh":
        content = f"""
        <div id="metric-formulas" class="formula-box">
          <h3>指标定义与计算公式</h3>
          <p><b>当前变化周期：</b>{period}。1日采用排名表公布的相对上一交易日增减；周/月采用同一合约当前快照与目标交易日前最近可用快照比较。历史不足显示“—”。</p>
          <h4>仓位与变化</h4>
          <p><code>净仓 = 多头持仓合计 − 空头持仓合计</code>；横条从中线向右为净多，向左为净空，长度表示绝对手数。</p>
          <p><code>Δ净变化 = 多头持仓变化 − 空头持仓变化</code>。周/月比较不跨主力合约；排名进出也会影响公开 Top20 口径。</p>
          <p><code>一致性 = (净加多席位数 − 净加空席位数) ÷ 有方向席位数</code>。它只统计方向，不按变化手数加权。</p>
          <h4>信号与分歧</h4>
          <p><code>总持仓 = 多头持仓 + 空头持仓</code>。它是方向信号的比例分母，并不等于净仓绝对值。</p>
          <p><code>绝对方向分 = 0.55×净仓/总持仓 + 0.30×截断(Δ净变化/总持仓, −1, 1) + 0.15×一致性</code>。强多/偏多/中性/偏空/强空按这个绝对分划分，不再由品种之间的相对排名决定。</p>
          <p><code>强多 ≥ +0.20；偏多 = +0.02 至 +0.20；中性 = −0.02 至 +0.02（不含边界）；偏空 = −0.20 至 −0.02；强空 ≤ −0.20</code>。板块标签先汇总板块净仓、总持仓和变化，再按有方向席位数加权一致性后计算，不对品种 Z 分做简单平均。</p>
          <p><code>标准化信号 Z = (绝对方向分 − 同类别全品种均值) ÷ 同类别全品种标准差</code>。</p>
          <p><code>四方分歧 = 四类标准化信号所有两两绝对距离的最大值</code>。页面显示的是标准化信号差，数值后的 σ 表示 Z 分差。</p>
          <h4>机构—散户分歧图</h4>
          <p>横轴＝机构型标准化信号；纵轴＝散户代理标准化信号；点大小＝两类信号的绝对距离。这里只保留两方，四类数据仍用于总体分歧值。</p>
          <p><b>数据说明：</b>分类基于交易所公开会员持仓排名，不代表期货公司自营观点；“散户代理席位”也不是个人账户持仓。</p>
          <p><a href="#metric-formulas">回到本说明</a></p>
        </div>"""
    else:
        content = """
        <div id="metric-formulas" class="formula-box"><h3>Metric definitions and formulas</h3>
        <p><b>Net position</b> = total longs − total shorts. <b>Net change</b> = long change − short change.</p>
        <p><b>Consensus</b> = (net-adding seats − net-reducing seats) / directional seats.</p>
        <p><b>Gross position</b> = longs + shorts. <b>Absolute direction score</b> = 0.55×net/gross + 0.30×clipped(net change/gross) + 0.15×consensus. Direction labels use this absolute score.</p>
        <p><b>Thresholds:</b> strong long ≥ +0.20; long from +0.02 to +0.20; neutral strictly between −0.02 and +0.02; short from −0.20 to −0.02; strong short ≤ −0.20. Sector labels use aggregated positions and seat-weighted consensus.</p>
        <p>The score is standardized within each category only for relative ranking and divergence.</p>
        <p><b>Four-way divergence</b> is the maximum absolute pairwise distance among the four standardized category signals.</p>
        <p>The simplified chart uses institution on X, retail proxy on Y, and their absolute standardized-signal gap as point size.</p></div>"""
    st.markdown(section_header("08", "指标说明" if lang == "zh" else "Metric guide",
                               "完整口径与计算公式" if lang == "zh" else "Complete definitions and formulas"),
                unsafe_allow_html=True)
    st.markdown(content, unsafe_allow_html=True)


def render_dashboard(page: str = "overview"):
    base = build_snapshot(metrics, positions, position_history, selected_date, selected_sectors, contracts)
    base = base[base["symbol"].isin(selected_symbols)]
    if market_group == "equity":
        base["sector"] = "股指期货"
    elif market_group == "treasury":
        base["sector"] = "国债期货"
    coverage = build_current_coverage(
        contracts, positions, selected_date, latest_weekday(selected_date)
    )
    coverage = coverage[coverage["symbol"].isin(selected_symbols)]
    detail_symbol = None
    if page == "detail":
        st.header(market_page_title(cp(lang, "detail")))
        if not selected_symbols:
            st.info(cp(lang, "no_category"))
            return
        detail_key = f"detail_symbol_{market_group}"
        if detail_key in st.session_state and st.session_state[detail_key] not in selected_symbols:
            st.session_state[detail_key] = selected_symbols[0]
        detail_symbol = st.selectbox(cp(lang, "symbols"), selected_symbols, key=detail_key,
                                     format_func=lambda symbol: instrument_name(symbol, lang))
        if detail_symbol not in set(base["symbol"]):
            # The selectbox can retain a value across a language/filter rerun
            # while the current snapshot has no matching coverage row.  Never
            # index an empty lookup during that transient state.
            matching_status = coverage[coverage["symbol"].eq(detail_symbol)]
            status_text = matching_status.iloc[0]["status"] if not matching_status.empty else "暂无数据"
            reason_text = matching_status.iloc[0]["reason"] if not matching_status.empty else "当前筛选下暂无该品种的可用记录"
            st.warning(
                f"{instrument_name(detail_symbol, lang)}：{status_text}。{reason_text}"
                if lang == "zh" else
                f"{instrument_name(detail_symbol, lang)}: member-level analysis is unavailable for this date."
            )
            price = contracts[(contracts["symbol"].eq(detail_symbol)) & contracts["source"].ne("demo") & contracts["close"].gt(0)].sort_values("trade_date").drop_duplicates("trade_date")
            if not price.empty:
                render_price_chart(price, lang)
            return
    category_rows, wide = build_three_category_snapshot(
        positions, base, selected_date, change_period=change_period
    )
    if category_rows.empty or wide.empty or not selected_categories:
        st.warning(cp(lang, "no_category")); st.stop()

    if divergence_only:
        wide = wide[wide["divergence_score"].ge(SIGNAL_THRESHOLDS["high_divergence"])]
    if consensus_only:
        wide = wide[wide["three_way_consensus"].ne(0)]
    if major_only and not category_rows.empty:
        threshold = category_rows["net_change"].abs().mean() + category_rows["net_change"].abs().std(ddof=0)
        major_symbols = category_rows.loc[category_rows["net_change"].abs().ge(threshold), "symbol"].unique()
        wide = wide[wide["symbol"].isin(major_symbols)]
    category_rows = category_rows[category_rows["symbol"].isin(wide["symbol"])]
    if wide.empty:
        st.warning(cp(lang, "no_category")); st.stop()
    display_categories = category_rows[category_rows["broker_category"].isin(selected_categories)]

    latest_positions = positions[positions["source"].ne("demo") & positions["trade_date"].dt.date.le(selected_date)
                                 & positions["symbol"].isin(base["symbol"])].copy()
    if not latest_positions.empty:
        latest_positions["latest"] = latest_positions.groupby("symbol")["trade_date"].transform("max")
        latest_positions = enrich_broker_classification(latest_positions[latest_positions["trade_date"].eq(latest_positions["latest"])])
    unclassified = sorted(latest_positions.loc[latest_positions["broker_category"].eq("other"), "broker_name_normalized"].unique()) if not latest_positions.empty else []

    latest_update = pd.to_datetime(logs["attempted_at"]).max() if not logs.empty else pd.NaT
    covered_exchange_codes = sorted(base["exchange"].dropna().unique())
    covered_exchanges = "、".join(
        EXCHANGE_NAMES_ZH.get(code, code) for code in covered_exchange_codes
    ) if lang == "zh" else ", ".join(covered_exchange_codes)
    updated_text = latest_update.strftime("%Y-%m-%d %H:%M") if pd.notna(latest_update) else "—"
    kicker = (
        f"期货会员持仓 · {market_label}市场图谱"
        if lang == "zh" else
        f"INSTITUTIONAL POSITIONING · {market_label.upper()} ATLAS"
    )
    report_title = (
        f"{market_label}期货持仓全景"
        if lang == "zh" and market_group != "treasury" else
        f"{market_label}持仓全景"
        if lang == "zh" else
        f"{market_label} Positioning Atlas"
    )
    st.markdown(f'''<div class="report-head"><div><span class="kicker">{kicker}</span>
    <h1>{report_title}</h1><p>{cp(lang,"tagline")}</p></div><div class="meta"><b>{selected_date:%Y.%m.%d}</b><br>
    {'更新时间' if lang=='zh' else 'Updated'}: {updated_text}<br>{'覆盖交易所' if lang=='zh' else 'Exchanges'}: {covered_exchanges}</div></div>''', unsafe_allow_html=True)
    if change_period > 1:
        available_symbols = category_rows.loc[category_rows["change_available"], "symbol"].nunique()
        missing_symbols = category_rows["symbol"].nunique() - available_symbols
        if missing_symbols:
            st.warning(
                f"所选周期有 {missing_symbols} 个品种缺少同合约历史基线，其 Δ 和一致性显示为‘—’，不以 0 代替。"
                if lang == "zh" else
                f"{missing_symbols} instruments lack a same-contract baseline; change and consensus are shown as ‘—’, not zero."
            )

    if page == "overview":
        # Generate the standalone snapshot only when requested so routine page
        # loads and filter reruns remain fast.
        def generate_static_report():
            return build_static_daily_report(
                display_categories,
                wide,
                coverage,
                selected_date,
                market_label,
                lang,
                selected_categories,
                updated_at=latest_update,
            )

        st.download_button(
            "↓ 导出当日静态日报（HTML）" if lang == "zh" else "↓ Export daily snapshot (HTML)",
            data=generate_static_report,
            file_name=f"SeatAlpha_{market_group}_{selected_date:%Y-%m-%d}.html",
            mime="text/html",
            width="stretch",
            help=(
                "导出当前市场、日期与筛选条件的数据快照；文件可离线打开，但不会自动更新。"
                if lang == "zh" else
                "Exports the current market, date and filters as an offline snapshot; the file will not update automatically."
            ),
        )
        st.caption(
            "HTML 已内嵌当前数据与图表，可直接发送；接收者无需安装 Python 或连接 iFinD。"
            if lang == "zh" else
            "The HTML embeds the current data and charts; recipients need neither Python nor an iFinD connection."
        )

    if unclassified:
        with st.expander(f"⚠ {cp(lang, 'unclassified')}: {len(unclassified)} · {cp(lang, 'warning_help')}"):
            st.write(" · ".join(unclassified))

    if page == "overview":
        ready_count = int(coverage["status"].eq("最新").sum())
        unavailable = coverage[coverage["status"].ne("最新")].copy()
        if lang == "zh":
            st.caption(
                f"当前筛选共 {len(coverage)} 个期货品种：{ready_count} 个可计算席位信号，"
                f"{len(unavailable)} 个因交易所未发布排名、无活跃合约或暂无数据而仅保留在目录中。"
            )
        else:
            st.caption(
                f"{len(coverage)} futures products in the current filter: {ready_count} have "
                f"computable member signals and {len(unavailable)} remain catalogued but unavailable."
            )
        if not unavailable.empty:
            unavailable["name"] = unavailable["symbol"].map(
                lambda symbol: instrument_name(symbol, lang)
            )
            if lang == "zh":
                unavailable = unavailable[["name", "status", "reason"]].rename(
                    columns={"name": "品种", "status": "当前状态", "reason": "原因"}
                )
                label = f"暂不可计算席位信号的品种 · {len(unavailable)}"
            else:
                unavailable = unavailable[["symbol", "name", "status", "reason"]].rename(
                    columns={"symbol": "Code", "name": "Instrument", "status": "Status", "reason": "Reason"}
                )
                label = f"Products without computable member signals · {len(unavailable)}"
            with st.expander(label):
                st.dataframe(unavailable, hide_index=True, width="stretch")

    if page == "detail":
        detail = display_categories[display_categories["symbol"].eq(detail_symbol)]
        columns = st.columns(max(len(selected_categories), 1))
        for column, category in zip(columns, selected_categories):
            row = detail[detail["broker_category"].eq(category)]
            if not row.empty:
                row = row.iloc[0]
                delta_text = f"Δ {row['net_change']:+,.0f}" if pd.notna(row["net_change"]) else "Δ —"
                column.metric(CATEGORY_LABELS[lang][category], f"{row['net_position']:+,.0f}", delta_text)
                consistency_text = f"{row['consistency']:+.0%}" if pd.notna(row["consistency"]) else "—"
                column.caption(f'{"一致性" if lang=="zh" else "Consensus"} {consistency_text}')
        detail_contracts = detail["contract"].dropna().astype(str).unique().tolist()
        detail_positions = positions[
            positions["source"].ne("demo")
            & positions["trade_date"].dt.date.le(selected_date)
            & positions["symbol"].eq(detail_symbol)
            & positions["contract"].astype(str).isin(detail_contracts)
        ].copy()
        if not detail_positions.empty:
            detail_positions["latest"] = detail_positions["trade_date"].max()
            detail_positions = detail_positions[detail_positions["trade_date"].eq(detail_positions["latest"])]
            detail_positions = enrich_broker_classification(detail_positions)
            detail_positions["net_position"] = detail_positions["long_position"] - detail_positions["short_position"]
            detail_positions["gross_position"] = detail_positions["long_position"] + detail_positions["short_position"]
            st.markdown(
                "#### 各类最大仓位前 5 家" if lang == "zh" else "#### Top 5 seats by gross position in each category"
            )
            st.caption(
                "按多头持仓＋空头持仓排序；净仓＝多头－空头。席位未进入当日公开排名时不会显示。"
                if lang == "zh" else
                "Ranked by long plus short positions; net equals long minus short. Seats absent from the published ranking are not shown."
            )
            top_columns = st.columns(max(len(selected_categories), 1))
            for column, category in zip(top_columns, selected_categories):
                ranked = detail_positions[detail_positions["broker_category"].eq(category)].nlargest(5, "gross_position")
                with column:
                    st.markdown(f"**{CATEGORY_LABELS[lang][category]}**")
                    if ranked.empty:
                        st.caption("—")
                    else:
                        shown = ranked[["broker_name_normalized", "long_position", "short_position", "net_position"]].rename(columns={
                            "broker_name_normalized": "席位" if lang == "zh" else "Seat",
                            "long_position": "多头" if lang == "zh" else "Long",
                            "short_position": "空头" if lang == "zh" else "Short",
                            "net_position": "净仓" if lang == "zh" else "Net",
                        })
                        st.dataframe(shown, hide_index=True, width="stretch")
        price = contracts[(contracts["symbol"].eq(detail_symbol)) & contracts["source"].ne("demo") & contracts["close"].gt(0)].sort_values("trade_date").drop_duplicates("trade_date")
        render_price_chart(price, lang)
        render_metric_formulas(change_period, lang)
        return

    st.markdown(section_header("01", cp(lang, "overview"), cp(lang, "overview_note")), unsafe_allow_html=True)
    st.markdown(overview_cards(display_categories, wide, lang, selected_categories), unsafe_allow_html=True)
    st.markdown(section_header("02", cp(lang, "sector"), cp(lang, "sector_note")), unsafe_allow_html=True)
    st.markdown(metric_quick_guide(lang), unsafe_allow_html=True)
    st.markdown(sector_matrix(display_categories, lang, selected_categories), unsafe_allow_html=True)

    st.markdown(section_header("03", cp(lang, "map"), cp(lang, "map_note")), unsafe_allow_html=True)
    chart_sectors = sorted(wide["sector"].dropna().unique())
    scope_labels = {
        "leaders": "各板块代表" if lang == "zh" else "Sector leaders",
        "sector": "单一板块" if lang == "zh" else "Single sector",
        "market": "全市场" if lang == "zh" else "Full market",
    }
    chart_scope = st.segmented_control(
        "图表范围" if lang == "zh" else "Chart scope",
        list(scope_labels),
        default="leaders" if market_group == "commodity" else "market",
        format_func=scope_labels.get,
        key=f"chart_scope_{market_group}",
    )
    if chart_scope == "sector":
        default_chart_sector = "黑色" if "黑色" in chart_sectors else chart_sectors[0]
        chart_sector = st.selectbox(
            "图表板块" if lang == "zh" else "Chart sector",
            chart_sectors,
            index=chart_sectors.index(default_chart_sector),
            format_func=lambda value: sector_name(value, lang),
            key=f"chart_sector_{market_group}",
        )
        map_wide = wide[wide["sector"].eq(chart_sector)]
    elif chart_scope == "leaders":
        top_n = st.slider(
            "每个板块显示品种数" if lang == "zh" else "Instruments per sector",
            min_value=1,
            max_value=5,
            value=2,
            key=f"sector_top_n_{market_group}",
        )
        map_wide = select_sector_leaders(wide, top_n)
    else:
        map_wide = wide
    map_category_rows = category_rows[category_rows["symbol"].isin(map_wide["symbol"])]
    show_all_chart_labels = st.toggle(
        "显示全部品种标签" if lang == "zh" else "Show all instrument labels",
        value=True,
        key=f"show_all_chart_labels_{market_group}",
        help=(
            "默认仅标注变化最明显的席位数据点；同一品种在不同席位类别中分别处理，所有点均可悬浮查看完整名称。"
            if lang == "zh" else
            "By default, only the most notable seat data points are labelled; each seat category is handled separately, and every point retains its full hover name."
        ),
    )
    st.caption(
        f"当前图表展示 {len(map_wide)} 个品种；默认直接标注变化较大的席位数据点，其余可悬浮查看。"
        if lang == "zh" else
        f"The charts show {len(map_wide)} instruments. Notable seat data points are labelled; hover for all names."
    )
    map_mode = st.segmented_control(cp(lang, "compare"), [cp(lang, "all")] + [CATEGORY_LABELS[lang][c] for c in selected_categories], default=cp(lang, "all"))
    visible_categories = [
        category for category in selected_categories
        if map_mode == cp(lang, "all") or map_mode == CATEGORY_LABELS[lang][category]
    ]
    label_candidates = map_category_rows[
        map_category_rows["broker_category"].isin(visible_categories)
    ].copy()
    label_candidates["label_priority"] = label_candidates["net_change"].abs()
    label_candidates = label_candidates.sort_values("label_priority", ascending=False)
    if not show_all_chart_labels:
        label_candidates = label_candidates.head(12 if chart_scope == "leaders" else 6)
    direct_label_keys = set(zip(label_candidates["symbol"], label_candidates["broker_category"]))
    fig = go.Figure(); marker_symbols = {"qian_kun": "diamond", "hot_money": "star", "institution": "circle", "retail": "triangle-up"}
    for category in visible_categories:
        block = map_category_rows[map_category_rows["broker_category"].eq(category)]
        block = block[block["net_change"].notna() & block["consistency"].notna()]
        if block.empty: continue
        gross = block["long_position"] + block["short_position"]
        sizes = 12 + 28 * np.sqrt(gross / max(float(gross.max()), 1))
        display_names = block["symbol"].map(lambda symbol: instrument_name(symbol, lang))
        direct_labels = [
            instrument_name(symbol, lang) if (symbol, category) in direct_label_keys else ""
            for symbol in block["symbol"]
        ]
        fig.add_trace(go.Scatter(x=block["net_change"], y=block["consistency"] * 100,
            mode="markers+text" if any(direct_labels) else "markers",
            text=direct_labels,
            textposition=radial_text_positions(block["net_change"], block["consistency"] * 100),
            textfont={"size": 10},
            name=CATEGORY_LABELS[lang][category], hovertext=display_names,
            customdata=np.stack([block["net_position"], block["long_position"], block["short_position"], block["signal_score"]], axis=-1),
            hovertemplate=("%{hovertext}<br>净仓变化 %{x:,.0f}<br>一致性 %{y:+.1f}%<br>净持仓 %{customdata[0]:,.0f}<br>多头 %{customdata[1]:,.0f}<br>空头 %{customdata[2]:,.0f}<br>信号 %{customdata[3]:+.2f}<extra></extra>" if lang == "zh" else "%{hovertext}<br>Net change %{x:,.0f}<br>Consensus %{y:+.1f}%<br>Net %{customdata[0]:,.0f}<br>Long %{customdata[1]:,.0f}<br>Short %{customdata[2]:,.0f}<br>Signal %{customdata[3]:+.2f}<extra></extra>"),
            marker={"size": sizes, "color": CATEGORY_COLORS[category], "symbol": marker_symbols[category], "opacity": .8, "line": {"color": "white", "width": 1}}))
    fig.add_hline(y=0, line_dash="dot", line_color="#8b959b"); fig.add_vline(x=0, line_dash="dot", line_color="#8b959b")
    fig.update_layout(height=520, paper_bgcolor="#fff", plot_bgcolor="#fff", margin={"l":50,"r":25,"t":25,"b":45},
                      xaxis_title="净仓变化" if lang=="zh" else "Net change", yaxis_title="一致性 (%)" if lang=="zh" else "Consensus (%)",
                      legend={"orientation":"h","y":1.08}, font={"color":"#19242c"})
    fig.update_xaxes(gridcolor="#e5e9ea", tickformat=",d" if lang == "zh" else None)
    fig.update_yaxes(gridcolor="#e5e9ea")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    st.markdown(section_header("03B", cp(lang, "div_map"), cp(lang, "div_note")), unsafe_allow_html=True)
    map_wide = map_wide.copy()
    map_wide["institution_retail_gap"] = (map_wide["institution_signal"] - map_wide["retail_signal"]).abs()
    divergence_label_rows = map_wide.sort_values("institution_retail_gap", ascending=False)
    if not show_all_chart_labels:
        divergence_label_rows = divergence_label_rows.head(6)
    divergence_label_symbols = set(divergence_label_rows["symbol"])
    divergence_labels = [
        instrument_name(symbol, lang) if symbol in divergence_label_symbols else ""
        for symbol in map_wide["symbol"]
    ]
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=map_wide["institution_signal"], y=map_wide["retail_signal"],
        mode="markers+text" if any(divergence_labels) else "markers", text=divergence_labels,
        textposition=radial_text_positions(map_wide["institution_signal"], map_wide["retail_signal"]),
        textfont={"size": 10}, showlegend=False,
        hovertext=map_wide["symbol"].map(lambda symbol: instrument_name(symbol, lang)),
        customdata=map_wide[["institution_retail_gap"]].to_numpy(),
        hovertemplate=("%{hovertext}<br>机构 %{x:+.2f}<br>散户代理 %{y:+.2f}<br>两方分歧 %{customdata[0]:.2f} Z分<extra></extra>" if lang == "zh" else "%{hovertext}<br>Institution %{x:+.2f}<br>Retail proxy %{y:+.2f}<br>Two-party gap %{customdata[0]:.2f} Z pts<extra></extra>"),
        marker={"size": 16 + map_wide["institution_retail_gap"].clip(0, 4) * 8,
                "symbol": "circle", "color": "#315f78", "opacity": .78,
                "line": {"color": "#fff", "width": 1}},
    ))
    fig2.add_hline(y=0,line_dash="dot",line_color="#8b959b"); fig2.add_vline(x=0,line_dash="dot",line_color="#8b959b")
    fig2.update_layout(height=480,paper_bgcolor="#fff",plot_bgcolor="#fff",margin={"l":50,"r":30,"t":20,"b":45},
                       xaxis_title="机构信号" if lang=="zh" else "Institution signal", yaxis_title="散户信号" if lang=="zh" else "Retail signal",
                       showlegend=False)
    fig2.update_xaxes(gridcolor="#e5e9ea"); fig2.update_yaxes(gridcolor="#e5e9ea")
    st.plotly_chart(fig2, width="stretch", config={"displayModeBar": False})

    st.markdown(section_header("04", cp(lang, "panorama"), cp(lang, "panorama_note")), unsafe_allow_html=True)
    st.markdown(metric_quick_guide(lang), unsafe_allow_html=True)
    st.markdown(panorama_rows(wide, lang, selected_categories), unsafe_allow_html=True)
    st.markdown(section_header("05", cp(lang, "changes"), cp(lang, "changes_note")), unsafe_allow_html=True)
    st.markdown('<div class="change-grid">' + "".join(change_column(display_categories, c, lang) for c in selected_categories) + '</div>', unsafe_allow_html=True)
    st.markdown(section_header("06", cp(lang, "monitor"), cp(lang, "monitor_note")), unsafe_allow_html=True)
    st.markdown(monitor_cards(wide, lang), unsafe_allow_html=True)
    st.markdown(section_header("07", cp(lang, "executive"), cp(lang, "executive_note")), unsafe_allow_html=True)
    st.markdown('<div class="executive-box">' + "".join(f'<p>• {line}</p>' for line in executive_read(display_categories, wide, lang)) + '</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="caveat">{cp(lang,"data_limit")}</div>', unsafe_allow_html=True)
    render_metric_formulas(change_period, lang)


navigation.run()
