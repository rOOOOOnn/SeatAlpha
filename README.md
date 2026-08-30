# SeatAlpha

[中文](#中文说明) | [English](#english)

## 中文说明

国内商品期货机构席位资金流监控与信号发现工具。项目完全运行在本地：从交易所公开数据更新，写入 DuckDB，并通过 Streamlit + Plotly 展示机构持仓全景、品种详情和席位画像。界面支持中文与英文即时切换。

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

### 页面功能

- 全景日报：研究报告式白色界面，包含分类方向速览、机构一致性地图、核心品种全景和今日关键变化
- 一致性地图：Top20 净仓强度 × 席位方向一致性，气泡大小代表多空持仓总量
- 核心品种扫描：净仓/价格双趋势、持仓体量、净仓强度、当日变化及真实数据日期
- 品种详情：价格与品种级 Top20 净仓历史、Top 净多/净空席位、席位行为分类
- 席位画像：单席位跨品种净持仓和变化分布
- 数据状态：四家交易所最近更新状态、来源、覆盖日期和完整更新日志

### 数据与口径

数据库默认位于 `data/seatalpha.duckdb`，包含 `contracts`、`broker_positions`、`daily_metrics`、`position_history`、`update_log` 五张表。核心口径详见 [docs/METRICS.md](docs/METRICS.md)。

公开数据由 AKShare 的交易所适配接口读取；原始来源为上期所、大商所、郑商所和广期所官网。大商所旧下载接口不可用时会启用新浪持仓备用源，并在页面明确显示实际数据日期，不会用演示数据补齐真实曲线。

### 开发与测试

```powershell
conda run -n seatalpha pytest -q
conda run -n seatalpha ruff check .
```

---

## English

SeatAlpha is a local research dashboard for monitoring institutional positioning and detecting signals in Chinese commodity futures. It updates from public exchange data, stores normalized records in DuckDB, and presents a Streamlit + Plotly positioning atlas, instrument detail views, and broker profiles. The entire interface can switch instantly between Chinese and English.

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

### Dashboard Views

- Positioning Atlas: a research-report layout with sector direction, an institutional consensus map, a core-instrument panorama, and key daily changes
- Consensus Map: Top 20 net-position strength versus directional member consensus, with gross positions encoded by bubble size
- Core Instrument Scan: net-position and price trends, gross positioning, net strength, daily change, and the true source date
- Instrument Detail: price and variety-level Top 20 positioning history, top net-long/net-short members, and member behavior classification
- Broker Profile: cross-instrument net positions and changes for an individual broker
- Data Status: latest exchange update states, source lineage, coverage dates, and the complete update log

### Data and Methodology

The default database is `data/seatalpha.duckdb`. It contains five tables: `contracts`, `broker_positions`, `daily_metrics`, `position_history`, and `update_log`. See [docs/METRICS.md](docs/METRICS.md) for metric definitions.

Data is retrieved through AKShare exchange adapters, whose underlying sources are SHFE, DCE, CZCE, and GFEX public releases. If the legacy DCE download endpoint is unavailable, SeatAlpha uses a controlled Sina positioning fallback and clearly displays the actual data date. Demo data is never used to fill gaps in real trends.

### Development and Tests

```powershell
conda run -n seatalpha pytest -q
conda run -n seatalpha ruff check .
```
