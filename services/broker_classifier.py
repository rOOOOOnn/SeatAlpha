from __future__ import annotations

import pandas as pd

from services.broker_normalizer import normalize_broker_name
from settings.broker_classification import CATEGORY_ORDER, SEAT_CLASSIFICATION

_CATEGORY_BY_BROKER = {
    broker: category
    for category, brokers in SEAT_CLASSIFICATION.items()
    for broker in brokers
}


def classify_broker(value: object) -> str:
    return _CATEGORY_BY_BROKER.get(normalize_broker_name(value), "other")


def enrich_broker_classification(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["broker_name_normalized"] = result["broker"].map(normalize_broker_name)
    result["broker_category"] = result["broker_name_normalized"].map(
        lambda value: _CATEGORY_BY_BROKER.get(value, "other")
    )
    return result


def unclassified_brokers(frame: pd.DataFrame) -> list[str]:
    if frame.empty:
        return []
    enriched = enrich_broker_classification(frame)
    return sorted(enriched.loc[enriched["broker_category"].eq("other"), "broker_name_normalized"].unique())


def category_options() -> tuple[str, ...]:
    return CATEGORY_ORDER

