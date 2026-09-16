from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
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
)
from crawler.akshare_provider import (
    fetch_price_history as fetch_sina_price_history,
)
from crawler.ifind_provider import (
    IFindError,
    enrich_contracts,
)
from crawler.ifind_provider import (
    fetch_daily as fetch_ifind_daily,
)
from crawler.ifind_provider import (
    fetch_cffex_member_position_history,
    fetch_position_history_bundle as fetch_ifind_position_history_bundle,
)
from crawler.ifind_provider import (
    fetch_price_history as fetch_ifind_price_history,
)
from crawler.ifind_provider import (
    is_configured as ifind_is_configured,
)
from metrics.signals import calculate_metrics
from pipeline.seed_demo import seed

DATA_PUBLICATION_CUTOFF_HOUR = 20


def latest_weekday(today: date | None = None, *, now: datetime | None = None) -> date:
    """Return the latest trade date whose end-of-day rankings should be published.

    The dashboard's observation date may be today, while exchange member rankings
    are still being compiled.  Treat the current business day as complete only
    after the evening publication window.
    """
    now = now or datetime.now(ZoneInfo("Asia/Shanghai"))
    result = today or now.date()
    while result.weekday() >= 5:
        result -= timedelta(days=1)
    if result == now.date() and now.hour < DATA_PUBLICATION_CUTOFF_HOUR:
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
            WHERE is_main AND source NOT IN ('demo', 'sina-price-history', 'ifind-price-history')
        ) WHERE rn = 1
    """, path=path)
    for row in mains.itertuples(index=False):
        history_end = pd.Timestamp(row.trade_date).date()
        desired_last = history_end - timedelta(days=1)
        if row.source == "sina-fallback":
            desired_last = latest_weekday()
            history_end = desired_last + timedelta(days=1)
        preferred_source = "ifind-price-history" if ifind_is_configured() else "sina-price-history"
        existing = query(
            "SELECT count(*) n, max(trade_date) last_date FROM contracts "
            "WHERE contract=? AND exchange=? AND source=?",
            [row.contract, row.exchange, preferred_source], path,
        )
        last_date = existing.iloc[0]["last_date"]
        if int(existing.iloc[0]["n"]) >= 20 and pd.notna(last_date) and pd.Timestamp(last_date).date() >= desired_last:
            continue
        try:
            history = fetch_ifind_price_history(str(row.contract), str(row.exchange), history_end)
        except IFindError:
            try:
                history = fetch_sina_price_history(str(row.contract), str(row.exchange), history_end)
            except Exception:  # noqa: BLE001, S112 - optional fallback cannot block rank updates.
                continue
        try:
            if not history.empty:
                upsert_frame("contracts", history, ["trade_date", "exchange", "contract"], path)
        except Exception:  # noqa: BLE001, S112 - optional enrichment; rank updates remain authoritative.
            continue


def _sync_position_snapshots(metrics: pd.DataFrame, path=DB_PATH) -> None:
    """Keep real contract snapshots available even when aggregate history is unavailable."""
    if metrics.empty:
        return
    sources = query("""
        SELECT trade_date, exchange, symbol, contract, max(source) AS source
        FROM broker_positions
        WHERE source <> 'demo'
        GROUP BY trade_date, exchange, symbol, contract
    """, path=path)
    snapshots = metrics.merge(sources, on=["trade_date", "exchange", "symbol", "contract"], how="inner")
    snapshots = snapshots[snapshots["source"].ne("demo")].copy()
    columns = ["trade_date", "exchange", "symbol", "contract", "top20_long", "top20_short",
               "net_position", "net_position_ratio", "source"]
    if not snapshots.empty:
        upsert_frame("position_history", snapshots[columns], ["trade_date", "exchange", "symbol", "contract"], path)


def _backfill_cffex_member_positions(
    target: date, path=DB_PATH, lookback_days: int = 45,
) -> None:
    """Backfill verified CFFEX daily rankings for 20-day category comparisons."""
    if not ifind_is_configured():
        return
    desired = [stamp.date() for stamp in pd.bdate_range(target - timedelta(days=lookback_days), target)]
    desired = desired[-25:]
    completed, failed = 0, []
    for trade_day in desired:
        existing = query(
            "SELECT count(DISTINCT symbol) n FROM broker_positions WHERE exchange='CFFEX' AND trade_date=? AND source<>'demo'",
            [trade_day], path,
        )
        if int(existing.iloc[0]["n"]) >= 8:
            completed += 1
            continue
        try:
            contracts, member_positions, _ = fetch_ifind_daily("CFFEX", trade_day)
            upsert_frame("contracts", contracts, ["trade_date", "exchange", "contract"], path)
            _replace_position_partitions(member_positions, path)
            completed += 1
        except Exception as exc:  # noqa: BLE001 - holidays/individual unavailable dates are expected.
            failed.append(f"{trade_day}: {exc}")
    current_contracts = query(
        """SELECT DISTINCT contract FROM contracts
        WHERE exchange='CFFEX' AND trade_date=? AND is_main AND source<>'demo'""",
        [target], path,
    )
    for contract in current_contracts["contract"].astype(str):
        existing = query(
            """SELECT count(DISTINCT trade_date) n FROM broker_positions
            WHERE exchange='CFFEX' AND contract=? AND source='ifind-member-position-history'""",
            [contract], path,
        )
        if int(existing.iloc[0]["n"]) >= 20:
            continue
        try:
            fixed_history = fetch_cffex_member_position_history(
                contract, target - timedelta(days=lookback_days), target
            )
            _replace_position_partitions(fixed_history, path)
        except IFindError as exc:
            failed.append(f"{contract}: {exc}")
    _log(
        "CFFEX", target, "success" if completed >= 20 else "partial", completed,
        f"中金所逐席位历史回填完成 {completed} 个交易日"
        + (f"；跳过/失败 {len(failed)} 日" if failed else ""),
        path, "ifind-member-position-history",
    )


def _backfill_position_history(target: date, path=DB_PATH, lookback_days: int = 45) -> None:
    """Backfill real Top20 history one exchange at a time so failures stay isolated."""
    _backfill_cffex_member_positions(target, path, lookback_days)
    for exchange in EXCHANGES:
        # CFFEX uses separate index/bond ranking reports. Daily snapshots are
        # persisted by _sync_position_snapshots; historical backfill is not mixed.
        if exchange == "CFFEX":
            continue
        if ifind_is_configured():
            mains = query("""SELECT DISTINCT contract FROM contracts WHERE exchange=? AND trade_date=?
                AND is_main AND source <> 'demo'""", [exchange, target], path)
            completed = 0
            pending = []
            for contract in mains.contract:
                existing_ifind = query("""SELECT count(*) n, max(trade_date) last_date FROM position_history
                    WHERE exchange=? AND contract=? AND source='ifind-position-history'""", [exchange, contract], path)
                existing_members = query("""SELECT count(DISTINCT trade_date) n FROM broker_positions
                    WHERE exchange=? AND contract=? AND source='ifind-member-position-history'""", [exchange, contract], path)
                if (int(existing_ifind.iloc[0]["n"]) >= 20
                        and int(existing_members.iloc[0]["n"]) >= 20
                        and pd.notna(existing_ifind.iloc[0]["last_date"])
                        and pd.Timestamp(existing_ifind.iloc[0]["last_date"]).date() >= target):
                    completed += 1
                    continue
                pending.append(contract)

            def fetch_history(contract: str, exchange: str = exchange) -> pd.DataFrame:
                return fetch_ifind_position_history_bundle(
                    contract, exchange, target-timedelta(days=lookback_days), target
                )

            with ThreadPoolExecutor(max_workers=min(6, max(len(pending), 1))) as executor:
                futures = {executor.submit(fetch_history, contract): contract for contract in pending}
                for future in as_completed(futures):
                    contract = futures[future]
                    try:
                        history, member_history = future.result()
                        upsert_frame("position_history", history, ["trade_date", "exchange", "symbol", "contract"], path)
                        _replace_position_partitions(member_history, path)
                        completed += 1
                    except IFindError as exc:
                        _log(exchange, target, "partial", 0, f"{contract} iFinD 持仓历史不可用：{exc}", path, "ifind-position-history")
            if len(mains) and completed == len(mains):
                continue
        # DCE's legacy public download currently returns HTML instead of its documented ZIP.
        # Its latest contract snapshot is preserved by _sync_position_snapshots.
        if exchange == "DCE":
            continue
        existing = query(
            "SELECT count(DISTINCT trade_date) n, max(trade_date) last_date FROM position_history WHERE exchange=?",
            [exchange], path,
        )
        last_date = existing.iloc[0]["last_date"]
        if int(existing.iloc[0]["n"]) >= 20 and pd.notna(last_date) and pd.Timestamp(last_date).date() >= target:
            continue
        try:
            history = fetch_position_history(exchange, target - timedelta(days=lookback_days), target)
            preferred = query("SELECT trade_date, exchange, symbol, contract FROM position_history WHERE source LIKE 'ifind%'", path=path)
            if not preferred.empty and not history.empty:
                keys = ["trade_date", "exchange", "symbol", "contract"]
                history = history.merge(preferred.assign(_preferred=True), on=keys, how="left")
                history = history[history["_preferred"].isna()].drop(columns="_preferred")
            upsert_frame("position_history", history, ["trade_date", "exchange", "symbol", "contract"], path)
        except Exception:  # noqa: BLE001, S112 - optional history must not block daily updates.
            continue


def update(
    trade_date: date | None = None,
    force: bool = False,
    path=DB_PATH,
    *,
    backfill_history: bool = True,
    missing_only: bool = False,
) -> dict[str, str]:
    """Update the latest daily snapshot, optionally running slow history backfills."""
    init_db(path)
    target, status = trade_date or latest_weekday(), {}
    for exchange in EXCHANGES:
        requested_symbols: set[str] | None = None
        if missing_only:
            active = query(
                """SELECT DISTINCT symbol FROM contracts
                WHERE trade_date=? AND exchange=? AND source<>'demo'
                AND is_main AND open_interest>0""",
                [target, exchange], path,
            )
            if not active.empty:
                ranked = query(
                    """SELECT DISTINCT symbol FROM broker_positions
                    WHERE trade_date=? AND exchange=? AND source<>'demo'""",
                    [target, exchange], path,
                )
                requested_symbols = set(active["symbol"]) - set(ranked["symbol"])
                if not requested_symbols:
                    status[exchange] = "已是最新"
                    continue
        if not force and not missing_only:
            catalog_attempt = query("""SELECT count(*) n FROM update_log WHERE trade_date=? AND exchange=?
                AND status IN ('success', 'partial') AND message LIKE '%全品种目录%'""",
                [target, exchange], path)
            if int(catalog_attempt.iloc[0]["n"]) > 0:
                status[exchange] = "已是最新"
                continue
        try:
            actual_date, update_message = target, "全品种目录更新成功"
            ifind_daily = False
            ifind_error = None
            try:
                contracts, positions, warnings = fetch_ifind_daily(
                    exchange, target, requested_symbols
                )
                ifind_daily = True
                missing_symbols = set(contracts.loc[contracts["is_main"], "symbol"]) - set(positions["symbol"])
                if missing_symbols and exchange != "DCE":
                    try:
                        public_positions = fetch_positions(exchange, target)
                        supplement = public_positions[public_positions["symbol"].isin(missing_symbols)]
                        if not supplement.empty:
                            positions = pd.concat([positions, supplement], ignore_index=True)
                            missing_symbols -= set(supplement["symbol"])
                    except Exception:  # noqa: BLE001, S110 - per-product fallback is optional.
                        pass
                warnings = [warning for warning in warnings if warning.split(":", 1)[0] in missing_symbols]
                if warnings:
                    update_message += "；部分品种排名不可用：" + "；".join(warnings)
            except IFindError as exc:
                ifind_error = exc
                update_message += f"；iFinD 日数据不可用（{exc}），尝试公开源"
            try:
                if ifind_daily:
                    pass
                elif exchange == "CFFEX":
                    raise IFindError(f"中金所仅使用已验证的 iFinD 排名接口：{ifind_error}")
                else:
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
                update_message = f"大商所接口异常，已使用备用源；席位数据截至 {actual_date}"
            try:
                # Quotes and member rankings have independent clocks. A stale
                # DCE ranking fallback must never pull the iFinD quote date back
                # to the ranking's actual date.
                if not ifind_daily:
                    contracts = enrich_contracts(contracts, target)
            except IFindError as exc:
                update_message += f"；iFinD 行情不可用（{exc}），保留公开行情"
            price_date = pd.to_datetime(contracts["trade_date"]).max().date()
            price_sources = "+".join(sorted(contracts["source"].astype(str).unique()))
            position_sources = "+".join(sorted(positions["source"].astype(str).unique()))
            update_source = f"price={price_sources}|positions={position_sources}"
            update_message += (
                f"；行情={price_sources}（截至 {price_date}）"
                f"；席位={position_sources}（截至 {actual_date}）"
            )
            upsert_frame("contracts", contracts, ["trade_date", "exchange", "contract"], path)
            _replace_position_partitions(positions, path)
            rows = len(contracts) + len(positions)
            log_status = "partial" if ifind_daily and warnings else ("success" if actual_date == target else "stale")
            _log(exchange, target, log_status, rows, update_message, path, update_source)
            status[exchange] = (
                (f"部分成功 · {rows} 行；" + "；".join(warnings) if log_status == "partial" else f"成功 · {rows} 行")
                if actual_date == target
                else f"备用数据 · 行情截至 {price_date} · 席位截至 {actual_date}"
            )
        except Exception as exc:  # noqa: BLE001 - isolate failures so one exchange cannot block the others.
            _log(exchange, target, "failed", 0, str(exc), path)
            status[exchange] = f"失败 · {exc}"
    if backfill_history:
        _backfill_main_prices(path)
    metrics = calculate_metrics(query("SELECT * FROM contracts", path=path), query("SELECT * FROM broker_positions", path=path))
    if not metrics.empty:
        upsert_frame("daily_metrics", metrics, ["trade_date", "exchange", "contract"], path)
        _sync_position_snapshots(metrics, path)
    if backfill_history:
        _backfill_position_history(target, path)
    return status


def _replace_position_partitions(positions: pd.DataFrame, path=DB_PATH) -> None:
    """Replace only validated contract/day snapshots atomically, never blend providers."""
    if positions.empty:
        return
    with connect(path) as con:
        con.register("incoming_positions", positions)
        columns = ", ".join(f'"{c}"' for c in positions.columns)
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute("""DELETE FROM broker_positions p USING incoming_positions i
                WHERE p.trade_date=i.trade_date AND p.exchange=i.exchange AND p.contract=i.contract""")
            con.execute(f"INSERT INTO broker_positions ({columns}) SELECT {columns} FROM incoming_positions")
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise


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
