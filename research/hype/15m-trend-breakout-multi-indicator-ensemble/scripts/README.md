# 研究脚本

本目录保存 `HYPE-15M-Trend-Breakout-Multi-Indicator-Ensemble` 的一次性组合研究脚本。

脚本要求：

- 读取标准 raw/normalized 数据湖，运行前通过数据质量 gate。
- V35 腿复用 `../../15m-ema-trend-breakout/scripts/research_hype_ema_tb_v35_profit_floor.py` 的 canonical 引擎；V1.3 腿复用 `../../15m-multi-indicator-intraday/scripts/` 的 V1.2/V1.3 模块。
- 显式声明两腿各自的成本与 funding 口径。
- 被 Markdown 报告引用的 JSON/CSV 写入 `../artifacts/`。

## 当前脚本

- `research_hype_15m_tb_mii_ensemble_backtest.py`：组合回测（`--trend v35|v39`，`--mii v13|v14`，`--run-date`）。双子账户组合（50/50、70/30、30/70 逐 K 再平衡、50/50 固定拆分）与单账户冲突仲裁（趋势腿优先 preempt / no-preempt），含 MII 腿 K+2 延迟压力与 `1d/7d/1m/3m/6m/1y` 审计分片。内置门禁：数据质量 gate、趋势腿与 canonical 引擎逐 K 权益零差、趋势腿/MII 腿与各自主账登记值对照（窗口一致时启用）、MII 腿单仓选择链与 MII 引擎逐笔/终值对照。
