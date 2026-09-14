"""Broker-seat aliases and the editable research taxonomy.

The taxonomy describes the client-position seats published by exchanges. It
must not be interpreted as a futures company's proprietary house view.
"""

BROKER_ALIASES = {
    "乾坤期货有限公司": "乾坤期货",
    "高盛期货（深圳）": "乾坤期货",
    "高盛期货(深圳)": "乾坤期货",
    "高盛期货": "乾坤期货",
    "中信期货有限公司": "中信期货",
    "国泰君安期货有限公司": "国泰君安",
    "国泰君安期货": "国泰君安",
    "永安期货股份有限公司": "永安期货",
    "银河期货有限公司": "银河期货",
    "华泰期货有限公司": "华泰期货",
    "东证期货有限公司": "东证期货",
    "申万期货": "申银万国",
    "中金财富期货": "中金财富",
    "物产中大期货": "物产中大",
    "紫金天风期货": "紫金天风",
    "首创京都期货": "首创京都",
    "摩根期货": "摩根大通",
    "摩根大通期货有限公司": "摩根大通",
    "瑞银期货有限责任公司": "瑞银期货",
    "摩根士丹利期货（中国）有限公司": "摩根士丹利期货",
    "摩根士丹利期货(中国)有限公司": "摩根士丹利期货",
    "混沌天成期货股份有限公司": "混沌天成",
    "混沌天成期货": "混沌天成",
    "国元": "国元期货",
    "平安": "平安期货",
    "东方财富期货": "东方财富",
}

SEAT_CLASSIFICATION = {
    "qian_kun": {
        "乾坤期货", "摩根大通", "瑞银期货", "摩根士丹利期货",
    },
    "hot_money": {
        "中财期货", "混沌天成", "永安期货", "新湖期货",
    },
    "institution": {
        "中信期货", "国泰君安", "东证期货", "中粮期货", "银河期货",
        "华泰期货", "国投期货", "中信建投", "广发期货", "南华期货", "浙商期货",
        "海通期货", "东吴期货", "招商期货", "中泰期货", "光大期货", "五矿期货",
        "中金财富", "申银万国", "宏源期货", "建信期货", "中银期货",
        "中金期货", "中银国际", "中国国际", "国信期货", "兴证期货",
        "方正中期", "国元期货", "平安期货",
    },
    "retail": {
        "东方财富", "徽商期货", "弘业期货", "瑞达期货",
    },
}

CATEGORY_ORDER = ("qian_kun", "hot_money", "institution", "retail")
CORE_THREE_WAY_ORDER = ("qian_kun", "institution", "retail")
CATEGORY_LABELS = {
    "zh": {"qian_kun": "外资", "hot_money": "游资风格", "institution": "机构型席位", "retail": "散户代理席位", "other": "未分类"},
    "en": {"qian_kun": "Foreign", "hot_money": "Active-trading style", "institution": "Institution", "retail": "Retail", "other": "Unclassified"},
}

# Public-market research notes shown in the classification explanation only.
# They are descriptive labels and never participate in broker classification or
# position aggregation.
SEAT_RESEARCH_NOTES = {
    "zh": {
        "中财期货": "边锡明 / 中财系资金",
        "混沌天成": "葛卫东 / 混沌系",
        "永安期货": "叶庆均 / 敦和、浙江系资金",
        "新湖期货": "浙江产业资本 / 私募资金",
    },
    "en": {
        "中财期货": "Bian Ximing / Zhongcai-related capital",
        "混沌天成": "Ge Weidong / Chaos-related capital",
        "永安期货": "Ye Qingjun / Dunhe and Zhejiang-related capital",
        "新湖期货": "Zhejiang industrial capital / private-fund capital",
    },
}
