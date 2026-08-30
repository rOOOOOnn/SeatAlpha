from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

from config import DEFAULT_SYMBOLS, SYMBOL_META
from pipeline.clean import canonical_broker, numeric, symbol_from_contract


class ProviderError(RuntimeError):
    pass


def _ak():
    try:
        import akshare as ak
    except ImportError as exc:
        raise ProviderError("缺少 akshare，请先安装 requirements.txt") from exc
    return ak


def _column(frame: pd.DataFrame, aliases: tuple[str, ...]) -> str | None:
    normalized = {str(c).lower().replace(" ", "").replace("_", ""): c for c in frame.columns}
    for alias in aliases:
        key = alias.lower().replace(" ", "").replace("_", "")
        if key in normalized:
            return normalized[key]
    return None


def _side(frame: pd.DataFrame, side: str) -> pd.DataFrame:
    if side == "long":
        broker_aliases = ("多头会员简称", "持买单会员简称", "long_party_name", "longbroker", "会员简称")
        pos_aliases = ("多头持仓", "多单持仓", "持买单量", "long_open_interest", "longposition")
        chg_aliases = ("多头增减", "持买单量增减", "比上交易增减", "long_open_interest_chg", "longchange")
    else:
        broker_aliases = ("空头会员简称", "持卖单会员简称", "short_party_name", "shortbroker", "会员简称")
        pos_aliases = ("空头持仓", "空单持仓", "持卖单量", "short_open_interest", "shortposition")
        chg_aliases = ("空头增减", "持卖单量增减", "比上交易增减", "short_open_interest_chg", "shortchange")
    broker_col = _column(frame, broker_aliases)
    pos_col = _column(frame, pos_aliases)
    chg_col = _column(frame, chg_aliases)
    if broker_col is None or pos_col is None:
        return pd.DataFrame(columns=["broker", f"{side}_position", f"{side}_change"])
    out = pd.DataFrame({"broker": frame[broker_col].map(canonical_broker), f"{side}_position": numeric(frame[pos_col]),
                        f"{side}_change": numeric(frame[chg_col]) if chg_col else 0.0})
    out = out[out["broker"].ne("") & ~out["broker"].str.contains("合计")]
    return out.groupby("broker", as_index=False).sum(numeric_only=True)


def normalize_rank_table(raw: pd.DataFrame, exchange: str, trade_date: date, contract: str) -> pd.DataFrame:
    merged = _side(raw, "long").merge(_side(raw, "short"), how="outer", on="broker").fillna(0)
    if merged.empty:
        raise ProviderError(f"{exchange} {contract} 返回字段无法识别: {list(raw.columns)}")
    merged.insert(0, "trade_date", pd.Timestamp(trade_date))
    merged.insert(1, "exchange", exchange)
    merged.insert(2, "symbol", symbol_from_contract(contract))
    merged.insert(3, "contract", str(contract).upper())
    merged["rank"] = range(1, len(merged) + 1)
    merged["source"] = "official-via-akshare"
    return merged


def _normalize_sina_rank(long_raw: pd.DataFrame, short_raw: pd.DataFrame, trade_date: date, contract: str) -> pd.DataFrame:
    merged = _side(long_raw, "long").merge(_side(short_raw, "short"), how="outer", on="broker").fillna(0)
    if merged.empty:
        raise ProviderError(f"新浪备用源 {contract} 未返回席位排名")
    merged.insert(0, "trade_date", pd.Timestamp(trade_date))
    merged.insert(1, "exchange", "DCE")
    merged.insert(2, "symbol", symbol_from_contract(contract))
    merged.insert(3, "contract", contract.upper())
    merged["rank"] = range(1, len(merged) + 1)
    merged["source"] = "sina-fallback"
    return merged


def _as_tables(value: Any) -> dict[str, pd.DataFrame]:
    if isinstance(value, dict):
        return {str(k): v for k, v in value.items() if isinstance(v, pd.DataFrame) and not v.empty}
    if isinstance(value, pd.DataFrame) and not value.empty:
        contract_col = _column(value, ("合约", "contract", "symbol", "合约代码"))
        if contract_col:
            return {str(k): g for k, g in value.groupby(contract_col)}
    return {}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8), reraise=True)
