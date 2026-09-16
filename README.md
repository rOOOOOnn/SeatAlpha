# SeatAlpha

[中文](#中文说明) | [English](#english)

## 中文说明

国内商品期货席位资金流监控与信号发现工具。项目完全运行在本地：从交易所公开数据更新，写入 DuckDB，并通过 Streamlit + Plotly 对外资、游资风格、机构型和散户代理四类客户持仓席位进行同口径比较。界面支持中文与英文即时切换。

### 快速开始（Windows）

首次安装：

```powershell
conda env create -f environment.yml
conda run -n seatalpha python -m pipeline.seed_demo
```

之后双击 `SeatAlpha.bat`。启动器会等待本地服务通过健康检查后再打开浏览器，首次启动可能需要十几秒。需要强制重新抓取最近交易日时双击 `Force_Update.bat`。

如果启动失败，窗口不会直接消失，并会提示错误；详细日志位于 `logs/streamlit-error.log`。

也可以从终端运行：

```powershell
conda run -n seatalpha python -m streamlit run app.py
```

在侧边栏顶部使用 `Language / 语言` 切换中文或英文。初次启动且数据库为空时，应用会生成可复现样例数据用于功能检查；真实全景页不会把演示数据混入真实序列。

### iFinD 配置（推荐）

复制 `.streamlit/secrets.example.toml` 为 `.streamlit/secrets.toml`，填入 iFinD `refresh_token`：

```toml
[ifind]
refresh_token = "你的 refresh token"
backup_refresh_token = "可选的备用 refresh token"
```

该文件已被 Git 忽略，不会提交到仓库。也可以通过环境变量 `IFIND_REFRESH_TOKEN` 和 `IFIND_BACKUP_REFRESH_TOKEN` 配置。程序只用 refresh token 获取当前有效的 access token；主账号明确返回额度超限时才切换备用账号，并且只补取当日缺失的活跃品种。

### 页面功能

- 顶部分层导航：商品、股指、国债期货三个独立市场，每个市场分别提供日报、品种详情、席位画像和数据状态
- 可选的“国内大型期货公司观点”页面：启用外部观点数据源后，展示公司 × 板块评分、中期展望、当日观点明细和运行质量；未启用或数据源不可用时不影响原有页面
- 四类总体概览：外资、游资风格、机构型、散户代理的净仓、今日变化、强弱品种横向比较
- 分类方向速览：按板块比较四类席位的净仓、变化、一致性与方向标签
- 一致性地图：固定使用不同形状区分类别；默认汇总展示每个板块分歧度和信号强度靠前的代表品种，也可切换单一板块或全市场
- 核心品种全景：每个品种一行并排展示四类席位统计、分歧度和核心三方共振状态
- 今日关键变化、分歧监控和基于确定性规则的 Executive Read
- 品种详情：价格与品种级 Top20 净仓历史、Top 净多/净空席位、席位行为分类
- 席位画像：单席位跨品种净持仓和变化分布
- 数据状态：五家交易所最近更新状态、来源、覆盖日期和完整更新日志

### 可选接入期货公司观点项目

期货公司观点作为可选外部数据源接入，不把 `futures_view_pipeline_v0_1` 的爬虫、模型调用、密钥、缓存和中间文件复制进 SeatAlpha。SeatAlpha 默认保持独立运行；只有明确开启接入并提供有效数据目录时，商品导航才显示“国内大型期货公司观点”。关闭接入、目录不存在或质量门禁未通过时，原有行情和席位页面继续正常工作。

在 `.streamlit/secrets.toml` 使用以下配置，默认关闭；也可以在侧栏按当前会话临时开启：

```toml
[external_views]
enabled = false
root = "F:/广发固收/期货公司观点/futures_view_pipeline_v0_1"
auto_update = true
llm_backend = "api"
timeout_seconds = 3600
```

启用自动更新后，SeatAlpha 按最新应发布交易日检查 `quality_report_YYYYMMDD.json`。数据已通过质量门禁时不重复运行；缺失时调用对方项目的 `run_all.ps1`，由其完成采集、分类、数据库同步、Excel 生成和严格质量检查。进程锁会阻止多个 Streamlit 会话重复更新，失败也不会中断 SeatAlpha 原有行情与席位页面。自动更新可能调用对方项目已经配置的模型/API；可设置 `auto_update = false` 后只使用页面上的手动更新按钮。

展示时，适配层只读取已经校验的最终产物和 `data/view_database.sqlite3`。网页还原 Excel 的“期货观点汇总”“中期展望”“当日观点明细”“运行与数据质量”，另提供 SQLite 全量历史观点页和原始 Excel 下载入口。程序不会读取或展示 `secrets/`、Prompt、模型原始回复或爬虫临时文件。

上述配置也可使用环境变量覆盖：`SEATALPHA_FUTURES_VIEW_ENABLED`、`SEATALPHA_FUTURES_VIEW_ROOT`、`SEATALPHA_FUTURES_VIEW_AUTO_UPDATE`、`SEATALPHA_FUTURES_VIEW_LLM_BACKEND` 和 `SEATALPHA_FUTURES_VIEW_TIMEOUT_SECONDS`。

GitHub 仓库只提交适配器、配置示例、页面代码和测试，不提交对方项目的密钥及本地原始数据。若需要在另一台机器或服务器使用，可把对方项目的 `output/` 作为只读目录挂载并修改 `root`；也可以以后增加一个脱敏同步步骤，把最终 JSON/Excel 镜像到 SeatAlpha 的本地数据目录。直接在 GitHub 上只有源码、没有挂载数据时，观点页面不会自动获得本机 Excel 内容。

### 四类席位配置

分类名单与别名统一位于 `settings/broker_classification.py`，信号阈值位于 `settings/signal_thresholds.py`。外资类包括乾坤期货、摩根大通、瑞银期货和摩根士丹利期货；游资风格类包括中财期货、混沌天成、永安期货和新湖期货；机构型席位新增方正中期、国元期货和平安期货；散户代理席位仅保留东方财富、徽商期货、弘业期货和瑞达期货。高盛期货及其深圳名称会标准化为乾坤期货。不能可靠归类的名称保留为 `other`，页面显示数量并可展开查看；不会静默丢弃。

数据流为：交易所原始排名 → 名称标准化 → 席位分类 → 同日期/品种/单一主力合约聚合 → 四类信号与分歧计算、外资/机构/散户代理核心三方共振计算 → 板块与页面视图。页面不把席位数据解释为期货公司的自营观点。

### 数据与口径

数据库默认位于 `data/seatalpha.duckdb`，包含 `contracts`、`broker_positions`、`daily_metrics`、`position_history`、`update_log` 五张表。核心口径详见 [docs/METRICS.md](docs/METRICS.md)。

行情、主力合约会员排名和持仓历史均优先使用 iFinD；不可用时保留公开源回退及错误日志。会员排名通过专题报表 `p00745` 获取，合约目录使用 `p02939`，固定合约持仓历史使用 `p02940`。大商所公开接口失败时仍保留新浪备用源。各品种按当日持仓量选择主力合约，排名按会员名称合并多空榜、排除合计行，整份替换同日同合约快照，避免混合来源重复计数。行情与席位分别显示来源及实际日期；缺失数据不伪装成零或最新值。原油等响应缺失的品种会记录不可用提示。历史曲线为固定合约，不是拼接主连。

当前目录覆盖上期所/上期能源、大商所、郑商所、广期所和中金所共 90 个期货品种。中金所股指与国债会员排名分别使用 iFinD 专题报表，并用相邻交易日持仓计算增减；账号无中金所普通行情权限时，行情改用已验证的 iFinD 专题行情报表。观察日仍自动显示当天，但在当日晚间数据发布窗口前，更新和新鲜度判断以上一个已完成交易日为基准。状态页只把每个品种最新记录用于新鲜度判断，旧的 8 月 21 日新浪备用数据仅保留在历史审计区，不再误报为当前延迟。目录存在但停牌、零持仓或未返回会员排名的品种会保留在目录中并明确标出原因。

四类席位均是对交易所公布的客户持仓席位所做的研究分类，完整名单在状态页和 `settings/broker_classification.py` 中公开展示。“游资风格”是用户指定的会员席位组合，“散户代理席位”不是交易所直接披露的个人账户数据；所有类别都不代表对应期货公司的自营观点，未能可靠判断的会员保留为“未分类”。

### 开发与测试

```powershell
conda run -n seatalpha pytest -q
conda run -n seatalpha ruff check .
```

---

## English

SeatAlpha is a local research dashboard for monitoring member positioning in Chinese futures. It updates from public exchange data, stores normalized records in DuckDB, and compares foreign, active-trading-style, institutional, and retail-oriented client-position seats on an identical basis. The entire interface can switch instantly between Chinese and English.

### Quick Start (Windows)

Create the Conda environment on first use:

```powershell
conda env create -f environment.yml
conda run -n seatalpha python -m pipeline.seed_demo
```

Then double-click `SeatAlpha.bat`. The launcher waits for the local health check before opening the browser, so the first cold start may take several seconds. Double-click `Force_Update.bat` when you need to force-refresh the latest completed trading day.

If startup fails, the launcher remains open and reports the error. Detailed logs are stored in `logs/streamlit-error.log`.

You can also start the app from a terminal:

```powershell
conda run -n seatalpha python -m streamlit run app.py
```

Use `Language / 语言` at the top of the sidebar to select Chinese or English. When the database is empty, the app can generate reproducible sample data for functional checks; the real-data atlas never blends demo observations into real series.

### iFinD Configuration (Recommended)

Copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml` and add the iFinD `refresh_token`:

```toml
[ifind]
refresh_token = "your refresh token"
backup_refresh_token = "optional backup refresh token"
```

The local secrets file is Git-ignored. You may alternatively set `IFIND_REFRESH_TOKEN` and `IFIND_BACKUP_REFRESH_TOKEN`. SeatAlpha obtains short-lived access tokens automatically. It switches accounts only after an explicit quota error and only retries active instruments missing from the current daily partition.

### Dashboard Views

- Two-level top navigation: separate commodity, equity-index, and treasury-futures markets, each with its own daily view, instrument detail, broker profile, and data status
- Optional China futures-company views page: when an external views source is enabled, it exposes company-by-sector scores, medium-term outlooks, daily evidence, and run quality; disabling or losing that source does not affect the existing dashboard
- Four-category overview: side-by-side foreign, active-trading-style, institution, and retail-proxy positioning and daily changes
- Sector direction: compact net position, change, consensus, and signal labels across seven sectors
- Consensus and divergence maps: distinct marker identities, with sector leaders shown together by default and optional single-sector/full-market scopes
- Core instrument panorama: one row per instrument with four category columns, divergence, and core three-way resonance state
- Key changes, divergence monitoring, and a deterministic Executive Read
- Instrument Detail: price and variety-level Top 20 positioning history, top net-long/net-short members, and member behavior classification
- Broker Profile: cross-instrument net positions and changes for an individual broker
- Data Status: latest exchange update states, source lineage, coverage dates, and the complete update log

### Optional Futures-Company Views Integration

Futures-company views are connected as an optional external data source. The crawler, model calls, secrets, caches, and intermediate files from `futures_view_pipeline_v0_1` are not copied into SeatAlpha. SeatAlpha remains standalone by default. The Commodities navigation shows the views page only when the integration is explicitly enabled and a valid data root is available. If the integration is disabled, the directory is missing, or its quality gate failed, the existing market and member-position pages continue to work.

Add the following to `.streamlit/secrets.toml`. It is disabled by default and can also be enabled temporarily for the current session from the sidebar:

```toml
[external_views]
enabled = false
root = "F:/广发固收/期货公司观点/futures_view_pipeline_v0_1"
auto_update = true
llm_backend = "api"
timeout_seconds = 3600
```

With automatic updates enabled, SeatAlpha checks the latest publishable trading day's `quality_report_YYYYMMDD.json`. It skips dates that already passed the quality gate. Missing dates invoke the source project's `run_all.ps1`, which owns collection, classification, database synchronization, workbook generation, and strict validation. A process lock prevents duplicate runs from concurrent Streamlit sessions, and failures do not interrupt the existing dashboard. Automatic updates may use the model/API already configured in the source project; set `auto_update = false` to update only through the page button.

For display, the adapter reads only validated final outputs and `data/view_database.sqlite3`. It reconstructs the workbook's sector summary, medium-term outlook, daily-detail, and run-quality views, adds the full SQLite history, and retains a download link to the original workbook. SeatAlpha never reads or displays the other project's secrets, prompts, raw model responses, or crawler scratch files.

Environment overrides are also supported: `SEATALPHA_FUTURES_VIEW_ENABLED`, `SEATALPHA_FUTURES_VIEW_ROOT`, `SEATALPHA_FUTURES_VIEW_AUTO_UPDATE`, `SEATALPHA_FUTURES_VIEW_LLM_BACKEND`, and `SEATALPHA_FUTURES_VIEW_TIMEOUT_SECONDS`.

The GitHub repository stores only the adapter, configuration example, page code, and tests. It does not store the other project's credentials or local raw data. Another workstation or server can mount the pipeline's `output/` directory read-only and change `root`; a later sanitized sync step may instead mirror final JSON/workbooks into SeatAlpha's local data directory. Source code on GitHub alone cannot access Excel files that remain only on this computer, so the optional page stays unavailable until a data directory is mounted or synchronized.

### Seat Classification

Edit aliases and the four category lists in `settings/broker_classification.py`; edit shared signal thresholds in `settings/signal_thresholds.py`. The foreign basket contains Qian Kun, J.P. Morgan, UBS, and Morgan Stanley Futures. The active-trading-style basket contains Zhongcai, Chaos Ternary, Yongan, and Xinhu Futures. Fangzheng CIFCO, Guoyuan Futures, and Ping An Futures are institutional seats. The retail-proxy basket is limited to East Money Futures, Huishang Futures, Holly Futures, and Ruida Futures. Goldman Sachs Futures variants normalize to Qian Kun. Uncertain names remain `other`, are counted and exposed in the UI, and are never silently dropped.

The calculation flow is: raw exchange ranks → broker normalization → classification → identical date/instrument/single-contract aggregation → category signals and divergence/resonance → sector and presentation views. The categories describe exchange-published client-position seats, not futures-company proprietary views.

### Data and Methodology

The default database is `data/seatalpha.duckdb`. It contains five tables: `contracts`, `broker_positions`, `daily_metrics`, `position_history`, and `update_log`. See [docs/METRICS.md](docs/METRICS.md) for metric definitions.

Quotes, main-contract member rankings and position history prefer iFinD, with public-source fallbacks and failure logs. Reports `p02939`, `p00745` and `p02940` provide the contract directory, member rankings and fixed-contract position history respectively. Main contracts are selected by daily open interest. Long/short lists are joined by normalized member name, totals are excluded, and each validated contract/day ranking snapshot replaces the previous snapshot atomically to prevent mixed-source double counting. Quotes and positions retain separate source labels and actual dates. Missing responses (including crude-oil rankings in the current verification) are not presented as zero or fresh data. Historical curves track a fixed contract, not a stitched continuous contract.

The catalog covers 90 futures products across SHFE/INE, DCE, CZCE, GFEX, and CFFEX. CFFEX equity-index and treasury-bond rankings use their dedicated iFinD reports, with daily changes calculated from adjacent trading days. If ordinary CFFEX quotation entitlement is unavailable, the verified iFinD financial-futures report supplies the quote fields. The observation selector still defaults to today, but before the evening publication window updates and freshness checks use the previous completed trading day. Freshness uses only the newest record for each product; the August 21 Sina fallback remains visible solely in historical audit coverage. Listed products that are dormant, have zero open interest, or have no published member ranking stay in the catalog with an explicit reason.

All four groups are research classifications of published client-position seats. The complete configured and currently observed member lists are visible on the Data Status page and maintained in `settings/broker_classification.py`. “Active-trading style” is a user-defined member basket; “retail proxy” is not exchange-disclosed individual-account data, and no category represents a futures company's proprietary house view. Uncertain members remain unclassified.

### Development and Tests

```powershell
conda run -n seatalpha pytest -q
conda run -n seatalpha ruff check .
```
