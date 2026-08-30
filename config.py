from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "seatalpha.duckdb"

EXCHANGES = ("SHFE", "DCE", "CZCE", "GFEX")

SYMBOL_META = {
    "RB": ("螺纹钢", "黑色", "SHFE"),
    "HC": ("热轧卷板", "黑色", "SHFE"),
    "CU": ("沪铜", "有色", "SHFE"),
    "AL": ("沪铝", "有色", "SHFE"),
    "AU": ("黄金", "贵金属", "SHFE"),
    "SC": ("原油", "能化", "SHFE"),
    "M": ("豆粕", "油脂油料", "DCE"),
    "I": ("铁矿石", "黑色", "DCE"),
    "P": ("棕榈油", "油脂油料", "DCE"),
    "MA": ("甲醇", "能化", "CZCE"),
    "SR": ("白糖", "软商品", "CZCE"),
    "CF": ("棉花", "软商品", "CZCE"),
    "SI": ("工业硅", "新能源", "GFEX"),
    "LC": ("碳酸锂", "新能源", "GFEX"),
}

DEFAULT_SYMBOLS = tuple(SYMBOL_META)

BROKER_ALIASES = {
    "中信期货有限公司": "中信期货",
    "国泰君安期货有限公司": "国泰君安",
    "永安期货股份有限公司": "永安期货",
    "银河期货有限公司": "银河期货",
    "华泰期货有限公司": "华泰期货",
    "东证期货有限公司": "东证期货",
}
