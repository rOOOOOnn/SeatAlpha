from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import duckdb
import pandas as pd

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS contracts (
    trade_date DATE NOT NULL,
    exchange VARCHAR NOT NULL,
    symbol VARCHAR NOT NULL,
    contract VARCHAR NOT NULL,
    close DOUBLE,
    open_interest DOUBLE,
    volume DOUBLE,
    is_main BOOLEAN DEFAULT TRUE,
    source VARCHAR NOT NULL,
    PRIMARY KEY (trade_date, exchange, contract)
);
CREATE TABLE IF NOT EXISTS broker_positions (
    trade_date DATE NOT NULL,
    exchange VARCHAR NOT NULL,
    symbol VARCHAR NOT NULL,
    contract VARCHAR NOT NULL,
    broker VARCHAR NOT NULL,
    long_position DOUBLE DEFAULT 0,
    long_change DOUBLE DEFAULT 0,
    short_position DOUBLE DEFAULT 0,
    short_change DOUBLE DEFAULT 0,
    rank INTEGER,
    source VARCHAR NOT NULL,
    PRIMARY KEY (trade_date, exchange, contract, broker)
);
CREATE TABLE IF NOT EXISTS daily_metrics (
    trade_date DATE NOT NULL,
    exchange VARCHAR NOT NULL,
    symbol VARCHAR NOT NULL,
    contract VARCHAR NOT NULL,
    close DOUBLE,
    open_interest DOUBLE,
    top20_long DOUBLE,
    top20_short DOUBLE,
    net_position DOUBLE,
    net_position_ratio DOUBLE,
    delta_net_1d DOUBLE,
    delta_net_5d DOUBLE,
    delta_net_20d DOUBLE,
    price_change_1d DOUBLE,
    consensus DOUBLE,
    bull_score DOUBLE,
    divergence_score DOUBLE,
    PRIMARY KEY (trade_date, exchange, contract)
);
CREATE TABLE IF NOT EXISTS position_history (
    trade_date DATE NOT NULL,
    exchange VARCHAR NOT NULL,
    symbol VARCHAR NOT NULL,
    contract VARCHAR NOT NULL,
    top20_long DOUBLE,
    top20_short DOUBLE,
    net_position DOUBLE,
    net_position_ratio DOUBLE,
    source VARCHAR NOT NULL,
    PRIMARY KEY (trade_date, exchange, symbol, contract)
);
CREATE TABLE IF NOT EXISTS update_log (
    attempted_at TIMESTAMP NOT NULL,
    trade_date DATE,
    exchange VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    rows_written INTEGER DEFAULT 0,
    message VARCHAR,
    source VARCHAR NOT NULL
);
"""


def _path(path: str | Path | None = None) -> Path:
    result = Path(path) if path else DB_PATH
    result.parent.mkdir(parents=True, exist_ok=True)
    return result


@contextmanager
def connect(path: str | Path | None = None, read_only: bool = False):
    con = duckdb.connect(str(_path(path)), read_only=read_only)
    try:
        yield con
    finally:
        con.close()


def init_db(path: str | Path | None = None) -> None:
    with connect(path) as con:
        con.execute(SCHEMA)


def upsert_frame(table: str, frame: pd.DataFrame, keys: list[str], path: str | Path | None = None) -> int:
    if frame.empty:
        return 0
    init_db(path)
    with connect(path) as con:
        con.register("incoming", frame)
        predicate = " AND ".join(f't."{key}" = i."{key}"' for key in keys)
        con.execute(f'DELETE FROM "{table}" t USING incoming i WHERE {predicate}')
        columns = list(frame.columns)
        quoted = ", ".join(f'"{column}"' for column in columns)
        con.execute(f'INSERT INTO "{table}" ({quoted}) SELECT {quoted} FROM incoming')
    return len(frame)


def query(sql: str, params: list | tuple | None = None, path: str | Path | None = None) -> pd.DataFrame:
    init_db(path)
    with connect(path, read_only=True) as con:
        return con.execute(sql, params or []).fetchdf()


def is_empty(path: str | Path | None = None) -> bool:
    init_db(path)
    return int(query("SELECT count(*) AS n FROM contracts", path=path).iloc[0]["n"]) == 0
