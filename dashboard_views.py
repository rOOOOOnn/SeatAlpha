from __future__ import annotations

from html import escape

import numpy as np
import pandas as pd

from config import SYMBOL_META
from i18n import instrument_name, sector_name, signal_name
from pipeline.clean import is_valid_broker

INK = "#17222b"
MUTED = "#73808a"
TEAL = "#2b7d75"
BLUE = "#426b88"
GOLD = "#a78331"
ROSE = "#b45f6a"
GRID = "#dfe5e7"


def build_broker_profiles(positions: pd.DataFrame, selected_date) -> tuple[pd.DataFrame, list[str]]:
    """Return the latest meaningful broker rows and brokers ordered by gross position."""
    required = {"trade_date", "source", "symbol", "broker"}
    value_columns = ["long_position", "short_position", "long_change", "short_change"]
    if positions.empty or not required.union(value_columns).issubset(positions.columns):
        return pd.DataFrame(columns=list(positions.columns)), []
    real = positions[
        positions["source"].ne("demo") & positions["trade_date"].dt.date.le(selected_date)
    ].copy()
    real["broker"] = real["broker"].map(lambda value: str(value).strip())
    real = real[real["broker"].map(is_valid_broker)]
    for column in value_columns:
        real[column] = pd.to_numeric(real[column], errors="coerce").fillna(0)
    real = real[real[value_columns].abs().sum(axis=1).gt(0)]
    if real.empty:
        return real, []
    real["latest"] = real.groupby("symbol")["trade_date"].transform("max")
    real = real[real["trade_date"].eq(real["latest"])].copy()
    scores = real.assign(
        gross=real["long_position"].abs() + real["short_position"].abs(),
        activity=real["long_change"].abs() + real["short_change"].abs(),
    ).groupby("broker", as_index=False).agg(gross=("gross", "sum"), activity=("activity", "sum"))
    options = scores.sort_values(["gross", "activity", "broker"], ascending=[False, False, True])["broker"].tolist()
    return real, options


def broker_profile_rows(latest_positions: pd.DataFrame, broker: str) -> pd.DataFrame:
    """Aggregate one broker by instrument and suppress zero-only chart rows."""
    columns = ["symbol", "long_position", "short_position", "long_change", "short_change"]
    if latest_positions.empty:
        return pd.DataFrame(columns=columns + ["net_position", "net_change"])
    profile = latest_positions[latest_positions["broker"].eq(broker)].groupby("symbol", as_index=False).agg(
        long_position=("long_position", "sum"), short_position=("short_position", "sum"),
        long_change=("long_change", "sum"), short_change=("short_change", "sum"),
    )
    profile = profile[profile[columns[1:]].abs().sum(axis=1).gt(0)].copy()
    profile["net_position"] = profile["long_position"] - profile["short_position"]
    profile["net_change"] = profile["long_change"] - profile["short_change"]
    return profile.reset_index(drop=True)


