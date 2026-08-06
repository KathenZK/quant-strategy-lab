# BTC-1H-Adaptive-Regime Core Ledger

## Family Identity

- 完整家族名：`BTC-1H-Adaptive-Regime`
- 别名：`BTC-1H-AR`
- 市场：Binance USD-M `BTCUSDT` 永续，`1h`
- 机制：Keltner breakout 趋势腿 + CCI reversal 反转腿的单仓 ensemble。
- 边界：不继承 HYPE/ETH 等资产的 Adaptive-Regime 版本号或参数。

## Current State

- 当前版本：`BTC-1H-Adaptive-Regime-V4`。
- 状态：V1–V4 均 `registered`；全家族 `not promoted / not live-ready`。
- V1 locked/reused holdout 明显失败；V2 缩放改善，V3 微调增强，V4 只是 V3 的 19 参数最小等价表达。
- V4 三类结构优化顺序验证严格增量 gate 均 `0`，没有 V5；19 参数邻域微调已停止。
- 下一门：新信息源或 untouched forward，再做 purged walk-forward、成本/延迟和 live-executable audit。

## Version Rules

- V1 为用户登记基线；V2/V3 是缩放与 micro-tune 观察；V4 是逐笔等价参数清理。
- 参数清理不提供新增收益证据；窗口复核使用 reused data，不是新鲜 OOS。
- 登记只冻结身份；不得据高年化推断 candidate、dry-run、handoff 或 live。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| `V1` | registered baseline / NO-GO | prefit-frozen Keltner + CCI ensemble | prefit `2.82x/-18.68%/68.29%`；reused holdout `0.17x/-42.73%/38.46%` | [spec](specs/btc-1h-ar-v1-baseline-spec.md) · [boundary](diagnostics/btc-1h-adaptive-regime-boundary-audit-2026-07-02.md) | 不 promotion |
| `V2` | registered observation / not promoted | V1 clean surface，Keltner 1.8x / CCI 2.7x | prefit `3.18x/-13.99%/84.85%`；holdout `1.52x/-13.48%/81.82%` | [audit](notes/btc-1h-ar-v1-scaled-frontier-audit-2026-07-02.md) · [ablation](ablations/btc-1h-ar-v2-full-parameter-ablation-2026-07-06.md) | 等 forward |
| `V3` | registered micro-tune / not promoted | Keltner 2.4x / CCI 3.5x，CCI TP/ADX/cooldown 微调 | prefit `6.16x/-12.87%/87.30%`；holdout `1.90x/-17.47%/81.82%` | [tune](notes/btc-1h-ar-v2-micro-tune-2026-07-06.md) · [windows](notes/btc-1h-ar-v3-window-backtest-2026-07-06.md) | not live-ready |
| `V4` | registered clean-equivalent / not promoted | V3 的 19 必要参数表面 | 与 V3 逐笔等价；current full `5.27x/-17.47%/86.49%/74` | [necessity](notes/btc-1h-ar-v3-param-necessity-2026-07-07.md) · [windows](notes/btc-1h-ar-v4-window-backtest-2026-07-07.md) | 无新增收益证据 |

## Shared Assumptions

- 数据：Binance BTCUSDT 闭合 `1h` K；split 与窗口见各 spec/report。
- 成本：fee `0.001/fill`、slippage `4 bps/fill`，计历史 funding。
- 执行：Keltner 双向、CCI long-only；闭合 K 信号，next-open，固定 TP/SL。
- 仓位：单仓不加仓；冲突按各腿 prefit score，持仓期间忽略新信号。
- V4 参数：8 个 Keltner + 11 个 CCI 必要参数；8 个槽位中和后与 V3 逐笔等价，配置 JSON 是参数真值。

## Evidence Map

- 参数配置：[V4 JSON](artifacts/btc_1h_ar_v4_config_2026-07-07.json) · [V3 JSON](artifacts/btc_1h_ar_v3_config_2026-07-06.json)
- 核心消融：[V2](ablations/btc-1h-ar-v2-full-parameter-ablation-2026-07-06.md) · [V3](ablations/btc-1h-ar-v3-full-parameter-ablation-2026-07-06.md)
- 局部最优：[minimal tune](notes/btc-1h-ar-v3-minimal-micro-tune-2026-07-07.md)
- 结构研究：[study](notes/btc-1h-ar-v4-structural-optimization-study-2026-07-10.md) · [trials](notes/btc-1h-ar-v4-structural-trials-2026-07-13.md)
- 决策：[decision-log.md](decision-log.md) · 脚本/产物：[scripts/README.md](scripts/README.md) · [artifacts/README.md](artifacts/README.md)
