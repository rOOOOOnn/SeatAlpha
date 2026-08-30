from __future__ import annotations

from html import escape

import numpy as np
import pandas as pd

from config import SYMBOL_META

INK = "#17222b"
MUTED = "#73808a"
TEAL = "#2b7d75"
BLUE = "#426b88"
GOLD = "#a78331"
ROSE = "#b45f6a"
GRID = "#dfe5e7"


def build_snapshot(
    metrics: pd.DataFrame,
    positions: pd.DataFrame,
    position_history: pd.DataFrame,
    selected_date,
    selected_sectors: list[str],
) -> pd.DataFrame:
    """Build one honest as-of row per symbol from the latest real observation."""
    eligible = metrics[(metrics["trade_date"].dt.date.le(selected_date)) & metrics["source"].ne("demo")].copy()
    eligible["sector"] = eligible["symbol"].map(lambda s: SYMBOL_META.get(s, (s, "其他", ""))[1])
    eligible = eligible[eligible["sector"].isin(selected_sectors)]
    if eligible.empty:
        return eligible
    eligible["latest_date"] = eligible.groupby("symbol")["trade_date"].transform("max")
    current = eligible[eligible["trade_date"].eq(eligible["latest_date"])].copy()
    current = current.sort_values(["symbol", "open_interest"]).drop_duplicates("symbol", keep="last")

    history = position_history[
        position_history["trade_date"].dt.date.le(selected_date) & position_history["symbol"].isin(current["symbol"])
    ].copy()
    if not history.empty:
        history["priority"] = history["source"].eq("official-aggregate-via-akshare").astype(int)
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
            current[target] = current[source].combine_first(current[target])
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
            active_brokers=("broker", "nunique"),
        )
        changes["net_change"] = changes["long_change"] - changes["short_change"]
        current = current.merge(changes, on="symbol", how="left")
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
        + zscore(current["consensus"]) * 0.2
    )
    current["signal"] = np.select(
        [
            (current["net_position_ratio"] > 0) & (current["consensus"] > 0),
            (current["net_position_ratio"] < 0) & (current["consensus"] < 0),
        ],
        ["共同净多", "共同净空"],
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


def sector_cards(snapshot: pd.DataFrame) -> str:
    cards = []
    for sector, group in snapshot.groupby("sector", sort=True):
        ratio = float(group["net_position_ratio"].mean() * 100)
        change = float(group["delta_net_1d"].sum() / 10_000)
        consensus = float(group["consensus"].mean() * 100)
        strongest = group.loc[group["bull_score"].idxmax(), "symbol"]
        weakest = group.loc[group["bull_score"].idxmin(), "symbol"]
        cards.append(
            '<div class="sector-card">'
            f'<div><h3>{escape(sector)}</h3><small>{len(group)} 个品种 · 强 {strongest} / 弱 {weakest}</small></div>'
            '<div class="sector-values">'
            f'<span>净仓<b>{signed(ratio)}</b></span><span>变化<b>{signed(change)}万</b></span>'
            f'<span>一致性<b>{signed(consensus)}</b></span></div>'
            '<div class="direction-scale"><i></i>'
            f'{_marker(ratio, -15, 15, BLUE)}{_marker(change, -15, 15, GOLD)}'
            f'{_marker(consensus, -100, 100, TEAL)}</div>'
            f'<div class="scale-legend"><span>净仓</span><span>变化</span><span>一致性</span></div></div>'
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


def sparkline_svg(position_values: pd.Series, price_values: pd.Series) -> str:
    position_points = _points(position_values)
    price_points = _points(price_values)
    if not position_points and not price_points:
        return '<span class="muted">历史不足</span>'
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


def panorama_table(snapshot: pd.DataFrame, position_history: pd.DataFrame, contracts: pd.DataFrame) -> str:
    max_net = max(float(snapshot["net_position"].abs().max()), 1)
    max_delta = max(float(snapshot["delta_net_1d"].abs().max()), 1)
    rows = []
    for row in snapshot.sort_values("bull_score", ascending=False).itertuples(index=False):
        ph = position_history[position_history["symbol"].eq(row.symbol)].sort_values("trade_date")
        px = contracts[
            contracts["symbol"].eq(row.symbol) & contracts["source"].ne("demo") & contracts["close"].gt(0)
        ].sort_values("trade_date").drop_duplicates("trade_date", keep="last")
        spark = sparkline_svg(ph["net_position_ratio"], px["close"])
        gauge_pos = float(np.clip((row.net_position_ratio + 0.15) / 0.30 * 100, 2, 98))
        stale = f'<span class="stale">滞后 {row.stale_days} 天</span>' if row.stale_days else ""
        rows.append(
            '<div class="pano-row">'
            f'<div class="instrument"><b>{escape(row.name)}</b><span>{row.symbol} · {escape(row.sector)}</span>{stale}</div>'
            f'<div>{spark}<small class="spark-key">— 净仓　— 价格</small></div>'
            f'<div class="gross"><b>{row.gross_position / 10_000:,.1f}</b><span>万手</span></div>'
            '<div class="ratio-gauge"><i></i>'
            f'<span style="left:{gauge_pos:.1f}%"></span><b>{row.net_position_ratio:+.1%}</b></div>'
            f'<div class="bar-cell">{_signed_bar(row.net_position, max_net, BLUE)}<b>{row.net_position / 10_000:+.1f}万</b></div>'
            f'<div class="bar-cell">{_signed_bar(row.delta_net_1d, max_delta, GOLD)}<b>{row.delta_net_1d / 10_000:+.1f}万</b></div>'
            f'<div class="consensus"><b>{row.consensus:+.0%}</b><span>{escape(row.signal)}</span></div>'
            '</div>'
        )
    header = (
        '<div class="pano-head"><span>核心品种</span><span>净仓 / 价格趋势</span><span>Top20体量</span>'
        '<span>净仓强度</span><span>净持仓</span><span>当日变化</span><span>席位一致性</span></div>'
    )
    return '<div class="panorama">' + header + "".join(rows) + "</div>"


def key_change_cards(snapshot: pd.DataFrame, limit: int = 8) -> str:
    selected = snapshot.reindex(snapshot["net_change"].abs().sort_values(ascending=False).index).head(limit)
    scale = max(float(selected[["long_change", "short_change", "net_change"]].abs().max().max()), 1)
    cards = []
    for row in selected.itertuples(index=False):
        lines = []
        for label, value, color in (
            ("多头增减", row.long_change, BLUE), ("空头增减", row.short_change, GOLD), ("净变化", row.net_change, TEAL)
        ):
            lines.append(
                f'<div class="change-line"><span>{label}</span>{_signed_bar(value, scale, color)}'
                f'<b>{value / 10_000:+.1f}万</b></div>'
            )
        cards.append(
            '<div class="change-card">'
            f'<h3>{escape(row.name)} <small>{row.symbol}</small></h3>'
            f'<p>Top20 {row.gross_position / 10_000:,.1f} 万手 · {escape(row.signal)}</p>'
            + "".join(lines) + '</div>'
        )
    return '<div class="change-grid">' + "".join(cards) + "</div>"