def build_snapshot(
    metrics: pd.DataFrame,
    positions: pd.DataFrame,
    position_history: pd.DataFrame,
    selected_date,
    selected_sectors: list[str],
    contracts: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build one honest as-of row per symbol from the latest real observation."""
    eligible = metrics[(metrics["trade_date"].dt.date.le(selected_date)) & metrics["source"].ne("demo")].copy()
    eligible["sector"] = eligible["symbol"].map(lambda s: SYMBOL_META.get(s, (s, "其他", ""))[1])
    eligible = eligible[eligible["sector"].isin(selected_sectors)]
    if eligible.empty:
        current = pd.DataFrame()
    else:
        eligible["latest_date"] = eligible.groupby("symbol")["trade_date"].transform("max")
        current = eligible[eligible["trade_date"].eq(eligible["latest_date"])].copy()
        current = current.sort_values(["symbol", "open_interest"]).drop_duplicates("symbol", keep="last")
        current["consensus_available"] = True
        if "price_source" not in current:
            current["price_source"] = current["source"]

    history = position_history[
        position_history["trade_date"].dt.date.le(selected_date) & position_history["source"].ne("demo")
    ].copy()
    history["sector"] = history["symbol"].map(lambda s: SYMBOL_META.get(s, (s, "其他", ""))[1])
    history = history[history["sector"].isin(selected_sectors)]
    if not history.empty:
        history["priority"] = history["source"].eq("official-aggregate-via-akshare").astype(int)
        latest_seed = history.sort_values(["symbol", "trade_date", "priority"]).drop_duplicates(
            "symbol", keep="last"
        )
        existing_symbols = set(current["symbol"]) if not current.empty else set()
        latest_seed = latest_seed[~latest_seed["symbol"].isin(existing_symbols)]
        if not latest_seed.empty:
            prices = pd.DataFrame()
            if contracts is not None and not contracts.empty:
                prices = contracts[
                    contracts["trade_date"].dt.date.le(selected_date)
                    & contracts["source"].ne("demo")
                    & contracts["close"].gt(0)
                    & contracts["symbol"].isin(latest_seed["symbol"])
                ].copy()
                prices = prices.sort_values(["symbol", "trade_date", "open_interest"]).drop_duplicates(
                    "symbol", keep="last"
                ).set_index("symbol")
            seed_rows = []
            for row in latest_seed.itertuples(index=False):
                price = prices.loc[row.symbol] if row.symbol in prices.index else None
                seed_rows.append({
                    "trade_date": row.trade_date,
                    "exchange": row.exchange,
                    "symbol": row.symbol,
                    "contract": str(price["contract"]) if price is not None else row.symbol,
                    "close": float(price["close"]) if price is not None else np.nan,
                    "open_interest": float(price["open_interest"]) if price is not None else row.top20_long + row.top20_short,
                    "top20_long": np.nan,
                    "top20_short": np.nan,
                    "net_position": np.nan,
                    "net_position_ratio": np.nan,
                    "delta_net_1d": 0.0,
                    "delta_net_5d": 0.0,
                    "delta_net_20d": 0.0,
                    "price_change_1d": 0.0,
                    "consensus": np.nan,
                    "bull_score": 0.0,
                    "divergence_score": 0.0,
                    "source": row.source,
                    "price_source": str(price["source"]) if price is not None else "unavailable",
                    "consensus_available": False,
                    "sector": row.sector,
                })
            current = pd.concat([current, pd.DataFrame(seed_rows)], ignore_index=True, sort=False)
    if current.empty:
        return current

    # Price and position observations are intentionally independent. A current
    # quote may coexist with an older exchange ranking and must keep its own date.
    if contracts is not None and not contracts.empty:
        prices = contracts[
            contracts["trade_date"].dt.date.le(selected_date)
            & contracts["source"].ne("demo")
            & contracts["close"].gt(0)
            & contracts["symbol"].isin(current["symbol"])
        ].copy()
        if not prices.empty:
            prices = prices.sort_values(["symbol", "trade_date", "open_interest"]).drop_duplicates(
                "symbol", keep="last"
            )
            prices = prices[["symbol", "trade_date", "close", "open_interest", "source"]].rename(columns={
                "trade_date": "price_date", "close": "latest_close",
                "open_interest": "latest_open_interest", "source": "latest_price_source",
            })
            current = current.merge(prices, on="symbol", how="left")
            current["close"] = current["latest_close"].where(current["latest_close"].notna(), current["close"])
            current["open_interest"] = current["latest_open_interest"].where(
                current["latest_open_interest"].notna(), current["open_interest"]
            )
            current["price_source"] = current["latest_price_source"].where(
                current["latest_price_source"].notna(), current["price_source"]
            )
    if "price_date" not in current:
        current["price_date"] = current["trade_date"]
    current["price_date"] = pd.to_datetime(current["price_date"].fillna(current["trade_date"]))

    history = history[history["symbol"].isin(current["symbol"])].copy()
    if not history.empty:
        history = history.sort_values(["symbol", "trade_date", "priority"]).drop_duplicates(
            ["symbol", "trade_date"], keep="last"
        )
        history["previous_net"] = history.groupby("symbol")["net_position"].shift(1)
        history["position_delta"] = history["net_position"] - history["previous_net"]
        latest_history = history.sort_values("trade_date").groupby("symbol", as_index=False).tail(1)
        latest_history = latest_history[[
            "symbol", "trade_date", "top20_long", "top20_short", "net_position",
            "net_position_ratio", "position_delta", "source",
        ]].rename(columns={
            "trade_date": "position_date", "source": "position_source",
            "top20_long": "history_long", "top20_short": "history_short",
            "net_position": "history_net", "net_position_ratio": "history_ratio",
        })
        current = current.merge(latest_history, on="symbol", how="left")
        for target, source in (
            ("top20_long", "history_long"), ("top20_short", "history_short"),
            ("net_position", "history_net"), ("net_position_ratio", "history_ratio"),
        ):
            current[target] = current[source].where(current[source].notna(), current[target])
        aggregate_override = current["position_date"].notna() & current["position_date"].ne(current["trade_date"])
        current.loc[aggregate_override, "consensus"] = np.nan
        current.loc[aggregate_override, "consensus_available"] = False
    else:
        current["position_date"] = current["trade_date"]
        current["position_source"] = current["source"]
        current["position_delta"] = np.nan

    pos = positions[
        positions["trade_date"].dt.date.le(selected_date) & positions["symbol"].isin(current["symbol"])
        & positions["source"].ne("demo")
    ].copy()
    if not pos.empty:
        pos["latest_date"] = pos.groupby("symbol")["trade_date"].transform("max")
        pos = pos[pos["trade_date"].eq(pos["latest_date"])]
        changes = pos.groupby("symbol", as_index=False).agg(
            long_change=("long_change", "sum"), short_change=("short_change", "sum"),
            active_brokers=("broker", "nunique"), change_date=("trade_date", "max"),
        )
        changes["net_change"] = changes["long_change"] - changes["short_change"]
        current = current.merge(changes, on="symbol", how="left")
        mismatched_change = current["change_date"].notna() & current["change_date"].ne(current["position_date"])
        current.loc[mismatched_change, ["long_change", "short_change", "net_change", "active_brokers"]] = np.nan
    for column in ("long_change", "short_change", "net_change", "active_brokers"):
        if column not in current:
            current[column] = 0.0
        current[column] = current[column].fillna(0)

    # Never let demo history leak into a real as-of change. Prefer adjacent real
    # aggregate observations; for a one-point series use the published rank changes.
    current["delta_net_1d"] = current["position_delta"].combine_first(current["net_change"]).fillna(0)

    current["name"] = current["symbol"].map(lambda s: SYMBOL_META.get(s, (s, "其他", ""))[0])
    current["sector"] = current["symbol"].map(lambda s: SYMBOL_META.get(s, (s, "其他", ""))[1])
    current["asof_date"] = pd.to_datetime(current.get("position_date", current["trade_date"]))
    current["stale_days"] = current["asof_date"].map(lambda x: (selected_date - x.date()).days)
    current["gross_position"] = current["top20_long"] + current["top20_short"]
    def zscore(series: pd.Series) -> pd.Series:
        spread = series.std(ddof=0)
        return (series - series.mean()) / spread if spread and not np.isnan(spread) else pd.Series(0.0, index=series.index)

    current["bull_score"] = (
        zscore(current["net_position_ratio"]) * 0.5
        + zscore(current["delta_net_1d"]) * 0.3
        + zscore(current["consensus"].fillna(0)) * 0.2
    )
    current["signal"] = np.select(
        [
            ~current["consensus_available"].fillna(False),
            (current["net_position_ratio"] > 0) & (current["consensus"] > 0),
            (current["net_position_ratio"] < 0) & (current["consensus"] < 0),
        ],
        ["仅汇总数据", "共同净多", "共同净空"],
        default="机构分歧",
    )
    return current.sort_values(["sector", "symbol"]).reset_index(drop=True)


def signed(value: float, digits: int = 1) -> str:
    return f"{value:+,.{digits}f}"


def section_title(number: str, title: str, note: str) -> str:
    return (
        '<div class="section-head">'
        f'<span class="section-no">{escape(number)}</span><h2>{escape(title)}</h2>'
        f'<span class="section-note">{escape(note)}</span></div>'
    )


def _marker(value: float, low: float, high: float, color: str) -> str:
    position = float(np.clip((value - low) / (high - low) * 100, 2, 98))
    return f'<span class="scale-dot" style="left:{position:.1f}%;background:{color}"></span>'


def sector_cards(snapshot: pd.DataFrame, lang: str = "zh") -> str:
    cards = []
    for sector, group in snapshot.groupby("sector", sort=True):
        ratio = float(group["net_position_ratio"].mean() * 100)
        change = float(group["delta_net_1d"].sum() / 10_000)
        consensus_values = group["consensus"].dropna()
        consensus = float(consensus_values.mean() * 100) if not consensus_values.empty else np.nan
        consensus_text = signed(consensus) if pd.notna(consensus) else "—"
        strongest = group.loc[group["bull_score"].idxmax(), "symbol"]
        weakest = group.loc[group["bull_score"].idxmin(), "symbol"]
        sector_label = sector_name(sector, lang)
        count_label = f"{len(group)} instruments · Strong {strongest} / Weak {weakest}" if lang == "en" else f"{len(group)} 个品种 · 强 {strongest} / 弱 {weakest}"
        net_label, change_label, consistency_label = (
            ("Net", "Change", "Consensus") if lang == "en" else ("净仓", "变化", "一致性")
        )
        change_suffix = "10k" if lang == "en" else "万"
        cards.append(
            '<div class="sector-card">'
            f'<div><h3>{escape(sector_label)}</h3><small>{escape(count_label)}</small></div>'
            '<div class="sector-values">'
            f'<span>{net_label}<b>{signed(ratio)}</b></span><span>{change_label}<b>{signed(change)}{change_suffix}</b></span>'
            f'<span>{consistency_label}<b>{consensus_text}</b></span></div>'
            '<div class="direction-scale"><i></i>'
            f'{_marker(ratio, -15, 15, BLUE)}{_marker(change, -15, 15, GOLD)}'
            f'{_marker(consensus, -100, 100, TEAL) if pd.notna(consensus) else ""}</div>'
            f'<div class="scale-legend"><span>{net_label}</span><span>{change_label}</span><span>{consistency_label}</span></div></div>'
        )
    return '<div class="sector-grid">' + "".join(cards) + "</div>"


def _points(values: pd.Series, width: int = 150, height: int = 34) -> str:
    clean = pd.to_numeric(values, errors="coerce").dropna().tail(34)
    if len(clean) < 2:
        return ""
    lo, hi = float(clean.min()), float(clean.max())
    spread = hi - lo or 1.0
    coords = []
    for index, value in enumerate(clean):
        x = index / (len(clean) - 1) * width
        y = height - (float(value) - lo) / spread * (height - 6) - 3
        coords.append(f"{x:.1f},{y:.1f}")
    return " ".join(coords)


def sparkline_svg(position_values: pd.Series, price_values: pd.Series, lang: str = "zh") -> str:
    position_points = _points(position_values)
    price_points = _points(price_values)
    if not position_points and not price_points:
        return f'<span class="muted">{"Insufficient history" if lang == "en" else "历史不足"}</span>'
    return (
        '<svg class="spark" viewBox="0 0 150 34" preserveAspectRatio="none">'
        '<line x1="0" y1="17" x2="150" y2="17" stroke="#d9dfe2" stroke-dasharray="2 3"/>'
        f'<polyline points="{price_points}" fill="none" stroke="{GOLD}" stroke-width="1.5"/>'
        f'<polyline points="{position_points}" fill="none" stroke="{BLUE}" stroke-width="1.8"/>'
        '</svg>'
    )


def _signed_bar(value: float, scale: float, color: str) -> str:
    width = min(abs(value) / max(scale, 1) * 47, 47)
    side = "left:50%" if value >= 0 else "right:50%"
    return (
        '<div class="microbar"><i></i>'
        f'<span style="{side};width:{width:.1f}%;background:{color}"></span></div>'
    )


def panorama_table(
    snapshot: pd.DataFrame,
    position_history: pd.DataFrame,
    contracts: pd.DataFrame,
    lang: str = "zh",
) -> str:
    max_net = max(float(snapshot["net_position"].abs().max()), 1)
    max_delta = max(float(snapshot["delta_net_1d"].abs().max()), 1)
    rows = []
    for row in snapshot.sort_values("bull_score", ascending=False).itertuples(index=False):
        ph = position_history[position_history["symbol"].eq(row.symbol)].sort_values("trade_date")
        px = contracts[
            contracts["symbol"].eq(row.symbol) & contracts["source"].ne("demo") & contracts["close"].gt(0)
        ].sort_values("trade_date").drop_duplicates("trade_date", keep="last")
        spark = sparkline_svg(ph["net_position_ratio"], px["close"], lang)
        gauge_pos = float(np.clip((row.net_position_ratio + 0.15) / 0.30 * 100, 2, 98))
        stale_text = f"{row.stale_days}d stale" if lang == "en" else f"滞后 {row.stale_days} 天"
        stale = f'<span class="stale">{stale_text}</span>' if row.stale_days else ""
        display_name = instrument_name(row.symbol, lang, row.name)
        display_sector = sector_name(row.sector, lang)
        trend_key = "— Net　— Price" if lang == "en" else "— 净仓　— 价格"
        lots_unit = "10k lots" if lang == "en" else "万手"
        short_unit = "10k" if lang == "en" else "万"
        consensus_text = f"{row.consensus:+.0%}" if pd.notna(row.consensus) else "—"
        rows.append(
            '<div class="pano-row">'
            f'<div class="instrument"><b>{escape(display_name)}</b><span>{escape(display_sector) if lang == "zh" else f"{row.symbol} · {escape(display_sector)}"}</span>{stale}</div>'
            f'<div>{spark}<small class="spark-key">{trend_key}</small></div>'
            f'<div class="gross"><b>{row.gross_position / 10_000:,.1f}</b><span>{lots_unit}</span></div>'
            '<div class="ratio-gauge"><i></i>'
            f'<span style="left:{gauge_pos:.1f}%"></span><b>{row.net_position_ratio:+.1%}</b></div>'
            f'<div class="bar-cell">{_signed_bar(row.net_position, max_net, BLUE)}<b>{row.net_position / 10_000:+.1f}{short_unit}</b></div>'
            f'<div class="bar-cell">{_signed_bar(row.delta_net_1d, max_delta, GOLD)}<b>{row.delta_net_1d / 10_000:+.1f}{short_unit}</b></div>'
            f'<div class="consensus"><b>{consensus_text}</b><span>{escape(signal_name(row.signal, lang))}</span></div>'
            '</div>'
        )
    labels = (
        ("Instrument", "Net / Price Trend", "Top 20 Gross", "Net Strength", "Net Position", "1-Day Change", "Consensus")
        if lang == "en"
        else ("核心品种", "净仓 / 价格趋势", "前20名体量", "净仓强度", "净持仓", "当日变化", "席位一致性")
    )
    header = '<div class="pano-head">' + "".join(f"<span>{label}</span>" for label in labels) + "</div>"
    return '<div class="panorama">' + header + "".join(rows) + "</div>"


def key_change_cards(snapshot: pd.DataFrame, limit: int = 8, lang: str = "zh") -> str:
    selected = snapshot.reindex(snapshot["net_change"].abs().sort_values(ascending=False).index).head(limit)
    scale = max(float(selected[["long_change", "short_change", "net_change"]].abs().max().max()), 1)
    cards = []
    for row in selected.itertuples(index=False):
        lines = []
        line_labels = ("Long Change", "Short Change", "Net Change") if lang == "en" else ("多头增减", "空头增减", "净变化")
        unit = "10k" if lang == "en" else "万"
        for label, value, color in zip(line_labels, (row.long_change, row.short_change, row.net_change), (BLUE, GOLD, TEAL)):
            lines.append(
                f'<div class="change-line"><span>{label}</span>{_signed_bar(value, scale, color)}'
                f'<b>{value / 10_000:+.1f}{unit}</b></div>'
            )
        cards.append(
            '<div class="change-card">'
            f'<h3>{escape(instrument_name(row.symbol, lang, row.name))} {f"<small>{row.symbol}</small>" if lang == "en" else ""}</h3>'
            f'<p>{"Top 20" if lang == "en" else "前20名"} {row.gross_position / 10_000:,.1f} {"10k lots" if lang == "en" else "万手"} · {escape(signal_name(row.signal, lang))}</p>'
            + "".join(lines) + '</div>'
        )
    return '<div class="change-grid">' + "".join(cards) + "</div>"
