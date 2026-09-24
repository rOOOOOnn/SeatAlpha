from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.clean import is_valid_broker
from services.broker_classifier import classify_broker
from services.broker_normalizer import normalize_broker_name

FORWARD_HORIZONS = (5, 10, 20)
LOOKBACK_DAYS = 365
MIN_SAMPLE_DAYS = 20

RESULT_COLUMNS = [
    "broker",
    "broker_category",
    "win_rate",
    "sample_days",
    "sample_observations",
    "average_directional_return",
    "first_date",
    "last_date",
    "current_long_position",
    "current_short_position",
    "current_net_position",
    *[f"win_rate_{h}d" for h in FORWARD_HORIZONS],
    *[f"samples_{h}d" for h in FORWARD_HORIZONS],
]


def _empty_results() -> pd.DataFrame:
    return pd.DataFrame(columns=RESULT_COLUMNS)


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.replace(",", "", regex=False), errors="coerce"
    )


def ranking_file_for_symbol(root: Path, symbol: str) -> Path | None:
    """Find a validated top-level manual export and ignore archived failed copies."""
    base = root / "data" / "ifind_manual" / "raw" / "member_rankings"
    exact: list[Path] = []
    fallback: list[Path] = []
    for exchange_dir in sorted(path for path in base.iterdir() if path.is_dir()):
        candidate = exchange_dir / f"{symbol}.xlsx"
        if candidate.exists():
            exact.append(candidate)
        fallback.extend(sorted(exchange_dir.glob(f"{symbol}_ALL_*.xlsx")))
    candidates = exact or fallback
    return candidates[0] if candidates else None


