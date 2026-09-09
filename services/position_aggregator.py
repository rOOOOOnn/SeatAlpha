from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd

from services.broker_classifier import enrich_broker_classification
from services.signal_engine import (
    classify_three_way,
    cross_section_zscore,
    signal_label,
)
from settings.broker_classification import CATEGORY_ORDER

GROUP_KEYS = ["trade_date", "exchange", "symbol", "contract", "broker_category"]


def aggregate_category_positions(positions: pd.DataFrame) -> pd.DataFrame:
    """Aggregate one identical contract/date population into seat categories."""
    columns = GROUP_KEYS + [
        "long_position", "short_position", "long_change", "short_change", "net_position",
        "net_change", "long_short_ratio", "consistency", "broker_count",
    ]
    if positions.empty:
        return pd.DataFrame(columns=columns)
    frame = enrich_broker_classification(positions)
    frame["broker_net_change"] = frame["long_change"] - frame["short_change"]
    grouped = frame.groupby(GROUP_KEYS, as_index=False, observed=True).agg(
        long_position=("long_position", "sum"), short_position=("short_position", "sum"),
        long_change=("long_change", "sum"), short_change=("short_change", "sum"),
        bullish=("broker_net_change", lambda s: int((s > 0).sum())),
        bearish=("broker_net_change", lambda s: int((s < 0).sum())),
        broker_count=("broker_name_normalized", "nunique"),
    )
    grouped["net_position"] = grouped["long_position"] - grouped["short_position"]
    grouped["net_change"] = grouped["long_change"] - grouped["short_change"]
    grouped["long_short_ratio"] = grouped["long_position"] / grouped["short_position"].replace(0, np.nan)
    grouped["consistency"] = (
        (grouped["bullish"] - grouped["bearish"])
        / (grouped["bullish"] + grouped["bearish"]).replace(0, np.nan)
    ).fillna(0)
    return grouped[columns]


def build_three_category_snapshot(
    positions: pd.DataFrame, base_snapshot: pd.DataFrame, selected_date
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return configured category rows and one wide row per visible instrument."""
    if positions.empty or base_snapshot.empty:
        return pd.DataFrame(), pd.DataFrame()
    visible = base_snapshot[["symbol", "contract", "sector", "name", "close", "price_date"]].copy()
    visible = visible.rename(columns={"contract": "selected_contract"})
    eligible = positions[
        positions["trade_date"].dt.date.le(selected_date)
        & positions["source"].ne("demo")
        & positions["symbol"].isin(visible["symbol"])
    ].copy()
    if eligible.empty:
        return pd.DataFrame(), pd.DataFrame()
    eligible["latest_date"] = eligible.groupby("symbol")["trade_date"].transform("max")
    eligible = eligible[eligible["trade_date"].eq(eligible["latest_date"])]
    eligible = eligible.merge(visible[["symbol", "selected_contract"]], on="symbol", how="inner")
    eligible["gross_row"] = eligible["long_position"].abs() + eligible["short_position"].abs()
    contract_size = eligible.groupby(["symbol", "contract"], as_index=False)["gross_row"].sum()
    contract_size = contract_size.merge(
        visible[["symbol", "selected_contract"]], on="symbol", how="left"
    )
    contract_size["is_selected"] = contract_size["contract"].eq(contract_size["selected_contract"])
    chosen = contract_size.sort_values(
        ["symbol", "is_selected", "gross_row"], ascending=[True, False, False]
    ).drop_duplicates("symbol")[["symbol", "contract"]]
    # Prefer the dashboard's selected main contract. If an aggregate-only row
    # has no matching contract, choose exactly one largest latest rank contract.
    eligible = eligible.merge(chosen, on=["symbol", "contract"], how="inner")
    aggregated = aggregate_category_positions(eligible)
    main = aggregated[aggregated["broker_category"].isin(CATEGORY_ORDER)].copy()
    universe = pd.MultiIndex.from_product(
        [visible["symbol"].unique(), CATEGORY_ORDER], names=["symbol", "broker_category"]
    ).to_frame(index=False)
    main = universe.merge(main, on=["symbol", "broker_category"], how="left")
    main = main.merge(visible, on="symbol", how="left")
    main["contract"] = main["contract"].fillna(main["selected_contract"])
    for column in ("long_position", "short_position", "long_change", "short_change", "net_position", "net_change", "consistency", "broker_count"):
        main[column] = pd.to_numeric(main[column], errors="coerce").fillna(0)
    gross = (main["long_position"] + main["short_position"]).replace(0, np.nan)
    main["normalized_net_position"] = (main["net_position"] / gross).fillna(0)
    main["normalized_net_change"] = (main["net_change"] / gross).fillna(0)
    main["raw_signal"] = (
        .55 * main["normalized_net_position"]
        + .30 * main["normalized_net_change"]
        + .15 * main["consistency"]
    )
    main["signal_score"] = main.groupby("broker_category")["raw_signal"].transform(cross_section_zscore)
    main["signal_label"] = main["signal_score"].map(signal_label)
    wide = main.pivot(index="symbol", columns="broker_category", values=[
        "net_position", "net_change", "consistency", "signal_score", "long_position", "short_position",
    ])
    wide.columns = [f"{category}_{measure.replace('signal_score', 'signal')}" for measure, category in wide.columns]
    wide = wide.reset_index().merge(visible, on="symbol", how="left")
    for category in CATEGORY_ORDER:
        if f"{category}_signal" not in wide:
            wide[f"{category}_signal"] = 0.0
    wide["qk_inst_divergence"] = wide["qian_kun_signal"] - wide["institution_signal"]
    wide["qk_retail_divergence"] = wide["qian_kun_signal"] - wide["retail_signal"]
    wide["inst_retail_divergence"] = wide["institution_signal"] - wide["retail_signal"]
    divergence_columns = []
    for left, right in combinations(CATEGORY_ORDER, 2):
        column = f"{left}_{right}_divergence"
        wide[column] = wide[f"{left}_signal"] - wide[f"{right}_signal"]
        divergence_columns.append(column)
    wide["divergence_score"] = wide[divergence_columns].abs().max(axis=1)
    resonance = wide.apply(classify_three_way, axis=1)
    wide["three_way_consensus"] = [item[0] for item in resonance]
    wide["three_way_state"] = [item[1] for item in resonance]
    return main, wide
