# SeatAlpha

国内商品期货机构席位资金流监控与信号发现工具。项目完全运行在本地：从交易所公开数据更新，写入 DuckDB，并通过 Streamlit + Plotly 展示市场全景、品种详情和席位画像。

## 快速开始（Windows）

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

初次启动且数据库为空时，应用会生成带有醒目“演示数据”标记的可复现样例数据，方便检查完整功能。点击侧边栏“更新官方数据”后才会写入真实数据；更新失败会保留失败日志，不会将样例标记为真实数据。

## 页面功能

- 全景日报：研究报告式白色界面，包含分类方向速览、机构一致性地图、核心品种全景和今日关键变化
- 一致性地图：Top20 净仓强度 × 席位方向一致性，气泡大小代表多空持仓总量
- 核心品种扫描：净仓/价格双趋势、持仓体量、净仓强度、当日变化及真实数据日期
- 品种详情：价格与品种级 Top20 净仓历史、Top 净多/净空席位、席位行为分类
- 席位画像：单席位跨品种净持仓和变化分布
- 数据状态：四家交易所最近更新状态、来源、覆盖日期和完整更新日志

## 数据与口径

数据库默认位于 `data/seatalpha.duckdb`，包含 `contracts`、`broker_positions`、`daily_metrics`、`position_history`、`update_log` 五张表。核心口径详见 [docs/METRICS.md](docs/METRICS.md)。

公开数据由 AKShare 的交易所适配接口读取；原始来源为上期所、大商所、郑商所和广期所官网。大商所旧下载接口不可用时会启用新浪持仓备用源，并在页面明确显示实际数据日期，不会用演示数据补齐真实曲线。交易所网页结构可能变化，因此使用前请检查“数据状态”。

## 开发与测试

```powershell
conda run -n seatalpha pytest -q
conda run -n seatalpha ruff check .
```
