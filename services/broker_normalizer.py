from __future__ import annotations

import re
import unicodedata

from settings.broker_classification import BROKER_ALIASES

LEGAL_SUFFIXES = ("股份有限公司", "有限责任公司", "有限公司", "股份", "公司")


def normalize_broker_name(value: object) -> str:
    """Normalize exchange variants without guessing an unknown broker identity."""
    raw = unicodedata.normalize("NFKC", str(value or "")).strip()
    raw = re.sub(r"\s+", "", raw)
    direct = BROKER_ALIASES.get(raw)
    if direct:
        return direct
    name = re.sub(r"[（(][^）)]*(?:[）)]|$)", "", raw).strip()
    for suffix in LEGAL_SUFFIXES:
        if name.endswith(suffix):
            name = name[: -len(suffix)].strip()
            break
    return BROKER_ALIASES.get(name, name)

