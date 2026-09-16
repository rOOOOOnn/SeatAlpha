from __future__ import annotations

import numpy as np
import pandas as pd

from settings.broker_classification import CORE_THREE_WAY_ORDER
from settings.signal_thresholds import DIRECTION_THRESHOLDS, SIGNAL_THRESHOLDS


def cross_section_zscore(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").fillna(0.0)
    std = values.std(ddof=0)
    return (values - values.mean()) / std if std and not np.isnan(std) else pd.Series(0.0, index=series.index)


def signal_label(score: float) -> str:
    t = SIGNAL_THRESHOLDS
    if score >= t["strong_long"]:
        return "strong_long"
    if score >= t["long"]:
        return "long"
    if score <= t["strong_short"]:
        return "strong_short"
    if score <= t["short"]:
        return "short"
    return "neutral"


def direction_score(
    net_position: float, gross_position: float, net_change: float = 0.0,
    consistency: float = 0.0,
) -> float:
    """Return an absolute, bounded directional score in [-1, 1]."""
    gross = float(gross_position or 0)
    if gross <= 0:
        return 0.0
    net_ratio = float(np.clip(float(net_position or 0) / gross, -1, 1))
    change_ratio = float(np.clip(float(net_change or 0) / gross, -1, 1))
    vote = float(np.clip(float(consistency or 0), -1, 1))
    return .55 * net_ratio + .30 * change_ratio + .15 * vote


def direction_label(score: float) -> str:
    t = DIRECTION_THRESHOLDS
    if score >= t["strong_long"]:
        return "strong_long"
    if score >= t["long"]:
        return "long"
    if score <= t["strong_short"]:
        return "strong_short"
    if score <= t["short"]:
        return "short"
    return "neutral"


def classify_three_way(row: pd.Series) -> tuple[int, str]:
    scores = [
        float(row.get(f"{category}_direction", row.get(f"{category}_signal", 0)) or 0)
        for category in CORE_THREE_WAY_ORDER
    ]
    directions = [
        1 if value >= DIRECTION_THRESHOLDS["long"]
        else -1 if value <= DIRECTION_THRESHOLDS["short"] else 0
        for value in scores
    ]
    qk, inst, retail = directions
    if qk == inst == retail == 1:
        return (2 if min(scores) >= DIRECTION_THRESHOLDS["strong_long"] else 1), "three_long"
    if qk == inst == retail == -1:
        return (-2 if max(scores) <= DIRECTION_THRESHOLDS["strong_short"] else -1), "three_short"
    if qk == inst != 0 and retail == -qk:
        return 0, "qk_inst_vs_retail"
    if qk == retail != 0 and inst == -qk:
        return 0, "qk_retail_vs_inst"
    if inst == retail != 0 and qk == -inst:
        return 0, "inst_retail_vs_qk"
    if qk == inst == retail == 0:
        return 0, "neutral"
    return 0, "high_divergence"
