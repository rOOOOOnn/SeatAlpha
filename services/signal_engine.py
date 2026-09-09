from __future__ import annotations

import numpy as np
import pandas as pd

from settings.broker_classification import CORE_THREE_WAY_ORDER
from settings.signal_thresholds import SIGNAL_THRESHOLDS


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


def classify_three_way(row: pd.Series) -> tuple[int, str]:
    scores = [float(row.get(f"{category}_signal", 0) or 0) for category in CORE_THREE_WAY_ORDER]
    directions = [1 if value >= .25 else -1 if value <= -.25 else 0 for value in scores]
    qk, inst, retail = directions
    if qk == inst == retail == 1:
        return (2 if min(scores) >= 1 else 1), "three_long"
    if qk == inst == retail == -1:
        return (-2 if max(scores) <= -1 else -1), "three_short"
    if qk == inst != 0 and retail == -qk:
        return 0, "qk_inst_vs_retail"
    if qk == retail != 0 and inst == -qk:
        return 0, "qk_retail_vs_inst"
    if inst == retail != 0 and qk == -inst:
        return 0, "inst_retail_vs_qk"
    if qk == inst == retail == 0:
        return 0, "neutral"
    return 0, "high_divergence"
