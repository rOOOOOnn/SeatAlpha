from __future__ import annotations

TEXT = {
    "zh": {
        "sidebar_subtitle": "机构期货持仓研究终端",
        "update": "↻ 更新公开数据",
        "updating": "正在逐所更新与校验…",
        "date": "观察日期",
        "sectors": "品种板块",
        "scope_caption": "口径：各品种截至观察日的最新可用 Top20 席位数据。",
        "no_real_data": "没有真实数据可展示，请先更新公开数据。",
        "no_filter_data": "当前日期与板块筛选下没有真实席位数据。",
        "report_title": "机构期货持仓全景",
        "report_subtitle": "Top20 净仓、席位一致性与关键变化的结构化扫描",
        "instrument_basis": "品种口径：各自最新可用交易日",
        "data_source": "数据源：交易所公开数据 / 合规备用源",
        "covered": "覆盖品种",
        "instruments": "个",
        "sector_count": "个板块",
        "total_net": "Top20 合计净仓",
        "ten_thousand_lots": "万手",
        "total_note": "跨品种直接加总，仅作方向观察",
        "strongest": "最强综合信号",
        "largest_change": "最大单日变化",
        "freshness": "数据新鲜度",
        "current_count": "当日品种",
        "stale_count": "个滞后",
        "tab_overview": "全景日报",
        "tab_detail": "品种详情",
        "tab_broker": "席位画像",
        "tab_status": "数据状态",
        "section_sector": "分类方向速览",
        "section_sector_note": "按板块汇总净仓强度、净仓变化和席位一致性",
        "section_map": "机构一致性地图",
        "section_map_note": "横轴为 Top20 净仓强度，纵轴为席位方向一致性；气泡为持仓体量",
        "net_strength": "净仓强度",
        "consistency": "席位一致性",
        "net_strength_axis": "Top20 净持仓强度（%）",
        "consistency_axis": "席位一致性（%）",
        "max_gross": "最大持仓体量",
        "section_panorama": "核心品种全景",
        "section_panorama_note": "蓝线为净仓强度，金线为价格；数值单位为手，按综合信号排序",
        "section_changes": "今日关键变化",
        "section_changes_note": "按席位净变化绝对值筛选，展示多头、空头与净变化",
        "dce_note": "大商所官方旧下载接口异常，DCE 使用备用源并保留真实数据日期。",
        "fresh_note": "所有品种席位数据均为观察日当日。",
        "data_note": "数据说明",
        "stale_instruments": "滞后品种",
        "none": "无",
        "no_demo_mix": "不与演示数据拼接。",
        "select_instrument": "选择品种",
        "current_strength": "当前净仓强度",
        "top20_net": "Top20 净持仓",
        "lots": "手",
        "position_date": "席位数据日期",
        "main_close": "主力收盘价",
        "top20_strength": "Top20 净仓强度",
        "close": "收盘价",
        "one_point": "该品种目前只有一个真实席位历史点，因此用指标和散点展示，不绘制虚假趋势线。",
        "select_broker": "选择席位",
        "net_position": "净持仓",
        "instrument": "品种",
        "status_title": "数据血缘与更新状态",
        "status_note": "逐交易所隔离更新，失败不会阻塞其他市场",
        "no_logs": "尚无更新日志。",
        "full_logs": "完整更新日志",
        "net_long_top": "净多 Top 8",
        "net_short_top": "净空 Top 8",
        "today_behavior": "今日行为",
        "up_to_date": "已是最新",
        "success": "成功",
        "fallback_data": "备用数据",
        "as_of": "截至",
        "failed": "失败",
        "rows": "行",
    },
    "en": {
        "sidebar_subtitle": "Institutional Futures Positioning Research",
        "update": "↻ Update Public Data",
        "updating": "Updating and validating each exchange…",
        "date": "As-of Date",
        "sectors": "Sectors",
        "scope_caption": "Basis: latest available Top 20 member-position data for each instrument as of the selected date.",
        "no_real_data": "No real data is available. Update public data first.",
        "no_filter_data": "No real position data matches the selected date and sectors.",
        "report_title": "Institutional Futures Positioning Atlas",
        "report_subtitle": "A structured scan of Top 20 net positioning, member consensus, and key changes",
        "instrument_basis": "Instrument basis: each instrument's latest available trading day",
        "data_source": "Sources: public exchange data / controlled fallback",
        "covered": "Instruments Covered",
        "instruments": "",
        "sector_count": "sectors",
        "total_net": "Aggregate Top 20 Net",
        "ten_thousand_lots": "10k lots",
        "total_note": "Cross-instrument sum; directional context only",
        "strongest": "Strongest Composite Signal",
        "largest_change": "Largest 1-Day Change",
        "freshness": "Data Freshness",
        "current_count": "current",
        "stale_count": "stale",
        "tab_overview": "Positioning Atlas",
        "tab_detail": "Instrument Detail",
        "tab_broker": "Broker Profile",
        "tab_status": "Data Status",
        "section_sector": "Sector Direction Snapshot",
        "section_sector_note": "Sector aggregates of net strength, position change, and member consensus",
        "section_map": "Institutional Consensus Map",
        "section_map_note": "X: Top 20 net strength; Y: directional consensus; bubble size: gross positions",
        "net_strength": "Net Strength",
        "consistency": "Member Consensus",
        "net_strength_axis": "Top 20 Net Position Strength (%)",
        "consistency_axis": "Member Consensus (%)",
        "max_gross": "Largest Gross Position",
        "section_panorama": "Core Instrument Panorama",
        "section_panorama_note": "Blue: net strength; gold: price. Sorted by composite signal",
        "section_changes": "Key Changes Today",
        "section_changes_note": "Largest absolute member-position changes, split into long, short, and net moves",
        "dce_note": "The legacy DCE download endpoint is unavailable; a controlled fallback is used with the true data date retained.",
        "fresh_note": "All instruments have position data for the selected date.",
        "data_note": "Data note",
        "stale_instruments": "Stale instruments",
        "none": "None",
        "no_demo_mix": "Demo data is never blended into real series.",
        "select_instrument": "Select Instrument",
        "current_strength": "Current Net Strength",
        "top20_net": "Top 20 Net Position",
        "lots": "lots",
        "position_date": "Position Data Date",
        "main_close": "Main Contract Close",
        "top20_strength": "Top 20 Net Strength",
        "close": "Close",
        "one_point": "Only one real position-history point is available, so the app shows a KPI and marker without drawing a misleading trend line.",
        "select_broker": "Select Broker",
        "net_position": "Net Position",
        "instrument": "Instrument",
        "status_title": "Data Lineage and Update Status",
        "status_note": "Exchange updates are isolated; one failure does not block other markets",
        "no_logs": "No update logs are available.",
        "full_logs": "Full Update Log",
        "net_long_top": "Top 8 Net Long",
        "net_short_top": "Top 8 Net Short",
        "today_behavior": "Today's Behavior",
        "up_to_date": "Up to date",
        "success": "Success",
        "fallback_data": "Fallback data",
        "as_of": "as of",
        "failed": "Failed",
        "rows": "rows",
    },
}

