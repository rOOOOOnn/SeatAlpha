from __future__ import annotations

import numpy as np
import pandas as pd


def _zscore(series: pd.Series) -> pd.Series:
    std = series.std(ddof=0)
    return (series - series.mean()) / std if std and not np.isnan(std) else pd.Series(0.0, index=series.index)


def calculate_metrics(contracts: pd.DataFrame, positions: pd.DataFrame) -> pd.DataFrame:
    columns = ["trade_date", "exchange", "symbol", "contract", "close", "open_interest", "top20_long", "top20_short",
               "net_position", "net_position_ratio", "delta_net_1d", "delta_net_5d", "delta_net_20d", "price_change_1d",
               "consensus", "bull_score", "divergence_score"]
    if contracts.empty or positions.empty:
        return pd.DataFrame(columns=columns)
    pos = positions.copy()
    pos["net_change"] = pos["long_change"] - pos["short_change"]
    agg = pos.groupby(["trade_date", "exchange", "symbol", "contract"], as_index=False).agg(
        top20_long=("long_position", "sum"), top20_short=("short_position", "sum"),
        bullish=("net_change", lambda s: int((s > 0).sum())), bearish=("net_change", lambda s: int((s < 0).sum())))
    base = contracts[contracts["is_main"]].merge(agg, on=["trade_date", "exchange", "symbol", "contract"], how="inner")
    if base.empty:
        base = contracts.merge(agg, on=["trade_date", "exchange", "symbol", "contract"], how="inner")
    base = base.sort_values(["symbol", "trade_date"])
    base["net_position"] = base["top20_long"] - base["top20_short"]
    denom = (base["top20_long"] + base["top20_short"]).replace(0, np.nan)
    base["net_position_ratio"] = (base["net_position"] / denom).fillna(0)
    base["consensus"] = ((base["bullish"] - base["bearish"]) / (base["bullish"] + base["bearish"]).replace(0, np.nan)).fillna(0)
    grouped = base.groupby("symbol", group_keys=False)
    for days in (1, 5, 20):
        base[f"delta_net_{days}d"] = grouped["net_position"].diff(days).fillna(0)
    base["price_change_1d"] = grouped["close"].pct_change(fill_method=None).fillna(0)
    base["bull_score"] = base.groupby("trade_date")["net_position_ratio"].transform(_zscore) * 0.5
    base["bull_score"] += base.groupby("trade_date")["delta_net_5d"].transform(_zscore) * 0.3
    base["bull_score"] += base.groupby("trade_date")["consensus"].transform(_zscore) * 0.2
    base["divergence_score"] = -np.sign(base["price_change_1d"]) * np.sign(base["delta_net_5d"]) * (
        base["price_change_1d"].abs() * base["delta_net_5d"].abs().pow(0.5))
    return base[columns].reset_index(drop=True)
