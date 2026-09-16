from __future__ import annotations

import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path
from threading import Lock
from typing import Any

import pandas as pd
import requests
import tomllib
from tenacity import retry, stop_after_attempt, wait_exponential

from config import ROOT, SYMBOL_META
from pipeline.clean import (
    canonical_broker,
    is_valid_broker,
    numeric,
    symbol_from_contract,
)

IFIND_SOURCE = "ifind-http"
IFIND_HISTORY_SOURCE = "ifind-price-history"
_BASE_URL = "https://quantapi.51ifind.com/api/v1"
_SUFFIX = {"SHFE": "SHF", "DCE": "DCE", "CZCE": "CZC", "GFEX": "GFE", "CFFEX": "CFE"}
_INE_SYMBOLS = {"BC", "EC", "LU", "NR", "SC"}
_access_tokens: dict[int, tuple[str, float]] = {}
_active_account_index = 0
_account_lock = Lock()
_ACCESS_TOKEN_CACHE_SECONDS = 6 * 24 * 60 * 60


class IFindError(RuntimeError):
    """Raised when an authenticated iFinD request cannot provide usable data."""


def _refresh_tokens() -> list[str]:
    """Load primary and backup refresh tokens without exposing them to logs."""
    tokens = [
        os.getenv("IFIND_REFRESH_TOKEN", "").strip(),
        os.getenv("IFIND_BACKUP_REFRESH_TOKEN", "").strip(),
    ]
    secrets_path = Path(ROOT) / ".streamlit" / "secrets.toml"
    if secrets_path.exists():
        try:
            config = tomllib.loads(secrets_path.read_text(encoding="utf-8"))["ifind"]
            tokens.extend([
                str(config.get("refresh_token", "")).strip(),
                str(config.get("backup_refresh_token", "")).strip(),
            ])
            configured_list = config.get("refresh_tokens", [])
            if isinstance(configured_list, list):
                tokens.extend(str(token).strip() for token in configured_list)
        except (KeyError, TypeError, tomllib.TOMLDecodeError) as exc:
            raise IFindError("iFinD secrets.toml 格式无效") from exc
    unique = list(dict.fromkeys(token for token in tokens if token))
    if not unique:
        raise IFindError("未配置 iFinD refresh token")
    return unique


def _refresh_token() -> str:
    """Return the active account token for backward compatibility."""
    tokens = _refresh_tokens()
    return tokens[min(_active_account_index, len(tokens) - 1)]


def is_configured() -> bool:
    try:
        _refresh_tokens()
    except IFindError:
        return False
    return True


