from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from config import DB_PATH, EXCHANGES
from core.db import connect, init_db, is_empty, query, upsert_frame
from crawler.akshare_provider import (
    fetch_contracts,
    fetch_dce_sina_fallback,
    fetch_position_history,
    fetch_positions,
    fetch_price_history,
)
from metrics.signals import calculate_metrics
from pipeline.seed_demo import seed


def latest_weekday(today: date | None = None) -> date:
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    result = today or now.date()
    while result.weekday() >= 5:
        result -= timedelta(days=1)
    if result == now.date() and now.hour < 16:
        result -= timedelta(days=1)
        while result.weekday() >= 5:
            result -= timedelta(days=1)
    return result


def _log(exchange: str, trade_date: date, status: str, rows: int, message: str, path=DB_PATH,
         source: str = "official-via-akshare") -> None:
    frame = pd.DataFrame([{"attempted_at": pd.Timestamp.now(), "trade_date": pd.Timestamp(trade_date), "exchange": exchange,
                           "status": status, "rows_written": rows, "message": message[:1000], "source": source}])
    with connect(path) as con:
        con.register("log_row", frame)
        con.execute("INSERT INTO update_log SELECT * FROM log_row")


def _backfill_main_prices(path=DB_PATH) -> None:
    mains = query("""
        SELECT * EXCLUDE (rn) FROM (
            SELECT *, row_number() OVER (PARTITION BY symbol ORDER BY trade_date DESC, open_interest DESC) rn
            FROM contracts
            WHERE is_main AND source NOT IN ('demo', 'sina-price-history')
        ) WHERE rn = 1
    """, path=path)
    for row in mains.itertuples(index=False):
        history_end = pd.Timestamp(row.trade_date).date()
        desired_last = history_end - timedelta(days=1)
        if row.source == "sina-fallback":
            desired_last = latest_weekday()
            history_end = desired_last + timedelta(days=1)
        existing = query("SELECT count(*) n, max(trade_date) last_date FROM contracts WHERE contract=? AND exchange=? AND source='sina-price-history'",
                         [row.contract, row.exchange], path)
        last_date = existing.iloc[0]["last_date"]
        if int(existing.iloc[0]["n"]) >= 20 and pd.notna(last_date) and pd.Timestamp(last_date).date() >= desired_last:
            continue
        try:
            history = fetch_price_history(str(row.contract), str(row.exchange), history_end)
            if not history.empty:
                upsert_frame("contracts", history, ["trade_date", "exchange", "contract"], path)
        except Exception:  # noqa: BLE001, S112 - optional enrichment; rank updates remain authoritative.
            continue


def _restore_rank_sources(path=DB_PATH) -> None:
    """A rank-bearing contract row is authoritative over price-only enrichment on the same date."""
    with connect(path) as con:
        con.execute("""
            UPDATE contracts AS c
            SET source = p.source
            FROM (
                SELECT DISTINCT trade_date, exchange, symbol, contract, source
                FROM broker_positions
                WHERE source <> 'demo'
            ) AS p
            WHERE c.trade_date = p.trade_date
              AND c.exchange = p.exchange
              AND c.symbol = p.symbol
              AND c.contract = p.contract
        """)


def _sync_position_snapshots(metrics: pd.DataFrame, path=DB_PATH) -> None:
    """Keep real contract snapshots available even when aggregate history is unavailable."""
    if metrics.empty:
        return
    sources = query("SELECT trade_date, exchange, symbol, contract, source FROM contracts", path=path)
    snapshots = metrics.merge(sources, on=["trade_date", "exchange", "symbol", "contract"], how="inner")
    snapshots = snapshots[~snapshots["source"].isin(["demo", "sina-price-history"])].copy()
    columns = ["trade_date", "exchange", "symbol", "contract", "top20_long", "top20_short",
               "net_position", "net_position_ratio", "source"]
    if not snapshots.empty:
        upsert_frame("position_history", snapshots[columns], ["trade_date", "exchange", "symbol", "contract"], path)


