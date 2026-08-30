from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from config import DB_PATH, SYMBOL_META
from core.db import init_db, upsert_frame
from metrics.signals import calculate_metrics

BROKERS = ("永安期货", "中信期货", "国泰君安", "银河期货", "华泰期货", "东证期货", "国投安信", "海通期货", "浙商期货", "光大期货", "申银万国", "方正中期")


def build_demo(end: date | None = None, periods: int = 45) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.bdate_range(end=end or datetime.now(ZoneInfo("Asia/Shanghai")).date(), periods=periods)
    rng = np.random.default_rng(20260830)
    contracts, positions = [], []
    for symbol_idx, (symbol, (_, _, exchange)) in enumerate(SYMBOL_META.items()):
        price, contract = 1000 + symbol_idx * 420, f"{symbol}2609"
        bias = (symbol_idx - len(SYMBOL_META) / 2) / len(SYMBOL_META)
        for day_idx, trade_date in enumerate(dates):
            price = max(50, price * (1 + rng.normal(bias * 0.0003, 0.012)))
            oi = int(90000 + symbol_idx * 7000 + rng.normal(0, 7000))
            contracts.append({"trade_date": trade_date, "exchange": exchange, "symbol": symbol, "contract": contract,
                              "close": round(price, 2), "open_interest": max(1000, oi), "volume": max(1000, int(oi * rng.uniform(.5, 1.8))),
                              "is_main": True, "source": "demo"})
            for rank, broker in enumerate(BROKERS, 1):
                base = 2800 + (len(BROKERS) - rank) * 480 + symbol_idx * 90
                drift = bias * 55 + np.sin(day_idx / 6 + symbol_idx) * 45
                positions.append({"trade_date": trade_date, "exchange": exchange, "symbol": symbol, "contract": contract,
                                  "broker": broker, "long_position": max(0, int(base + day_idx * drift + rng.normal(0, 900))),
                                  "long_change": int(rng.normal(drift, 380)),
                                  "short_position": max(0, int(base - day_idx * drift + rng.normal(0, 900))),
                                  "short_change": int(rng.normal(-drift, 380)), "rank": rank, "source": "demo"})
    return pd.DataFrame(contracts), pd.DataFrame(positions)


def seed(path=DB_PATH, replace: bool = False) -> None:
    init_db(path)
    contracts, positions = build_demo()
    if replace:
        from core.db import connect
        with connect(path) as con:
            con.execute("DELETE FROM daily_metrics; DELETE FROM broker_positions; DELETE FROM contracts")
    upsert_frame("contracts", contracts, ["trade_date", "exchange", "contract"], path)
    upsert_frame("broker_positions", positions, ["trade_date", "exchange", "contract", "broker"], path)
    upsert_frame("daily_metrics", calculate_metrics(contracts, positions), ["trade_date", "exchange", "contract"], path)


if __name__ == "__main__":
    seed(replace=True)
    print(f"Demo database created: {DB_PATH}")
