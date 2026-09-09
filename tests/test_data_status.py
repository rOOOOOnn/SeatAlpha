from datetime import date

import pandas as pd

from config import SYMBOL_META
from services.data_status import build_current_coverage


def test_full_futures_catalog_is_configured():
    assert len(SYMBOL_META) == 90
    assert {"RB", "I", "EC", "IF", "TL", "PS"}.issubset(SYMBOL_META)


def test_old_fallback_does_not_override_new_ifind_status():
    contracts = pd.DataFrame([
        {"symbol": "I", "trade_date": pd.Timestamp("2026-09-04"), "source": "ifind-http"}
    ])
    positions = pd.DataFrame([
        {"symbol": "I", "trade_date": pd.Timestamp("2026-08-21"), "source": "sina-fallback"},
        {"symbol": "I", "trade_date": pd.Timestamp("2026-09-04"), "source": "ifind-member-ranking"},
    ])
    result = build_current_coverage(contracts, positions, date(2026, 9, 7), date(2026, 9, 4))
    iron = result[result["symbol"].eq("I")].iloc[0]
    assert iron["status"] == "最新"
    assert iron["position_source"] == "ifind-member-ranking"