def _backfill_position_history(target: date, path=DB_PATH, lookback_days: int = 28) -> None:
    """Backfill real Top20 history one exchange at a time so failures stay isolated."""
    for exchange in EXCHANGES:
        # DCE's legacy public download currently returns HTML instead of its documented ZIP.
        # Its latest contract snapshot is preserved by _sync_position_snapshots.
        if exchange == "DCE":
            continue
        existing = query(
            "SELECT count(DISTINCT trade_date) n, max(trade_date) last_date FROM position_history WHERE exchange=?",
            [exchange], path,
        )
        last_date = existing.iloc[0]["last_date"]
        if int(existing.iloc[0]["n"]) >= 15 and pd.notna(last_date) and pd.Timestamp(last_date).date() >= target:
            continue
        try:
            history = fetch_position_history(exchange, target - timedelta(days=lookback_days), target)
            upsert_frame("position_history", history, ["trade_date", "exchange", "symbol", "contract"], path)
        except Exception:  # noqa: BLE001, S112 - optional history must not block daily updates.
            continue


def update(trade_date: date | None = None, force: bool = False, path=DB_PATH) -> dict[str, str]:
    init_db(path)
    target, status = trade_date or latest_weekday(), {}
    for exchange in EXCHANGES:
        if not force:
            existing = query("SELECT count(*) n FROM contracts WHERE trade_date=? AND exchange=? AND source <> 'demo'", [target, exchange], path)
            if int(existing.iloc[0]["n"]) > 0:
                status[exchange] = "已是最新"
                continue
        try:
            actual_date, update_source, update_message = target, "official-via-akshare", "更新成功"
            try:
                contracts, positions = fetch_contracts(exchange, target), fetch_positions(exchange, target)
                contracts = contracts[contracts["contract"].isin(set(positions["contract"]))].copy()
                if contracts.empty:
                    raise RuntimeError("行情合约与持仓排名合约无法匹配")
                contracts["is_main"] = False
                contracts.loc[contracts.groupby("symbol")["open_interest"].idxmax(), "is_main"] = True
            except Exception:  # Only DCE has a controlled secondary source.
                if exchange != "DCE":
                    raise
                contracts, positions, actual_date = fetch_dce_sina_fallback(target)
                update_source = "sina-fallback"
                update_message = f"大商所接口异常，已使用备用源；席位数据截至 {actual_date}"
            upsert_frame("contracts", contracts, ["trade_date", "exchange", "contract"], path)
            upsert_frame("broker_positions", positions, ["trade_date", "exchange", "contract", "broker"], path)
            rows = len(contracts) + len(positions)
            log_status = "success" if actual_date == target else "stale"
            _log(exchange, target, log_status, rows, update_message, path, update_source)
            status[exchange] = f"成功 · {rows} 行" if actual_date == target else f"备用数据 · 截至 {actual_date}"
        except Exception as exc:  # noqa: BLE001 - isolate failures so one exchange cannot block the others.
            _log(exchange, target, "failed", 0, str(exc), path)
            status[exchange] = f"失败 · {exc}"
    _backfill_main_prices(path)
    _restore_rank_sources(path)
    metrics = calculate_metrics(query("SELECT * FROM contracts", path=path), query("SELECT * FROM broker_positions", path=path))
    if not metrics.empty:
        upsert_frame("daily_metrics", metrics, ["trade_date", "exchange", "contract"], path)
        _sync_position_snapshots(metrics, path)
    _backfill_position_history(target, path)
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description="Update SeatAlpha from exchange public data")
    parser.add_argument("--date", help="YYYY-MM-DD; default: latest completed weekday")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--seed-demo", action="store_true")
    args = parser.parse_args()
    if args.seed_demo or is_empty():
        seed(replace=args.seed_demo)
        if args.seed_demo:
            print("Demo data seeded")
            return 0
    result = update(date.fromisoformat(args.date) if args.date else None, args.force)
    for exchange, message in result.items():
        print(f"{exchange}: {message}")
    return 1 if all(value.startswith("失败") for value in result.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