def fetch_positions(exchange: str, trade_date: date, symbols: tuple[str, ...] = DEFAULT_SYMBOLS) -> pd.DataFrame:
    ak = _ak()
    ds = trade_date.strftime("%Y%m%d")
    wanted = [s for s in symbols if SYMBOL_META.get(s, (None, None, None))[2] == exchange]
    if exchange == "SHFE":
        raw = ak.get_shfe_rank_table(date=ds, vars_list=wanted)
    elif exchange == "DCE":
        raw = ak.futures_dce_position_rank(date=ds, vars_list=wanted)
    elif exchange == "CZCE":
        raw = ak.get_rank_table_czce(date=ds)
    elif exchange == "GFEX":
        raw = ak.futures_gfex_position_rank(date=ds, vars_list=wanted)
    else:
        raise ProviderError(f"不支持的交易所: {exchange}")
    frames = [normalize_rank_table(table, exchange, trade_date, contract) for contract, table in _as_tables(raw).items()
              if symbol_from_contract(contract) in wanted]
    if not frames:
        raise ProviderError(f"{exchange} {ds} 未返回目标品种持仓排名")
    return pd.concat(frames, ignore_index=True)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8), reraise=True)
def fetch_contracts(exchange: str, trade_date: date) -> pd.DataFrame:
    raw = _ak().get_futures_daily(start_date=trade_date.strftime("%Y%m%d"), end_date=trade_date.strftime("%Y%m%d"), market=exchange)
    if raw is None or raw.empty:
        raise ProviderError(f"{exchange} {trade_date} 未返回日行情")
    rename = {}
    for target, aliases in {"contract": ("symbol", "合约"), "symbol": ("variety", "品种"), "close": ("close", "收盘价"),
                            "open_interest": ("open_interest", "持仓量"), "volume": ("volume", "成交量")}.items():
        col = _column(raw, aliases)
        if col is not None:
            rename[col] = target
    frame = raw.rename(columns=rename)
    if not {"contract", "close", "open_interest", "volume"}.issubset(frame.columns):
        raise ProviderError(f"{exchange} 行情字段无法识别: {list(raw.columns)}")
    if "symbol" not in frame:
        frame["symbol"] = frame["contract"].map(symbol_from_contract)
    frame["symbol"] = frame["symbol"].astype(str).str.upper()
    frame = frame[frame["symbol"].isin(DEFAULT_SYMBOLS)].copy()
    for col in ("close", "open_interest", "volume"):
        frame[col] = numeric(frame[col])
    frame["trade_date"] = pd.Timestamp(trade_date)
    frame["exchange"] = exchange
    frame["contract"] = frame["contract"].astype(str).str.upper()
    frame["is_main"] = False
    if not frame.empty:
        frame.loc[frame.groupby("symbol")["open_interest"].idxmax(), "is_main"] = True
    frame["source"] = "official-via-akshare"
    return frame[["trade_date", "exchange", "symbol", "contract", "close", "open_interest", "volume", "is_main", "source"]]


DCE_SINA_NAMES = {"M": "豆粕", "I": "铁矿石", "P": "棕榈"}


def _sina_main_contracts() -> dict[str, str]:
    ak = _ak()
    result = {}
    for symbol, name in DCE_SINA_NAMES.items():
        realtime = ak.futures_zh_realtime(symbol=name)
        realtime = realtime[~realtime["symbol"].astype(str).str.endswith("0")].copy()
        realtime["position"] = pd.to_numeric(realtime["position"], errors="coerce").fillna(0)
        if not realtime.empty:
            result[symbol] = str(realtime.nlargest(1, "position").iloc[0]["symbol"]).upper()
    if not result:
        raise ProviderError("新浪备用源未返回大商所主力合约")
    return result


def _latest_sina_rank_date(contract: str, target: date, lookback_days: int = 14) -> date:
    ak = _ak()
    for offset in range(lookback_days + 1):
        candidate = target - timedelta(days=offset)
        if candidate.weekday() >= 5:
            continue
        frame = ak.futures_hold_pos_sina(symbol="多单持仓", contract=contract, date=candidate.strftime("%Y%m%d"))
        if frame is not None and not frame.empty:
            return candidate
    raise ProviderError(f"新浪备用源最近 {lookback_days} 天无 {contract} 席位排名")


def _sina_contract_row(contract: str, symbol: str, trade_date: date) -> dict:
    history = _ak().futures_zh_daily_sina(symbol=contract)
    history["date"] = pd.to_datetime(history["date"]).dt.date
    match = history[history["date"].eq(trade_date)]
    if match.empty:
        raise ProviderError(f"新浪备用源缺少 {contract} {trade_date} 日行情")
    row = match.iloc[-1]
    return {"trade_date": pd.Timestamp(trade_date), "exchange": "DCE", "symbol": symbol, "contract": contract,
            "close": float(row["close"]), "open_interest": float(row["hold"]), "volume": float(row["volume"]),
            "is_main": True, "source": "sina-fallback"}


