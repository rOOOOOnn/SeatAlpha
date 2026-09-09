from __future__ import annotations

import re

import pandas as pd

from services.broker_normalizer import normalize_broker_name

INVALID_BROKER_NAMES = frozenset({"", "-", "--", "---", "—", "–", "nan", "none", "null", "合计", "总计"})


def canonical_broker(value: object) -> str:
    """Backward-compatible entry point for provider normalization."""
    return normalize_broker_name(value)


def is_valid_broker(value: object) -> bool:
    """Reject exchange placeholders and totals that are not actual broker seats."""
    name = canonical_broker(value).strip()
    return name.lower() not in INVALID_BROKER_NAMES and "合计" not in name and "总计" not in name


def symbol_from_contract(contract: object) -> str:
    match = re.match(r"([A-Za-z]+)", str(contract).strip())
    return match.group(1).upper() if match else str(contract).upper()


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.replace(",", "", regex=False), errors="coerce").fillna(0)


def classify_behavior(long_change: float, short_change: float) -> str:
    if long_change > 0 and short_change < 0:
        return "强加多"
    if long_change < 0 and short_change > 0:
        return "强加空"
    if long_change > 0 and short_change > 0:
        return "双边扩仓"
    if long_change < 0 and short_change < 0:
        return "双边减仓"
    return "方向不明"
