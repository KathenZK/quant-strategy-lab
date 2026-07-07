# BTC-1H-Adaptive-Regime

`BTC-1H-Adaptive-Regime`（短 id：`BTC-1H-AR`）是 Binance USD-M Futures `BTCUSDT` perpetual `1h` 多指标自适应策略研究家族，与任何 HYPE family 无版本继承关系。

## 研究目标

- 数据：运行时最近两年的全部闭合 `1h` K，直接刷新自 Binance FAPI，并保存 raw/normalized 数据湖分区、资金费历史和合约过滤器快照。
- OOS：最后三个月固定为 locked out-of-sample；搜索和排序不得读取该区间。
- 硬门槛：年化权益倍率 `>=10.0x`（即年化收益 `>=900%`）、胜率 `>=50%`、最大回撤严格小于 `20%`。
- 执行：闭合 K 产生信号，下一根 `1h` open 市价成交；入场后立即具备 stop-market/TP 保护；同 K 双触发按 stop-first；跳空穿越 stop 按 open 成交。
- 成本：`0.001` fee/fill、`4 bps` slippage/fill，并计入 Binance 历史资金费。

## 指标与搜索面

搜索覆盖 EMA/MACD、RSI、Stochastic、CCI、Williams %R、ADX/DI、ATR、Bollinger、Keltner、Donchian、rolling VWAP、成交量、动量、wick/body 结构、`4h/12h/1d` 闭合 regime、固定/风险预算仓位、固定 bracket/trailing exit 及 long/short/both。

## 当前状态

`V1 registered diagnostic baseline；V2 registered paper-audit observation；V3 registered diagnostic micro-tune observation；not live-ready`。

2026-07-02 共生成 `300,768` 组配置（`768` curated + `300,000` random），`41,898` 组满足最低评分条件，prefit 硬门槛命中 `0`。prefit 预冻结冠军为 `Keltner breakout + CCI reversal` ensemble：prefit `2.82x` 年化倍率、`-18.68%` 回撤、`68.29%` 胜率；最近三个月 locked OOS 降至 `0.17x`、`-42.73%`、`38.46%`。该边界按用户要求登记为 `BTC-1H-Adaptive-Regime-V1`，但不生成 live spec。

V1 全参数消融覆盖两腿 `78/78` 个字段槽：`27` 个 active tunable、`12` 个 contract fixed、`35` 个 baseline fixed、`4` 个 neutral fixed。clean interface 仅保留 `27` 个可调参数，删除或硬编码 `51` 个槽，和 V1 逐笔完全等价。

clean tune 每腿各采样 `150,000` 组，组合 `122,500` 组；得到 scaled frontier observation：prefit `3.18x / -13.99% / 84.85%`，reused holdout `1.52x / -13.48% / 81.82%`，current full `2.88x / -13.99% / 84.42%`；K+2 prefit `2.50x / -19.70% / 80.30%`。该观察已按用户要求登记为 `BTC-1H-Adaptive-Regime-V2`，但仍需新增 forward trades 与生产 runner，状态为 `paper-audit observation / not live-ready`。

2026-07-06 已对 V2 冻结参数执行全参数消融：覆盖两腿 `78/78` 个 `StrategyConfig` 字段槽，生成 `205` 行 baseline/variant 证据；相对 V2 基线，one-at-a-time prefit 严格改善行数为 `5`。该消融仅为敏感性审计，不登记 V2.1，不改变 `not live-ready`。

基于 V2 消融前沿方向的受约束微调生成 `BTC-1H-AR-V2-MICRO-TUNE-2026-07-06` 观察：`7,200` 组网格中 `3,852` 组满足 prefit 年化高于 V2、train/validation/prefit 胜率均 `>=80%`、回撤均 `<20%`；首选组合 prefit `6.16x / -12.87% / 87.30%`，current full `5.27x / -17.47% / 86.49%`。该观察已按用户要求登记为 `BTC-1H-Adaptive-Regime-V3`，仍 `not live-ready`。

2026-07-06 已对 V3 冻结参数执行全参数消融与多窗口回测：全消融覆盖两腿 `78/78` 个字段槽，生成 `205` 行 baseline/variant 证据，相对 V3 基线的严格改善单字段为 `0`；多窗口显示 recently unlocked holdout/recent 90d 为 `1.91x / +17.34% / -17.47% / 81.82% / 11`，最近 30d 为 `1.29x / +2.13% / -17.47% / 75.00% / 4`，最近 7d 无交易。该诊断不产生 V3.1/V4，也不改变 `not live-ready`。

