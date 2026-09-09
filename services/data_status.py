from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from config import SYMBOL_META

SOURCE_PRIORITY = {
    "ifind-member-ranking": 4,
    "official-via-akshare": 3,
    "sina-fallback": 2,
}


def _latest_by_symbol(frame: pd.DataFrame, selected_date: date, kind: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["symbol", f"{kind}_date", f"{kind}_source"])
    current = frame[
        frame["source"].ne("demo") & frame["trade_date"].dt.date.le(selected_date)
    ].copy()
    if current.empty:
        return pd.DataFrame(columns=["symbol", f"{kind}_date", f"{kind}_source"])
    current["priority"] = current["source"].map(SOURCE_PRIORITY).fillna(1)
    sort_columns = ["symbol", "trade_date"]
    if kind == "price" and "open_interest" in current:
        sort_columns.append("open_interest")
    sort_columns.append("priority")
    current = current.sort_values(sort_columns).drop_duplicates(
        "symbol", keep="last"
    )
    columns = ["symbol", "trade_date", "source"]
    if kind == "price" and "open_interest" in current:
        columns.append("open_interest")
    return current[columns].rename(
        columns={"trade_date": f"{kind}_date", "source": f"{kind}_source",
                 "open_interest": "latest_open_interest"}
    )


def _business_lag(actual: object, expected: date) -> int | None:
    if pd.isna(actual):
        return None
    actual_date = pd.Timestamp(actual).date()
    if actual_date >= expected:
        return 0
    return int(np.busday_count(actual_date.isoformat(), expected.isoformat()))


def build_current_coverage(
    contracts: pd.DataFrame,
    positions: pd.DataFrame,
    selected_date: date,
    expected_date: date,
) -> pd.DataFrame:
    """One current-status row per configured futures product."""
    expected = pd.DataFrame([
        {"symbol": symbol, "name": name, "sector": sector, "exchange": exchange}
        for symbol, (name, sector, exchange) in SYMBOL_META.items()
    ])
    price = _latest_by_symbol(contracts, selected_date, "price")
    ranking = _latest_by_symbol(positions, selected_date, "position")
    result = expected.merge(price, on="symbol", how="left").merge(ranking, on="symbol", how="left")
    result["price_lag"] = result["price_date"].map(lambda value: _business_lag(value, expected_date))
    result["position_lag"] = result["position_date"].map(lambda value: _business_lag(value, expected_date))

    def status(row: pd.Series) -> str:
        if pd.isna(row["price_date"]) and pd.isna(row["position_date"]):
            return "暂无数据"
        if pd.isna(row["position_date"]):
            if pd.notna(row.get("latest_open_interest")) and row["latest_open_interest"] <= 0:
                return "无活跃主力合约"
            return "暂无席位排名"
        if row["position_lag"] and row["position_lag"] > 0:
            return f"席位延迟 {int(row['position_lag'])} 个交易日"
        if pd.isna(row["price_date"]):
            return "暂无行情"
        if row["price_lag"] and row["price_lag"] > 0:
            return f"行情延迟 {int(row['price_lag'])} 个交易日"
        return "最新"

    result["status"] = result.apply(status, axis=1)
    result["reason"] = result["status"].map({
        "暂无数据": "目录存在，但当日未返回行情与席位记录",
        "暂无席位排名": "当日有活跃行情，但 iFinD/交易所未返回会员排名",
        "无活跃主力合约": "当日持仓量为零，无法选取主力合约",
        "暂无行情": "席位存在，但当日行情不可用",
        "最新": "行情与席位均达到数据基准日",
    }).fillna("存在交易日延迟")
    return result


def historical_source_coverage(frame: pd.DataFrame) -> pd.DataFrame:
    """Source history is audit evidence, not the current freshness state."""
    real = frame[frame["source"].ne("demo")]
    if real.empty:
        return pd.DataFrame(columns=["exchange", "source", "first_date", "last_date", "rows"])
    return real.groupby(["exchange", "source"], as_index=False).agg(
        first_date=("trade_date", "min"), last_date=("trade_date", "max"),
        rows=("symbol", "size"), products=("symbol", "nunique"),
    )
