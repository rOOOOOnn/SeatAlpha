from __future__ import annotations

import re

import pandas as pd

from config import BROKER_ALIASES


def canonical_broker(value: object) -> str:
    name = re.sub(r"[（(].*?[）)]", "", str(value or "")).strip()
    name = name.replace("有限公司", "").replace("股份", "").strip()
    return BROKER_ALIASES.get(str(value).strip(), BROKER_ALIASES.get(name, name))


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
