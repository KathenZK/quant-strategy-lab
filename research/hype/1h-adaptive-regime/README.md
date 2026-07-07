# HYPE-1H-Adaptive-Regime

Family id：`HYPE-1H-AR`

本家族研究 Binance USD-M Futures `HYPEUSDT` `1h` 自适应市场状态策略。核心问题是：趋势、突破与均值回归不能在所有市场状态下同时有效，策略应只在闭合 K 线可确认的 regime 中启用对应入场腿，并使用入场后立即生效的保护性 bracket。

本家族独立于现有 `HYPE-15M-Multi-Indicator-Intraday`、`HYPE-EMA-Crossover`、`HYPE-EMA-Trend-Breakout`、`HYPE-5M-Pullback-Trail` 和 `HYPE-6H-RS4-Regime-Switch`。不得用裸版本号跨家族引用。

## 研究范围

- 市场：Binance USD-M Futures `HYPEUSDT` perpetual。
- 周期：`1h`。
- 数据：从合约可用的第一根闭合 `1h` K 到运行时最后一根闭合 K；同时保留 Binance FAPI raw evidence、标准 normalized 数据湖分区、资金费历史和合约过滤器快照。
- 信号：EMA、MACD、RSI、Stochastic、ADX/DI、ATR、Bollinger、Keltner、Donchian、rolling VWAP、成交量、收益动量、K 线结构及闭合 `4h/12h/1d` regime。
- 执行：闭合 K 生成信号，下一根 `1h` open 市价入场；成交后立即放置 stop-market / take-profit；同 K 双触发按 stop-first；跳空穿越 stop 按 open 成交。
- 成本：Binance 仓库默认 `0.001` fee/fill、`4 bps` slippage/fill，并单独计入历史资金费。

## 用户硬门槛

- 年化权益倍率 `>= 10.0x`（同步报告 annual return percent，`10.0x` 对应 `+900%`）。
- 胜率 `>= 50%`。
- 最大回撤 `< 20%`。
- 必须通过时间顺序 train/validation/locked holdout、成本压力、延迟、参数邻域和 live-executable 审计，才能讨论 promotion。

## 当前状态

`HYPE-1H-Adaptive-Regime-V1` 已登记为历史最强冻结基线；`HYPE-1H-Adaptive-Regime-V2` 已登记为全参数消融后的干净等价版；`HYPE-1H-Adaptive-Regime-V3` 已按用户要求登记为 V2 消融引导组合 `di_roc_off__stoch_th55` 的 diagnostic baseline；`HYPE-1H-Adaptive-Regime-V4` 已登记为 V3 剪枝后 prefit 三场景微调的 diagnostic pruned tuned baseline。全部版本都维持 `NO-GO / not live-ready / not promoted`。

刷新至 `2026-07-02 02:00 UTC` 后，V1/V2 current full 完全相同：`9.6838x` 年化权益倍率、`78.26%` 胜率、`-19.64%` 最大回撤、`69` 笔；reused holdout 仅 `5.1305x`。V1 全字段消融覆盖 `76/76` 字段槽，V2 删除 `40` 个 dormant 或固定状态机字段槽，DI、Stoch 与 merged 交易签名逐笔完全相等。

V4 参数槽从 V3 的 `34` 个剪枝到 `25` 个，base K+1 current full 为 `22.8128x / -19.11% / 81.08% / 74 trades`，reused holdout 为 `13.0662x / -19.11% / 77.78% / 18 trades`。但 K+2 current full `8.7014x / -23.56%`、8bps current full `15.3677x / -22.46%`，压力回撤仍穿越 `20%`；V4 是登记版诊断基线，不是实盘版本。

## 入口

- `hype-1h-ar-core-ledger.md`：本家族主账；登记 V1/V2/V3/V4、当前状态、版本规则和后续版本约束。
- `decision-log.md`：决策与状态变更。
- `scripts/fetch_hype_binance_1h.py`：全量 K 线、资金费与合约快照抓取和质量审计。
- `diagnostics/hype-binance-1h-data-quality-2026-07-01.md`：`9,526` 根全量闭合 K 的质量与校验值。
- `scripts/research_hype_1h_adaptive_regime_search.py`：多阶段广泛搜索与 locked holdout 评估。
- `scripts/research_hype_1h_adaptive_regime_refine.py`：只基于 prefit Pareto 边界的高密度邻域搜索。
- `scripts/audit_hype_1h_adaptive_regime_boundary.py`：延迟、成本、消融、月度、bootstrap 与实盘可执行审计。
- `canonical-specs/hype-1h-ar-v1-baseline-spec.md`：V1 正式版本规格。
- `canonical-specs/hype-1h-ar-v2-clean-baseline-spec.md`：V2 干净等价版本、删除字段和微调结论。
- `canonical-specs/hype-1h-ar-v3-baseline-spec.md`：V3 diagnostic baseline；来源为 `di_roc_off__stoch_th55`，仍不可实盘。
- `canonical-specs/hype-1h-ar-v4-pruned-tuned-baseline-spec.md`：V4 diagnostic pruned tuned baseline；列出剪枝后的 `25` 个参数并逐项解释。
- `ablations/hype-1h-ar-v1-full-parameter-ablation-2026-07-02.md`：`76/76` 字段槽全量消融。
- `ablations/hype-1h-ar-v2-full-parameter-ablation-2026-07-02.md`：V2 clean `34` 字段槽全参数消融；完整 target-like 通过 `0` 行。
- `ablations/hype-1h-ar-v3-full-parameter-ablation-2026-07-06.md`：V3 clean `34` 字段槽全参数消融与最近/滚动时间片复核；target-like 通过 `5` 行，但未包含 K+2/滑点完整通过。
- `research-notes/hype-1h-ar-v2-ablation-combo-retest-2026-07-06.md`：V2 消融引导组合复测；base/K+2/8bps 完整通过 `0/16`。
- `research-notes/hype-1h-ar-v3-prune-and-tune-2026-07-07.md`：验证 V3 可移除 `9` 个 dormant 字段槽（路径 exact equal），剪枝后 prefit 微调最佳组合 base 三项超越 V3，但 K+2/8bps 回撤仍穿越 `20%`。
- `diagnostics/hype-1h-ar-v2-tune-frontier-live-audit-2026-07-02.md`：基础达标微调前沿的成本/延迟否决。
- `research-notes/hype-1h-ar-v2-live-robust-prefit-tune-2026-07-02.md`：把 K+2 和 8 bps 提前放入 prefit 的扩大搜索。
- `canonical-specs/hype-1h-ar-boundary-reproduction-not-live-ready-2026-07-01.md`：最强边界组合完整复现规格；不可实盘。
- `diagnostics/hype-1h-adaptive-regime-search-2026-07-01.md`：第一轮广搜报告。
- `diagnostics/hype-1h-adaptive-regime-refine-2026-07-01.md`：第二轮邻域搜索报告。
- `diagnostics/hype-1h-adaptive-regime-boundary-audit-2026-07-01.md`：最终严格审计与 `NO-GO` 结论。
- `diagnostics/`：搜索、稳健性和 live-executable 报告。
- `artifacts/`：脚本生成的 JSON/CSV/Parquet 证据（默认由 `.gitignore` 忽略，可复现）。