def parse_manual_ranking_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Parse the stable first-sheet layout of an iFinD position-ranking export."""
    required_columns = 27
    if frame.empty or frame.shape[1] < required_columns:
        return pd.DataFrame(columns=["trade_date", "broker", "net_position", "close"])

    dates = pd.to_datetime(frame.iloc[:, 0], errors="coerce", format="mixed")
    prices = pd.DataFrame({
        "trade_date": dates,
        "close": _numeric(frame.iloc[:, 26]),
    }).dropna(subset=["trade_date", "close"])
    prices = prices[prices["close"].gt(0)].groupby("trade_date", as_index=False)["close"].last()

    sides: list[pd.DataFrame] = []
    for side, broker_column, position_column in (
        ("long", 7, 8),
        ("short", 12, 13),
    ):
        values = pd.DataFrame({
            "trade_date": dates,
            "broker": frame.iloc[:, broker_column],
            f"{side}_position": _numeric(frame.iloc[:, position_column]),
        }).dropna(subset=["trade_date", f"{side}_position"])
        values["broker"] = values["broker"].map(normalize_broker_name)
        values = values[
            values["broker"].map(is_valid_broker)
            & values[f"{side}_position"].ge(0)
        ]
        values = values.groupby(["trade_date", "broker"], as_index=False)[f"{side}_position"].sum()
        sides.append(values)

    if not sides or all(side.empty for side in sides):
        return pd.DataFrame(columns=["trade_date", "broker", "net_position", "close"])
    positions = sides[0].merge(sides[1], on=["trade_date", "broker"], how="outer").fillna(0)
    positions["net_position"] = positions["long_position"] - positions["short_position"]
    return positions.merge(prices, on="trade_date", how="inner").sort_values(
        ["trade_date", "broker"]
    ).reset_index(drop=True)


def load_manual_ranking_history(path: Path) -> pd.DataFrame:
    frame = pd.read_excel(path, sheet_name=0, header=None)
    return parse_manual_ranking_frame(frame)


def calculate_win_rates(
    history: pd.DataFrame,
    as_of,
    *,
    lookback_days: int = LOOKBACK_DAYS,
    min_sample_days: int = MIN_SAMPLE_DAYS,
) -> pd.DataFrame:
    """Rank each broker by pooled 5/10/20-day directional hit rate.

    A signal is the sign of that broker's published net position for the product.
    Each horizon uses the product's next available trading observations. Missing
    dates and horizons are excluded rather than counted as losses or zero returns.
    """
    if history.empty:
        return _empty_results()
    required = {"trade_date", "broker", "net_position", "close"}
    if not required.issubset(history.columns):
        raise ValueError(f"win-rate history is missing columns: {sorted(required - set(history.columns))}")

    cutoff = pd.Timestamp(as_of).normalize()
    start = cutoff - pd.Timedelta(days=lookback_days)
    data = history.copy()
    data["trade_date"] = pd.to_datetime(data["trade_date"], errors="coerce").dt.normalize()
    data["net_position"] = pd.to_numeric(data["net_position"], errors="coerce")
    data["close"] = pd.to_numeric(data["close"], errors="coerce")
    data = data.dropna(subset=["trade_date", "broker", "net_position", "close"])
    data = data[
        data["trade_date"].le(cutoff)
        & data["close"].gt(0)
        & data["net_position"].ne(0)
    ]
    if data.empty:
        return _empty_results()

    prices = data.groupby("trade_date", as_index=False)["close"].last().sort_values("trade_date")
    for horizon in FORWARD_HORIZONS:
        prices[f"future_close_{horizon}d"] = prices["close"].shift(-horizon)
    signals = data.drop(columns="close").merge(prices, on="trade_date", how="inner")
    signals = signals[signals["trade_date"].ge(start)].copy()
    if signals.empty:
        return _empty_results()

    observations: list[pd.DataFrame] = []
    horizon_summaries: list[pd.DataFrame] = []
    direction = np.sign(signals["net_position"])
    for horizon in FORWARD_HORIZONS:
        future = f"future_close_{horizon}d"
        valid = signals[future].notna() & signals[future].gt(0)
        evaluated = signals.loc[valid, ["trade_date", "broker"]].copy()
        if evaluated.empty:
            continue
        evaluated["horizon"] = horizon
        evaluated["directional_return"] = (
            direction.loc[valid]
            * (signals.loc[valid, future] / signals.loc[valid, "close"] - 1.0)
        )
        evaluated["win"] = evaluated["directional_return"].gt(0).astype(int)
        observations.append(evaluated)
        horizon_summary = evaluated.groupby("broker", as_index=False).agg(
            wins=("win", "sum"), samples=("win", "size")
        )
        horizon_summary[f"win_rate_{horizon}d"] = (
            horizon_summary["wins"] / horizon_summary["samples"]
        )
        horizon_summary = horizon_summary.rename(columns={"samples": f"samples_{horizon}d"})
        horizon_summaries.append(
            horizon_summary[["broker", f"win_rate_{horizon}d", f"samples_{horizon}d"]]
        )

    if not observations:
        return _empty_results()
    evaluated = pd.concat(observations, ignore_index=True)
    result = evaluated.groupby("broker", as_index=False).agg(
        wins=("win", "sum"),
        sample_observations=("win", "size"),
        sample_days=("trade_date", "nunique"),
        average_directional_return=("directional_return", "mean"),
        first_date=("trade_date", "min"),
        last_date=("trade_date", "max"),
    )
    result["win_rate"] = result["wins"] / result["sample_observations"]
    for summary in horizon_summaries:
        result = result.merge(summary, on="broker", how="left")
    for horizon in FORWARD_HORIZONS:
        rate_column = f"win_rate_{horizon}d"
        sample_column = f"samples_{horizon}d"
        if rate_column not in result:
            result[rate_column] = np.nan
            result[sample_column] = 0

    latest = data.sort_values("trade_date").groupby("broker", as_index=False).tail(1).copy()
    if "long_position" not in latest:
        latest["long_position"] = np.nan
    if "short_position" not in latest:
        latest["short_position"] = np.nan
    latest = latest[["broker", "long_position", "short_position", "net_position"]].rename(
        columns={
            "long_position": "current_long_position",
            "short_position": "current_short_position",
            "net_position": "current_net_position",
        }
    )
    result = result.merge(latest, on="broker", how="left")
    result["broker_category"] = result["broker"].map(classify_broker)
    result = result[result["sample_days"].ge(min_sample_days)].copy()
    if result.empty:
        return _empty_results()
    result = result.sort_values(
        ["broker_category", "win_rate", "sample_days", "average_directional_return", "broker"],
        ascending=[True, False, False, False, True],
    )
    return result[RESULT_COLUMNS].reset_index(drop=True)


def load_symbol_win_rates(root: Path, symbol: str, as_of) -> tuple[pd.DataFrame, Path | None]:
    path = ranking_file_for_symbol(root, symbol)
    if path is None:
        return _empty_results(), None
    history = load_manual_ranking_history(path)
    return calculate_win_rates(history, as_of), path