def fetch_dce_sina_fallback(target: date) -> tuple[pd.DataFrame, pd.DataFrame, date]:
    """Fetch latest available DCE ranks from Sina when DCE's public endpoint rejects the request."""
    ak = _ak()
    main_contracts = _sina_main_contracts()
    probe = main_contracts.get("M") or next(iter(main_contracts.values()))
    actual_date = _latest_sina_rank_date(probe, target)
    contract_rows, position_frames = [], []
    for symbol, contract in main_contracts.items():
        long_raw = ak.futures_hold_pos_sina(symbol="多单持仓", contract=contract, date=actual_date.strftime("%Y%m%d"))
        short_raw = ak.futures_hold_pos_sina(symbol="空单持仓", contract=contract, date=actual_date.strftime("%Y%m%d"))
        if long_raw.empty or short_raw.empty:
            continue
        contract_rows.append(_sina_contract_row(contract, symbol, actual_date))
        position_frames.append(_normalize_sina_rank(long_raw, short_raw, actual_date, contract))
    if not contract_rows or not position_frames:
        raise ProviderError(f"新浪备用源 {actual_date} 未返回完整大商所数据")
    return pd.DataFrame(contract_rows), pd.concat(position_frames, ignore_index=True), actual_date


def fetch_price_history(contract: str, exchange: str, end_date: date, periods: int = 60) -> pd.DataFrame:
    """Backfill actual prices for the selected main contract without inventing position history."""
    request_contract = contract
    if exchange == "CZCE":
        digits = "".join(ch for ch in contract if ch.isdigit())
        letters = symbol_from_contract(contract)
        if len(digits) == 3:
            request_contract = f"{letters}{str(end_date.year)[2]}{digits}"
    raw = _ak().futures_zh_daily_sina(symbol=request_contract)
    raw["date"] = pd.to_datetime(raw["date"])
    raw = raw[raw["date"].dt.date.lt(end_date)].tail(periods).copy()
    if raw.empty:
        return pd.DataFrame()
    return pd.DataFrame({"trade_date": raw["date"], "exchange": exchange, "symbol": symbol_from_contract(contract),
                         "contract": contract, "close": numeric(raw["close"]), "open_interest": numeric(raw["hold"]),
                         "volume": numeric(raw["volume"]), "is_main": True, "source": "sina-price-history"})


def fetch_position_history(exchange: str, start_date: date, end_date: date) -> pd.DataFrame:
    """Fetch exchange-published Top20 variety aggregates for a historical date range."""
    wanted = [symbol for symbol, meta in SYMBOL_META.items() if meta[2] == exchange]
    if not wanted:
        return pd.DataFrame()
    raw = _ak().get_rank_sum_daily(
        start_day=start_date.strftime("%Y%m%d"),
        end_day=end_date.strftime("%Y%m%d"),
        vars_list=wanted,
    )
    if raw is None or raw.empty:
        raise ProviderError(f"{exchange} 未返回品种汇总持仓历史")
    symbol = raw["symbol"].astype(str).str.upper()
    variety = raw["variety"].astype(str).str.upper()
    aggregate = raw[symbol.eq(variety) & variety.isin(wanted)].copy()
    if aggregate.empty:
        # GFEX currently returns contract rows only; its variety aggregate is the sum
        # of published contract-level Top20 values, matching AKShare's other markets.
        contract_rows = raw[variety.isin(wanted)].copy()
        if contract_rows.empty:
            raise ProviderError(f"{exchange} 返回结果缺少目标品种持仓")
        for column in ("long_open_interest_top20", "short_open_interest_top20"):
            contract_rows[column] = numeric(contract_rows[column])
        aggregate = contract_rows.groupby(["date", "variety"], as_index=False)[
            ["long_open_interest_top20", "short_open_interest_top20"]
        ].sum()
        aggregate["symbol"] = aggregate["variety"]
    aggregate = aggregate.reset_index(drop=True)
    aggregate_variety = aggregate["variety"].astype(str).str.upper()
    long_pos = numeric(aggregate["long_open_interest_top20"])
    short_pos = numeric(aggregate["short_open_interest_top20"])
    denominator = (long_pos + short_pos).replace(0, float("nan"))
    result = pd.DataFrame({
        "trade_date": pd.to_datetime(aggregate["date"].astype(str), format="%Y%m%d"),
        "exchange": exchange,
        "symbol": aggregate_variety,
        "contract": aggregate_variety,
        "top20_long": long_pos,
        "top20_short": short_pos,
        "net_position": long_pos - short_pos,
        "net_position_ratio": ((long_pos - short_pos) / denominator).fillna(0),
        "source": "official-aggregate-via-akshare",
    })
    return result.reset_index(drop=True)