def _get_access_token() -> tuple[str, int]:
    global _active_account_index
    with _account_lock:
        tokens = _refresh_tokens()
        _active_account_index = min(_active_account_index, len(tokens) - 1)
        account_index = _active_account_index
        cached = _access_tokens.get(account_index)
        if cached and time.monotonic() - cached[1] < _ACCESS_TOKEN_CACHE_SECONDS:
            return cached[0], account_index
        try:
            response = requests.post(
                f"{_BASE_URL}/get_access_token",
                headers={"refresh_token": tokens[account_index]},
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise IFindError(f"iFinD 鉴权请求失败: {exc}") from exc
        data = payload.get("data") or {}
        token = data.get("access_token") or data.get("accessToken") or payload.get("access_token")
        if payload.get("errorcode") != 0 or not token:
            raise IFindError(f"iFinD 鉴权失败: {payload.get('errmsg') or payload.get('errorcode')}")
        _access_tokens[account_index] = (str(token), time.monotonic())
        return str(token), account_index


def _is_quota_error(message: object) -> bool:
    normalized = str(message or "").lower()
    return any(term in normalized for term in (
        "usage of data has exceeded", "quota", "额度", "用量", "超限", "超过",
    ))


def _activate_backup_account(failed_index: int) -> bool:
    """Atomically move to the next account after an explicit quota error."""
    global _active_account_index
    with _account_lock:
        tokens = _refresh_tokens()
        if _active_account_index != failed_index:
            return True  # Another request already performed the switch.
        if failed_index + 1 >= len(tokens):
            return False
        _active_account_index = failed_index + 1
        return True


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=6), reraise=True)
def _post(endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
    while True:
        access_token, account_index = _get_access_token()
        try:
            response = requests.post(
                f"{_BASE_URL}/{endpoint}",
                headers={
                    "Content-Type": "application/json",
                    "access_token": access_token,
                    "ifindlang": "cn",
                },
                json=body,
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise IFindError(f"iFinD 数据请求失败: {exc}") from exc
        if payload.get("errorcode") == 0:
            return payload
        message = payload.get("errmsg") or payload.get("errorcode")
        if _is_quota_error(message) and _activate_backup_account(account_index):
            continue
        raise IFindError(f"iFinD 返回错误: {message}")


def ifind_code(contract: str, exchange: str) -> str:
    suffix = _SUFFIX.get(exchange)
    if symbol_from_contract(contract) in _INE_SYMBOLS:
        suffix = "INE"
    if suffix is None:
        raise IFindError(f"iFinD 不支持交易所 {exchange}")
    return f"{str(contract).upper()}.{suffix}"


IFIND_POSITION_SOURCE = "ifind-member-ranking"
_EXCHANGE_NAMES = {"SHFE": "上海期货交易所", "DCE": "大连商品交易所",
                   "CZCE": "郑州商品交易所", "GFEX": "广州期货交易所",
                   "CFFEX": "中国金融期货交易所"}


def _report(report: str, params: dict, fields: list[int]) -> pd.DataFrame:
    payload = _post("data_pool", {"reportname": report, "functionpara": params,
                    "outputpara": ",".join(f"{report}_f{i:03d}" for i in fields)})
    frames = [pd.DataFrame(t["table"]) for t in payload.get("tables", []) if t.get("table")]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def normalize_member_ranking(raw: pd.DataFrame, exchange: str, trade_date: date,
                             contract: str) -> pd.DataFrame:
    """p00745 has independent long/short Top20 lists, not aligned broker rows."""
    sides = []
    for side, name, amount, change in (("long", 5, 6, 8), ("short", 9, 10, 12)):
        side_label = "多头" if side == "long" else "空头"
        fields = [f"p00745_f{i:03d}" for i in (name, amount, change)]
        if not set(fields).issubset(raw.columns):
            missing = ", ".join(sorted(set(fields) - set(raw.columns)))
            raise IFindError(f"iFinD {side_label}排名缺少字段：{missing}")
        frame = raw[fields].copy()
        frame.columns = ["broker", f"{side}_position", f"{side}_change"]
        frame = frame[frame["broker"].map(is_valid_broker)].head(20).copy()
        if frame.empty:
            raise IFindError(
                f"iFinD {side_label}排名无有效会员（原始返回 {len(raw)} 行）"
            )
        frame["broker"] = frame["broker"].map(canonical_broker)
        for column in frame.columns[1:]:
            frame[column] = pd.to_numeric(frame[column].astype(str).str.replace(",", "", regex=False), errors="coerce")
        missing_counts = frame.iloc[:, 1:].isna().sum()
        if int(missing_counts.sum()):
            raise IFindError(
                f"iFinD {side_label}排名数值缺失：持仓 {int(missing_counts.iloc[0])} 行、"
                f"变化 {int(missing_counts.iloc[1])} 行（有效会员 {len(frame)} 行）"
            )
        if (frame[f"{side}_position"] < 0).any():
            raise IFindError(f"iFinD {side_label}排名出现负持仓数值")
        sides.append(frame.groupby("broker", as_index=False).sum())
    result = sides[0].merge(sides[1], on="broker", how="outer").fillna(0)
    result["trade_date"], result["exchange"] = pd.Timestamp(trade_date), exchange
    result["symbol"], result["contract"] = symbol_from_contract(contract), contract
    result["rank"], result["source"] = range(1, len(result) + 1), IFIND_POSITION_SOURCE
    return result


def normalize_financial_ranking(
    current: pd.DataFrame,
    previous: pd.DataFrame,
    report: str,
    trade_date: date,
    contract: str,
) -> pd.DataFrame:
    """Normalize CFFEX interval ranking; daily changes are adjacent-day differences."""
    sides = []
    for side, name, amount in (("long", 5, 6), ("short", 8, 9)):
        name_field, amount_field = f"{report}_f{name:03d}", f"{report}_f{amount:03d}"

        def side_frame(
            raw: pd.DataFrame,
            value_name: str,
            name_field: str = name_field,
            amount_field: str = amount_field,
        ) -> pd.DataFrame:
            if not {name_field, amount_field}.issubset(raw.columns):
                raise IFindError("iFinD 中金所会员排名缺少多空字段")
            frame = raw[[name_field, amount_field]].copy()
            frame.columns = ["broker", value_name]
            frame = frame[frame["broker"].map(is_valid_broker)].head(20)
            frame["broker"] = frame["broker"].map(canonical_broker)
            frame[value_name] = pd.to_numeric(frame[value_name], errors="coerce")
            if frame.empty or frame[value_name].isna().any() or (frame[value_name] < 0).any():
                raise IFindError("iFinD 中金所会员排名为空或数值缺失")
            return frame.groupby("broker", as_index=False)[value_name].sum()

        today = side_frame(current, f"{side}_position")
        prior = side_frame(previous, "previous")
        merged = today.merge(prior, on="broker", how="left").fillna({"previous": 0})
        merged[f"{side}_change"] = merged[f"{side}_position"] - merged["previous"]
        sides.append(merged.drop(columns="previous"))
    result = sides[0].merge(sides[1], on="broker", how="outer").fillna(0)
    result["trade_date"], result["exchange"] = pd.Timestamp(trade_date), "CFFEX"
    result["symbol"], result["contract"] = symbol_from_contract(contract), contract
    result["rank"], result["source"] = range(1, len(result) + 1), IFIND_POSITION_SOURCE
    return result


def _previous_trade_date(exchange: str, trade_date: date) -> date:
    payload = _post("get_trade_dates", {
        "marketcode": exchange,
        "functionpara": {"dateType": "0", "period": "D", "offset": "-1",
                         "dateFormat": "0", "output": "sequencedate"},
        "startdate": trade_date.isoformat(),
    })
    values = (payload.get("tables") or {}).get("time") or []
    previous = [pd.Timestamp(value).date() for value in values if pd.Timestamp(value).date() < trade_date]
    if not previous:
        raise IFindError("iFinD 未返回上一交易日")
    return max(previous)


def _contract_universe(exchange: str, ds: str) -> pd.DataFrame:
    requests_to_make = [(_EXCHANGE_NAMES[exchange], "0")]
    if exchange == "SHFE":
        requests_to_make.append((_EXCHANGE_NAMES["CFFEX"], "1"))  # EC is grouped in this topic.
    elif exchange == "CFFEX":
        requests_to_make = [(_EXCHANGE_NAMES[exchange], "1"), (_EXCHANGE_NAMES[exchange], "2")]
    frames = []
    for exchange_name, product_type in requests_to_make:
        frames.append(_report("p02939", {"date": ds, "edate": ds,
                      "p0": exchange_name, "type": product_type}, [1, 2, 3]))
    return pd.concat(frames, ignore_index=True).drop_duplicates()


def _financial_quotes(rows: list[dict[str, Any]], trade_date: date) -> pd.DataFrame:
    """Use iFinD's financial-futures reports when quotation entitlement is absent."""
    ds = trade_date.strftime("%Y%m%d")

    def fetch_quote(row: dict[str, Any]) -> dict[str, Any] | None:
        contract = row["contract"]
        symbol = row["symbol"]
        month = int(contract[len(symbol) + 2:])
        report = "p02945" if symbol in {"T", "TF", "TL", "TS"} else "p02944"
        raw = _report(report, {"sdate": ds, "edate": ds,
                      "jys": _EXCHANGE_NAMES["CFFEX"], "pz": symbol,
                      "hyyf": f"{month}月"}, [2, 4, 9, 14, 16])
        if raw.empty:
            return None
        item = raw.iloc[-1]
        result = row.copy()
        result.update({
            "trade_date": pd.Timestamp(item[f"{report}_f004"]),
            "contract": str(item[f"{report}_f002"]).split(".")[0].upper(),
            "close": float(item[f"{report}_f009"]),
            "open_interest": float(item[f"{report}_f014"]),
            "volume": float(item[f"{report}_f016"]),
            "source": IFIND_SOURCE,
        })
        return result

    quotes = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(fetch_quote, row) for row in rows]
        for future in as_completed(futures):
            try:
                result = future.result()
                if result is not None:
                    quotes.append(result)
            except IFindError:
                continue
    if not quotes:
        raise IFindError("iFinD 中金所专题行情为空")
    frame = pd.DataFrame(quotes).drop_duplicates("contract")
    frame["is_main"] = False
    valid = frame[frame["open_interest"].gt(0)]
    if not valid.empty:
        frame.loc[valid.groupby("symbol")["open_interest"].idxmax(), "is_main"] = True
    return frame


def fetch_daily(
    exchange: str,
    trade_date: date,
    symbols: set[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Discover contracts and fetch quotes first; retrieve each symbol's main-contract ranks.

    Report IDs/parameters come from iFinD's official SuperCommand commodity futures
    page (futures_00546). p00744 is *new entrants*, not the full ranking: use p00745.
    """
    ds = trade_date.strftime("%Y%m%d")
    universe = _contract_universe(exchange, ds)
    rows, identifiers = [], {}
    for item in universe.to_dict("records"):
        identifier = str(item["p02939_f003"])
        symbol = identifier.split(";")[0].upper()
        if symbol not in SYMBOL_META or SYMBOL_META[symbol][2] != exchange:
            continue
        if symbols is not None and symbol not in symbols:
            continue
        name = str(item["p02939_f001"])
        match = re.search(r"(\d{4})$", name)
        if not match:
            continue
        expiry = match.group(1)
        contract = symbol + (expiry[1:] if exchange == "CZCE" else expiry)
        identifiers[contract] = (identifier, name)
        rows.append({"trade_date": pd.Timestamp(trade_date), "exchange": exchange,
                     "symbol": symbol, "contract": contract, "close": float("nan"),
                     "volume": float("nan"), "open_interest": float("nan"),
                     "is_main": False, "source": "unverified"})
    if not rows:
        raise IFindError("iFinD 合约目录为空")
    quotes = _financial_quotes(rows, trade_date) if exchange == "CFFEX" else enrich_contracts(pd.DataFrame(rows), trade_date)
    quotes = quotes[quotes["source"].eq(IFIND_SOURCE)].copy()
    if quotes.empty:
        raise IFindError("iFinD 当日行情为空")
    positions, warnings = [], []

    def fetch_ranking(item):
        identifier, name = identifiers[item.contract]
        if exchange == "CFFEX":
            report = "p02424" if item.symbol in {"T", "TF", "TL", "TS"} else "p02122"
            previous_date = _previous_trade_date(exchange, trade_date)
            fields = [5, 6, 8, 9]
            current = _report(report, {"sdate": ds, "edate": ds,
                              "type": identifier, "p0": name}, fields)
            previous_ds = previous_date.strftime("%Y%m%d")
            previous = _report(report, {"sdate": previous_ds, "edate": previous_ds,
                               "type": identifier, "p0": name}, fields)
            return normalize_financial_ranking(current, previous, report, trade_date, item.contract)
        raw = _report("p00745", {"p0": identifier, "date": ds, "hycode": name}, [5, 6, 8, 9, 10, 12])
        return normalize_member_ranking(raw, exchange, trade_date, item.contract)

    main_rows = list(quotes[quotes["is_main"]].itertuples())
    with ThreadPoolExecutor(max_workers=min(6, max(len(main_rows), 1))) as executor:
        futures = {executor.submit(fetch_ranking, item): item for item in main_rows}
        for future in as_completed(futures):
            item = futures[future]
            try:
                positions.append(future.result())
            except IFindError as exc:
                warnings.append(f"{item.symbol}: {exc}")
    if not positions and symbols is None:
        raise IFindError("iFinD 会员排名不可用：" + "；".join(warnings))
    position_frame = (
        pd.concat(positions, ignore_index=True)
        if positions else
        pd.DataFrame(columns=[
            "trade_date", "exchange", "symbol", "contract", "broker",
            "long_position", "short_position", "long_change", "short_change",
            "rank", "source",
        ])
    )
    return quotes, position_frame, warnings


def fetch_position_history_bundle(
    contract: str, exchange: str, start: date, end: date,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return aggregate and member-level Top20 history for one fixed contract."""
    if exchange == "CFFEX":
        raise IFindError("中金所历史排名采用独立报表，当前仅保存每日更新快照")
    ds = end.strftime("%Y%m%d")
    universe = _contract_universe(exchange, ds)
    symbol = symbol_from_contract(contract)
    expiry = contract[len(symbol):]
    if len(expiry) == 3:
        expiry = str(end.year)[2] + expiry
    matches = universe[universe["p02939_f003"].str.startswith(symbol + ";")
                       & universe["p02939_f001"].str.endswith(expiry)]
    if len(matches) != 1:
        raise IFindError(f"iFinD 无法唯一定位历史合约 {contract}")
    item = matches.iloc[0]
    raw = _report("p02940", {"date": start.strftime("%Y%m%d"), "edate": ds,
                  "p0": item["p02939_f003"], "type": item["p02939_f001"]}, [8, 9, 10, 12, 13, 14, 23])
    if raw.empty:
        raise IFindError(f"iFinD {contract} 历史排名为空")
    rows, member_rows = [], []
    for day, group in raw.groupby("p02940_f023"):
        actual = pd.Timestamp(day).date()
        if not start <= actual <= end:
            continue
        mapped = group.rename(columns={f"p02940_f{a:03d}": f"p00745_f{b:03d}"
                                       for a, b in ((8, 5), (9, 6), (10, 8), (12, 9), (13, 10), (14, 12))})
        try:
            positions = normalize_member_ranking(mapped, exchange, actual, contract)
        except IFindError:
            continue
        positions["source"] = "ifind-member-position-history"
        member_rows.append(positions)
        long, short = positions.long_position.sum(), positions.short_position.sum()
        rows.append({"trade_date": pd.Timestamp(actual), "exchange": exchange, "symbol": symbol,
                     "contract": contract, "top20_long": long, "top20_short": short,
                     "net_position": long - short, "net_position_ratio": (long-short)/(long+short) if long+short else 0,
                     "source": "ifind-position-history"})
    if not rows:
        raise IFindError(f"iFinD {contract} 历史排名无有效记录")
    return pd.DataFrame(rows), pd.concat(member_rows, ignore_index=True)


def fetch_position_history(contract: str, exchange: str, start: date, end: date) -> pd.DataFrame:
    """Actual Top20 aggregate history for one fixed contract."""
    aggregate, _ = fetch_position_history_bundle(contract, exchange, start, end)
    return aggregate


def fetch_cffex_member_position_history(
    contract: str, start: date, end: date,
) -> pd.DataFrame:
    """Backfill one fixed CFFEX contract without stitching main-contract rolls."""
    universe = _contract_universe("CFFEX", end.strftime("%Y%m%d"))
    symbol = symbol_from_contract(contract)
    expiry = contract[len(symbol):]
    matches = universe[
        universe["p02939_f003"].str.startswith(symbol + ";")
        & universe["p02939_f001"].str.endswith(expiry)
    ]
    if len(matches) != 1:
        raise IFindError(f"iFinD 无法唯一定位中金所历史合约 {contract}")
    item = matches.iloc[0]
    identifier, name = str(item["p02939_f003"]), str(item["p02939_f001"])
    report = "p02424" if symbol in {"T", "TF", "TL", "TS"} else "p02122"
    fields = [5, 6, 8, 9]
    rows = []
    for stamp in pd.bdate_range(start, end):
        actual = stamp.date()
        try:
            previous = _previous_trade_date("CFFEX", actual)
            current_raw = _report(report, {
                "sdate": actual.strftime("%Y%m%d"), "edate": actual.strftime("%Y%m%d"),
                "type": identifier, "p0": name,
            }, fields)
            previous_raw = _report(report, {
                "sdate": previous.strftime("%Y%m%d"), "edate": previous.strftime("%Y%m%d"),
                "type": identifier, "p0": name,
            }, fields)
            frame = normalize_financial_ranking(
                current_raw, previous_raw, report, actual, contract
            )
            frame["source"] = "ifind-member-position-history"
            rows.append(frame)
        except IFindError:
            continue
    if not rows:
        raise IFindError(f"iFinD {contract} 中金所固定合约历史排名为空")
    return pd.concat(rows, ignore_index=True)


def _history(codes: list[str], start_date: date, end_date: date) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    for offset in range(0, len(codes), 80):
        payload = _post(
            "cmd_history_quotation",
            {
                "codes": ",".join(codes[offset:offset + 80]),
                "indicators": "close,volume,openInterest",
                "startdate": start_date.isoformat(),
                "enddate": end_date.isoformat(),
                "functionpara": {"Fill": "Omit", "Interval": "D"},
            },
        )
        chunk = payload.get("tables") or []
        if not isinstance(chunk, list):
            raise IFindError("iFinD 历史行情返回结构异常")
        tables.extend(chunk)
    return tables


def _table_frame(item: dict[str, Any]) -> pd.DataFrame:
    times = item.get("time") or []
    table = item.get("table") or {}
    if not times or not isinstance(table, dict):
        return pd.DataFrame()
    result = pd.DataFrame({"trade_date": pd.to_datetime(times)})
    for target, source in (("close", "close"), ("volume", "volume"), ("open_interest", "openInterest")):
        values = table.get(source)
        result[target] = numeric(pd.Series(values)) if isinstance(values, list) else float("nan")
    return result.dropna(subset=["close"])


def enrich_contracts(base: pd.DataFrame, trade_date: date) -> pd.DataFrame:
    """Replace discoverable daily quotes with iFinD values, preserving row-level lineage."""
    if base.empty:
        return base.copy()
    exchange = str(base.iloc[0]["exchange"])
    code_to_contract = {
        ifind_code(str(contract), exchange): str(contract).upper() for contract in base["contract"].unique()
    }
    tables = _history(list(code_to_contract), trade_date, trade_date)
    updates: dict[str, dict[str, float]] = {}
    for item in tables:
        contract = code_to_contract.get(str(item.get("thscode", "")).upper())
        frame = _table_frame(item)
        if not frame.empty:
            frame = frame[frame["trade_date"].dt.date.eq(trade_date)]
        if contract and not frame.empty:
            row = frame.iloc[-1]
            updates[contract] = {
                "close": float(row["close"]),
                "volume": float(row["volume"]),
                "open_interest": float(row["open_interest"]),
            }
    if not updates:
        raise IFindError(f"iFinD 未返回 {exchange} {trade_date} 目标合约行情")
    result = base.copy()
    for index, row in result.iterrows():
        values = updates.get(str(row["contract"]).upper())
        if values and all(pd.notna(value) for value in values.values()):
            for column, value in values.items():
                result.at[index, column] = value
            result.at[index, "trade_date"] = pd.Timestamp(trade_date)
            result.at[index, "source"] = IFIND_SOURCE
    result["is_main"] = False
    valid = result[result["open_interest"].gt(0)]
    if not valid.empty:
        result.loc[valid.groupby("symbol")["open_interest"].idxmax(), "is_main"] = True
    return result


def fetch_price_history(contract: str, exchange: str, end_date: date, periods: int = 60) -> pd.DataFrame:
    """Fetch actual iFinD daily prices strictly before ``end_date``."""
    final_date = end_date - timedelta(days=1)
    start_date = final_date - timedelta(days=max(periods * 2, 120))
    code = ifind_code(contract, exchange)
    tables = _history([code], start_date, final_date)
    item = next((value for value in tables if str(value.get("thscode", "")).upper() == code), None)
    frame = _table_frame(item or {}).tail(periods).copy()
    if frame.empty:
        raise IFindError(f"iFinD 缺少 {contract} 截至 {final_date} 的价格历史")
    frame["exchange"] = exchange
    frame["symbol"] = symbol_from_contract(contract)
    frame["contract"] = str(contract).upper()
    frame["is_main"] = True
    frame["source"] = IFIND_HISTORY_SOURCE
    return frame[[
        "trade_date", "exchange", "symbol", "contract", "close", "open_interest", "volume", "is_main", "source"
    ]]
