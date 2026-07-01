# 研究脚本

本目录保存 `HYPE-15M-Multi-Indicator-Intraday` 的一次性研究、消融和审计脚本。

脚本要求：

- 优先读取 `data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m/`；`data/cache` 只能用于明确标记的历史复现。
- 使用闭合 K 信号和下一根 open 入场。
- 显式计算手续费与滑点。
- 被 Markdown 报告引用的 JSON/CSV 写入 `../artifacts/`。

## 当前脚本

- `research_hype_15m_mii_search.py`：首次广泛多指标搜索，结论为未达到目标。
- `research_hype_15m_mii_full_ablation.py`：旧 cache 口径的最佳综合策略时间切片和 OAT 消融。
- `research_hype_15m_mii_surface_combo_optimization.py`：组合旧消融里的表面改善参数，验证是否能同时提高收益与降低回撤。
- `research_hype_15m_mii_v1_full_ablation.py`：标准 raw/normalized 数据湖上的 V1 复现脚本；修复 timeout 与单仓时序，并覆盖所有生效参数及 MACD/ATR 指标周期消融。
- `research_hype_15m_mii_clean_evolution.py`：根据 V1 消融清理 dormant 参数，并在干净参数空间做多目标演化。
- `research_hype_15m_mii_delay_aware_selection.py`：读取 clean evolution 的 risk-feasible 结果，把入场推迟到 K+2 open 做延迟联合筛选。
- `research_hype_15m_mii_v11_lead_robustness.py`：对历史 `V1.1 diagnostic lead` 做邻域、成本、K+2、方向、月度和滚动 90d 压力复核；该临时命名已被当前 `HYPE-15M-MII-V1.1` 主观察基线 supersede。
- `research_hype_15m_mii_relaxed_dd_selection.py`：在接受更大回撤时筛选高收益/高胜率诊断版本，并生成暴露阶梯。
- `research_hype_15m_mii_fast_validation_ranking.py`：面向小额快速验证，把频率、收益、回撤、胜率、Last90 与 K+2 延迟综合打分排序。
- `research_hype_15m_mii_balanced_leverage_stress.py`：对放弃频率后的均衡观察版本做 `1.75x/2x/3x` 暴露阶梯和 K+1/K+2 压力测试。
- `research_hype_15m_mii_v1_1_window_backtest.py`：把 `HYPE-15M-MII-V1base` 登记为 `HYPE-15M-MII-V1.1` 干净参数，并回测最近 `1w/1m/3m/6m/1y/all` 的 K+1 与 K+2 表现。
- `research_hype_15m_mii_v1_1_trade_path_chart.py`：生成 `HYPE-15M-MII-V1.1` 逐笔交易路径 HTML，包含局部 15m K 线、入场/出场连线、RSI(7) 与 MACD(12,26,9)。
- `research_hype_15m_mii_v1_1_dynamic_take_profit.py`：测试 `HYPE-15M-MII-V1.1` 固定 TP 改为 activation 后 trailing stop 的动态止盈，并输出 K+1/K+2 排名与出场原因。
- `research_hype_15m_mii_v1_2_atr_bracket_exit.py`：把 `HYPE-15M-MII-V1.1` 的固定 TP/SL 改为入场时按 `ATR96%` 设置固定 bracket，并记录为 `HYPE-15M-MII-V1.2`；输出 K+1/K+2 排名与出场原因。
- `research_hype_15m_mii_v1_2_window_slice_backtest.py`：对 `HYPE-15M-MII-V1.2` 做最近 `1w/1m/3m/6m/1y/all` 固定窗口、`30/90/180d` 滚动窗口和随机切片回测，并输出交易数、收益、回撤、Sharpe/Sortino/Calmar 等指标。
- `research_hype_15m_mii_v1_2_atr_rvol_filter_ablation.py`：保持 `HYPE-15M-MII-V1.2` 信号、MACD、ATR bracket 出场、成本和单仓状态机不变，分别去掉 `ATR96 >= 0.75%`、`RVOL96 >= 1.0`，以及同时去掉二者，评估开单数、收益和回撤变化。
- `research_hype_15m_mii_v1_2_macd_filter_ablation.py`：保持 `HYPE-15M-MII-V1.2` 的 ATR/RVOL 过滤、ATR bracket 出场、成本和单仓状态机不变，只去掉 `MACD(12,26,9)` 方向过滤，评估漏入信号和回测质量。
- `research_hype_15m_mii_v1_1_btc_eth_cross_asset.py`：把 `HYPE-15M-MII-V1.1` 直接套到 Binance USD-M `BTCUSDT`、`ETHUSDT` `15m` API 数据，做跨资产迁移诊断；该脚本不使用标准数据湖，结果不得作为 promotion 证据。
