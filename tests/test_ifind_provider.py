from datetime import date

import pandas as pd
import pytest

from crawler import ifind_provider


def test_member_rankings_join_broker_not_row_and_exclude_totals():
    raw = pd.DataFrame({"p00745_f005": ["中信期货(代客)", "合计值"],
                        "p00745_f006": ["100", "100"], "p00745_f008": ["5", "5"],
                        "p00745_f009": ["永安期货(代客)", "合计值"],
                        "p00745_f010": ["80", "80"], "p00745_f012": ["-3", "-3"]})
    result = ifind_provider.normalize_member_ranking(raw, "DCE", date(2026, 9, 4), "I2701")
    assert len(result) == 2
    assert result.long_position.sum() == 100
    assert result.short_position.sum() == 80
    assert result.set_index("broker").loc["中信期货", "short_position"] == 0
    assert set(result.source) == {"ifind-member-ranking"}


def test_member_missing_value_is_not_zero():
    raw = pd.DataFrame({"p00745_f005": ["中信期货"], "p00745_f006": ["--"],
                        "p00745_f008": ["5"], "p00745_f009": ["永安期货"],
                        "p00745_f010": ["80"], "p00745_f012": ["-3"]})
    with pytest.raises(ifind_provider.IFindError, match="多头排名数值缺失.*持仓 1 行"):
        ifind_provider.normalize_member_ranking(raw, "DCE", date(2026, 9, 4), "I2701")


def test_crude_oil_uses_ine():
    assert ifind_provider.ifind_code("SC2610", "SHFE") == "SC2610.INE"


def test_energy_exchange_and_cffex_codes():
    assert ifind_provider.ifind_code("EC2610", "SHFE") == "EC2610.INE"
    assert ifind_provider.ifind_code("IF2609", "CFFEX") == "IF2609.CFE"


def test_financial_rankings_calculate_adjacent_day_changes():
    current = pd.DataFrame({"p02122_f005": ["中信期货"], "p02122_f006": [110],
                            "p02122_f008": ["国泰君安"], "p02122_f009": [80]})
    previous = pd.DataFrame({"p02122_f005": ["中信期货"], "p02122_f006": [100],
                             "p02122_f008": ["国泰君安"], "p02122_f009": [90]})
    result = ifind_provider.normalize_financial_ranking(
        current, previous, "p02122", date(2026, 9, 4), "IF2609"
    )
    assert result.long_change.sum() == 10
    assert result.short_change.sum() == -10
    assert set(result.exchange) == {"CFFEX"}


def test_ifind_exchange_codes():
    assert ifind_provider.ifind_code("RB2609", "SHFE") == "RB2609.SHF"
    assert ifind_provider.ifind_code("M2609", "DCE") == "M2609.DCE"
    assert ifind_provider.ifind_code("MA609", "CZCE") == "MA609.CZC"
    assert ifind_provider.ifind_code("LC2609", "GFEX") == "LC2609.GFE"


def test_enrich_contracts_keeps_partial_fallback_lineage(monkeypatch):
    base = pd.DataFrame([
        {"trade_date": pd.Timestamp("2026-08-28"), "exchange": "SHFE", "symbol": "RB",
         "contract": "RB2609", "close": 1, "open_interest": 1, "volume": 1,
         "is_main": True, "source": "official-via-akshare"},
        {"trade_date": pd.Timestamp("2026-08-28"), "exchange": "SHFE", "symbol": "RB",
         "contract": "RB2610", "close": 2, "open_interest": 2, "volume": 2,
         "is_main": False, "source": "official-via-akshare"},
    ])

    monkeypatch.setattr(ifind_provider, "_history", lambda *_: [{
        "thscode": "RB2609.SHF", "time": ["2026-08-28"],
        "table": {"close": [3065], "volume": [3346], "openInterest": [4940]},
    }])

    result = ifind_provider.enrich_contracts(base, date(2026, 8, 28))

    assert result.loc[result["contract"].eq("RB2609"), "source"].iloc[0] == "ifind-http"
    assert result.loc[result["contract"].eq("RB2610"), "source"].iloc[0] == "official-via-akshare"
    assert result.loc[result["contract"].eq("RB2609"), "is_main"].iloc[0]


def test_enrich_contracts_updates_only_quotes_for_requested_date(monkeypatch):
    base = pd.DataFrame([
        {"trade_date": pd.Timestamp("2026-08-21"), "exchange": "DCE", "symbol": "P",
         "contract": "P2701", "close": 1, "open_interest": 1, "volume": 1,
         "is_main": True, "source": "sina-fallback"},
    ])
    monkeypatch.setattr(ifind_provider, "_history", lambda *_: [{
        "thscode": "P2701.DCE", "time": ["2026-08-21", "2026-09-01"],
        "table": {"close": [10160, 10220], "volume": [10, 20], "openInterest": [30, 40]},
    }])

    result = ifind_provider.enrich_contracts(base, date(2026, 9, 1))

    assert result.iloc[0]["trade_date"] == pd.Timestamp("2026-09-01")
    assert result.iloc[0]["close"] == 10220
    assert result.iloc[0]["source"] == "ifind-http"


def test_ifind_price_history_excludes_observation_date(monkeypatch):
    captured = {}

    def fake_history(codes, start_date, end_date):
        captured.update(codes=codes, start=start_date, end=end_date)
        return [{
            "thscode": "M2609.DCE", "time": ["2026-08-27", "2026-08-28"],
            "table": {"close": [3300, 3312], "volume": [10, 20], "openInterest": [30, 40]},
        }]

    monkeypatch.setattr(ifind_provider, "_history", fake_history)
    result = ifind_provider.fetch_price_history("M2609", "DCE", date(2026, 8, 29))

    assert captured["codes"] == ["M2609.DCE"]
    assert captured["end"] == date(2026, 8, 28)
    assert result["source"].eq("ifind-price-history").all()
    assert result["close"].tolist() == [3300, 3312]


def test_quota_error_switches_to_backup_account_once(monkeypatch):
    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    calls = []

    def fake_post(url, headers, **kwargs):
        if url.endswith("get_access_token"):
            account = headers["refresh_token"]
            calls.append(("auth", account))
            return Response({"errorcode": 0, "data": {"access_token": account + "-access"}})
        access = headers["access_token"]
        calls.append(("data", access))
        if access == "primary-access":
            return Response({"errorcode": 1, "errmsg": "your usage of data has exceeded this month"})
        return Response({"errorcode": 0, "tables": []})

    monkeypatch.setattr(ifind_provider, "_refresh_tokens", lambda: ["primary", "backup"])
    monkeypatch.setattr(ifind_provider.requests, "post", fake_post)
    ifind_provider._access_tokens.clear()
    monkeypatch.setattr(ifind_provider, "_active_account_index", 0)

    result = ifind_provider._post("data_pool", {"reportname": "test"})

    assert result["errorcode"] == 0
    assert calls == [
        ("auth", "primary"),
        ("data", "primary-access"),
        ("auth", "backup"),
        ("data", "backup-access"),
    ]