SYMBOL_NAMES_EN = {
    "RB": "Rebar", "HC": "Hot-Rolled Coil", "CU": "Copper", "AL": "Aluminum", "AU": "Gold",
    "SC": "Crude Oil", "M": "Soybean Meal", "I": "Iron Ore", "P": "Palm Oil", "MA": "Methanol",
    "SR": "Sugar", "CF": "Cotton", "SI": "Silicon", "LC": "Lithium Carbonate",
}

SECTORS_EN = {
    "黑色": "Ferrous", "有色": "Base Metals", "贵金属": "Precious Metals", "能化": "Energy & Chemicals",
    "油脂油料": "Oils & Oilseeds", "软商品": "Soft Commodities", "新能源": "New Energy", "其他": "Other",
}

SIGNALS_EN = {"共同净多": "Consensus Net Long", "共同净空": "Consensus Net Short", "机构分歧": "Institutional Divergence"}
BEHAVIORS_EN = {"强加多": "Strong Long Build", "强加空": "Strong Short Build", "双边扩仓": "Two-Sided Expansion",
                "双边减仓": "Two-Sided Reduction", "方向不明": "No Clear Direction"}


def tr(lang: str, key: str, **kwargs: object) -> str:
    value = TEXT.get(lang, TEXT["zh"]).get(key, TEXT["zh"].get(key, key))
    return value.format(**kwargs) if kwargs else value


def instrument_name(symbol: str, lang: str, chinese_name: str | None = None) -> str:
    return SYMBOL_NAMES_EN.get(symbol, symbol) if lang == "en" else (chinese_name or symbol)


def sector_name(sector: str, lang: str) -> str:
    return SECTORS_EN.get(sector, sector) if lang == "en" else sector


def signal_name(signal: str, lang: str) -> str:
    return SIGNALS_EN.get(signal, signal) if lang == "en" else signal


def behavior_name(behavior: str, lang: str) -> str:
    return BEHAVIORS_EN.get(behavior, behavior) if lang == "en" else behavior


def update_message(message: str, lang: str) -> str:
    if lang == "zh":
        return message
    replacements = {
        "已是最新": "Up to date", "成功": "Success", "备用数据": "Fallback data", "截至": "as of",
        "失败": "Failed", "行": "rows",
    }
    result = message
    for source, target in replacements.items():
        result = result.replace(source, target)
    return result


def log_message(message: str, lang: str) -> str:
    if lang == "zh" or not isinstance(message, str):
        return message
    if message == "更新成功":
        return "Update successful"
    if message.startswith("大商所接口异常"):
        date_text = message.split("截至", 1)[-1].strip() if "截至" in message else ""
        suffix = f"; position data as of {date_text}" if date_text else ""
        return f"DCE endpoint unavailable; controlled fallback used{suffix}"
    return message
