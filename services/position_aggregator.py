from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd

from services.broker_classifier import enrich_broker_classification
from services.signal_engine import (
    classify_three_way,
    cross_section_zscore,
    direction_label,
)
from settings.broker_classification import CATEGORY_ORDER

GROUP_KEYS = ["trade_date", "exchange", "symbol", "contract", "broker_category"]


def aggregate_category_positions(positions: pd.DataFrame) -> pd.DataFrame:
    """Aggregate one identical contract/date population into seat categories."""
    columns = GROUP_KEYS + [
        "long_position", "short_position", "long_change", "short_change", "net_position",
        "net_change", "long_short_ratio", "consistency", "directional_count", "broker_count",
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
    grouped["directional_count"] = grouped["bullish"] + grouped["bearish"]
    return grouped[columns]


def build_three_category_snapshot(
    positions: pd.DataFrame, base_snapshot: pd.DataFrame, selected_date,
    change_period: int = 1,
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
    aggregated["change_available"] = True
    aggregated["change_baseline_date"] = pd.NaT
    if change_period > 1:
        # Compare like-for-like contracts with the latest published snapshot on
        # or before the requested trading-day lookback.  Missing history stays
        # missing instead of being presented as a zero change.
        current_dates = eligible.groupby("symbol")["trade_date"].max()
        baselines = []
        for symbol, current_date in current_dates.items():
            target = current_date - pd.offsets.BDay(change_period)
            contract = chosen.loc[chosen["symbol"].eq(symbol), "contract"].iloc[0]
            candidates = positions[
                positions["symbol"].eq(symbol)
                & positions["contract"].eq(contract)
                & positions["source"].ne("demo")
                & positions["trade_date"].le(target)
            ]
            if not candidates.empty:
                baseline_date = candidates["trade_date"].max()
                baselines.append(candidates[candidates["trade_date"].eq(baseline_date)])
        aggregated[["long_change", "short_change", "net_change", "consistency", "directional_count"]] = np.nan
        aggregated["change_available"] = False
        if baselines:
            baseline = pd.concat(baselines, ignore_index=True)
            current_brokers = enrich_broker_classification(eligible).copy()
            baseline_brokers = enrich_broker_classification(baseline).copy()
            broker_keys = ["symbol", "contract", "broker_category", "broker_name_normalized"]
            current_brokers = current_brokers.groupby(broker_keys, as_index=False).agg(
                current_long=("long_position", "sum"), current_short=("short_position", "sum"),
                trade_date=("trade_date", "max"), exchange=("exchange", "first"),
            )
            baseline_brokers = baseline_brokers.groupby(broker_keys, as_index=False).agg(
                baseline_long=("long_position", "sum"), baseline_short=("short_position", "sum"),
                change_baseline_date=("trade_date", "max"),
            )
            comparison = current_brokers.merge(baseline_brokers, on=broker_keys, how="outer")
            comparison[["current_long", "current_short", "baseline_long", "baseline_short"]] = (
                comparison[["current_long", "current_short", "baseline_long", "baseline_short"]].fillna(0)
            )
            comparison["long_change"] = comparison["current_long"] - comparison["baseline_long"]
            comparison["short_change"] = comparison["current_short"] - comparison["baseline_short"]
            comparison["broker_net_change"] = comparison["long_change"] - comparison["short_change"]
            period = comparison.groupby(["symbol", "contract", "broker_category"], as_index=False).agg(
                long_change=("long_change", "sum"), short_change=("short_change", "sum"),
                bullish=("broker_net_change", lambda s: int((s > 0).sum())),
                bearish=("broker_net_change", lambda s: int((s < 0).sum())),
                change_baseline_date=("change_baseline_date", "max"),
            )
            period["net_change"] = period["long_change"] - period["short_change"]
            period["consistency"] = (
                (period["bullish"] - period["bearish"])
                / (period["bullish"] + period["bearish"]).replace(0, np.nan)
            ).fillna(0)
            period["directional_count"] = period["bullish"] + period["bearish"]
            period["change_available"] = period["change_baseline_date"].notna()
            update_columns = ["symbol", "contract", "broker_category", "long_change", "short_change",
                              "net_change", "consistency", "directional_count", "change_available", "change_baseline_date"]
            aggregated = aggregated.drop(columns=update_columns[3:]).merge(
                period[update_columns], on=["symbol", "contract", "broker_category"], how="left"
            )
    main = aggregated[aggregated["broker_category"].isin(CATEGORY_ORDER)].copy()
    universe = pd.MultiIndex.from_product(
        [visible["symbol"].unique(), CATEGORY_ORDER], names=["symbol", "broker_category"]
    ).to_frame(index=False)
    main = universe.merge(main, on=["symbol", "broker_category"], how="left")
    main = main.merge(visible, on="symbol", how="left")
    main["contract"] = main["contract"].fillna(main["selected_contract"])
    for column in ("long_position", "short_position", "net_position", "broker_count", "directional_count"):
        main[column] = pd.to_numeric(main[column], errors="coerce").fillna(0)
    for column in ("long_change", "short_change", "net_change", "consistency"):
        main[column] = pd.to_numeric(main[column], errors="coerce")
    if change_period == 1:
        main[["long_change", "short_change", "net_change", "consistency", "directional_count"]] = (
            main[["long_change", "short_change", "net_change", "consistency", "directional_count"]].fillna(0)
        )
        main["change_available"] = True
    else:
        main["change_available"] = main["change_available"].eq(True)
    gross = (main["long_position"] + main["short_position"]).replace(0, np.nan)
    main["normalized_net_position"] = (main["net_position"] / gross).fillna(0).clip(-1, 1)
    main["normalized_net_change"] = (
        (main["net_change"] / gross).where(main["change_available"]).fillna(0).clip(-1, 1)
    )
    main["direction_score"] = (
        .55 * main["normalized_net_position"]
        + .30 * main["normalized_net_change"]
        + .15 * main["consistency"].fillna(0)
    )
    main["raw_signal"] = main["direction_score"]
    main["signal_score"] = main.groupby("broker_category")["raw_signal"].transform(cross_section_zscore)
    main["signal_label"] = main["direction_score"].map(direction_label)
    wide = main.pivot(index="symbol", columns="broker_category", values=[
        "net_position", "net_change", "consistency", "signal_score", "direction_score", "long_position", "short_position",
        "change_available", "change_baseline_date",
    ])
    wide.columns = [
        f"{category}_{measure.replace('signal_score', 'signal').replace('direction_score', 'direction')}"
        for measure, category in wide.columns
    ]
    wide = wide.reset_index().merge(visible, on="symbol", how="left")
    for category in CATEGORY_ORDER:
        if f"{category}_signal" not in wide:
            wide[f"{category}_signal"] = 0.0
        for measure in ("net_position", "net_change", "consistency", "signal", "direction", "long_position", "short_position"):
            column = f"{category}_{measure}"
            if column in wide:
                wide[column] = pd.to_numeric(wide[column], errors="coerce")
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