2026-07-07 完成 V3 参数必要性审计：`27` 个 clean active 槽位中有 `8` 个在 V3 冻结值下从不生效（两腿 `max_atr_bps`、两腿 `cooldown_bars=0`、Keltner `min_dir_roc_bps`/`roc_window`/`max_aligned_funding_bps`/`max_hold_bars`），移除后与 V3 逐笔路径完全等价；最小等价表面为 `19` 个必要参数。随后在最小表面上做受约束微调（杠杆冻结）：`24,576` 组网格中没有组合能三项同时严格优于 V3；Pareto 口径（年化更高、回撤与胜率不劣）`8` 组，首选 prefit `6.24x / -12.87% / 87.30%`（CCI `max_hold_bars 72->96`、`max_dist_ema_bps 750->700`），改善幅度约 `+1.4%` 年化倍率，属于噪声级别。结论：V3 在其冻结邻域已是局部最优，不登记新版本。

## 入口

- `btc-1h-ar-core-ledger.md`：家族主账。
- `canonical-specs/btc-1h-ar-v1-baseline-spec.md`：V1 完整冻结规格。
- `decision-log.md`：研究决策。
- `scripts/fetch_btc_binance_1h.py`：两年 K 线、资金费、合约快照抓取与质量审计。
- `scripts/research_btc_1h_adaptive_regime_search.py`：locked OOS 多指标宽搜索。
- `scripts/audit_btc_1h_adaptive_regime_boundary.py`：延迟、成本、仓位、单腿、参数邻域、月度、bootstrap 与实盘可执行审计。
- `scripts/btc_1h_ar_v1.py`：V1 冻结配置与复现入口。
- `scripts/research_btc_1h_ar_v1_full_ablation.py`：V1 `78/78` 字段槽全参数消融。
- `scripts/btc_1h_ar_v1_clean.py`：27 参数 clean-equivalent interface。
- `scripts/research_btc_1h_ar_v1_clean_tune.py`：prefit-only 双腿高密度微调。
- `scripts/audit_btc_1h_ar_v1_scaled_frontier.py`：最终缩放前沿、K+2、成本、邻域与 forward-readiness 审计。
- `scripts/research_btc_1h_ar_v2_full_ablation.py`：V2 冻结参数 `78/78` 字段槽全参数消融。
- `scripts/research_btc_1h_ar_v2_micro_tune.py`：基于 V2 消融前沿方向的受约束 active 参数微调。
- `scripts/btc_1h_ar_v3.py`：V3 冻结配置与复现入口。
- `scripts/research_btc_1h_ar_v3_full_ablation.py`：V3 冻结参数 `78/78` 字段槽全参数消融。
- `scripts/research_btc_1h_ar_v3_window_backtest.py`：V3 canonical/recent/calendar/half-year/monthly 多窗口回测。
- `scripts/research_btc_1h_ar_v3_param_necessity.py`：V3 参数必要性审计与最小等价表面验证。
- `scripts/research_btc_1h_ar_v3_minimal_micro_tune.py`：V3 最小表面（19 必要参数、杠杆冻结）受约束微调。
- `diagnostics/btc-binance-1h-data-quality-2026-07-02.md`：两年数据质量报告。
- `diagnostics/btc-1h-adaptive-regime-search-2026-07-02.md`：30 万组主搜索报告。
- `diagnostics/btc-1h-adaptive-regime-boundary-audit-2026-07-02.md`：最终 NO-GO 审计。
- `ablations/btc-1h-ar-v1-full-parameter-ablation-2026-07-02.md`：V1 全参数消融与删参分类。
- `ablations/btc-1h-ar-v2-full-parameter-ablation-2026-07-06.md`：V2 全参数消融与单字段敏感性审计。
- `research-notes/btc-1h-ar-v2-micro-tune-2026-07-06.md`：V2 微调观察，已登记为 `BTC-1H-Adaptive-Regime-V3`。
- `ablations/btc-1h-ar-v3-full-parameter-ablation-2026-07-06.md`：V3 全参数消融与单字段敏感性审计。
- `research-notes/btc-1h-ar-v3-window-backtest-2026-07-06.md`：V3 多窗口回测。
- `research-notes/btc-1h-ar-v3-param-necessity-2026-07-07.md`：V3 参数必要性审计与 19 参数最小等价表面。
- `research-notes/btc-1h-ar-v3-minimal-micro-tune-2026-07-07.md`：V3 最小表面受约束微调（结论：V3 局部最优）。
- `research-notes/btc-1h-ar-v1-clean-parameter-tune-2026-07-02.md`：clean surface 微调。
- `research-notes/btc-1h-ar-v1-scaled-frontier-audit-2026-07-02.md`：当前首选 paper-audit observation。
- `artifacts/`：可复现证据；默认由 `.gitignore` 忽略。
