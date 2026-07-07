# ETH-1H-Adaptive-Regime 主账

## 家族身份

- 完整名称：`ETH-1H-Adaptive-Regime`
- 短 id：`ETH-1H-AR`
- 市场：Binance USD-M Futures `ETHUSDT` perpetual
- 周期：`1h`
- 独立性：不继承任何 BTC、HYPE 或其他资产策略的版本号。

## 当前状态

`V3 registered diagnostic clean tuned observation / NO-GO / not promoted / not live-ready`

V3 已按用户要求登记为 V2.1 全参数消融、删参后的 clean 参数面严格改善微调版本。版本登记只冻结可复现身份；由于最近三个月 reused holdout 仍为负，且没有新增 forward trades 与生产执行证据，不构成 promotion，也不生成 live spec。

## 版本规则

- `V1`：首轮 `600,768` 组广搜的 prefit 冻结冠军，保留原始 `StrategyConfig` 字段面，用作 registered diagnostic baseline。
- `V2`：V1 全参数消融后生成的 `29` 参数 clean interface 上的 prefit-only tuned observation；继承 V1 的执行契约、数据切分、成本和资金费口径，参数选择不使用最近三个月 reused holdout。
- `V2.1`：V2 全参数消融域上的 high-win guided tuned observation；满足 current-full 高胜率形状，但 reused holdout 和压力测试失败。
- `V3`：V2.1 全参数消融后删除 `2` 个 inert 字段，在 `27` 参数 clean surface 上得到的严格改善 observation；current full 三项优于 V2.1，但 reused holdout 仍为负。
- `candidate`、`paper-live`、`dry-run`、`handoff` 或 `live` 需要新增 forward trades、成本/延迟/邻域审计、生产状态机和 live-executable 边界通过；V3 当前不满足。

## 版本表

| 版本 | 状态 | 规则与指标 | 证据 | live-readiness |
| --- | --- | --- | --- | --- |
| `ETH-1H-Adaptive-Regime-V1` | registered diagnostic baseline | BB breakout long + RSI reversal both；prefit `2.8109x / -16.29% / 71.57% / 102`；locked OOS `0.5196x / -20.87% / 14.29% / 7`；full `2.2462x / -20.87% / 67.89% / 109` | [canonical spec](canonical-specs/eth-1h-ar-v1-baseline-spec.md)、[首轮搜索](diagnostics/eth-1h-adaptive-regime-search-2026-07-03.md)、[全消融](ablations/eth-1h-ar-v1-full-parameter-ablation-2026-07-03.md)、[clean tune](research-notes/eth-1h-ar-v1-clean-parameter-tune-2026-07-03.md)、[最终审计](research-notes/eth-1h-ar-v1-clean-tune-audit-2026-07-03.md) | `NO-GO / not live-ready` |
| `ETH-1H-Adaptive-Regime-V2` | registered diagnostic tuned observation | V1 clean interface tuned observation；prefit `3.4333x / -15.02% / 73.33% / 105`；reused holdout `0.4323x / -18.93% / 50.00% / 10`；full `2.6071x / -18.93% / 71.30% / 115` | [canonical spec](canonical-specs/eth-1h-ar-v2-clean-tuned-spec-2026-07-06.md)、[V1 全消融](ablations/eth-1h-ar-v1-full-parameter-ablation-2026-07-03.md)、[clean tune](research-notes/eth-1h-ar-v1-clean-parameter-tune-2026-07-03.md)、[最终审计](research-notes/eth-1h-ar-v1-clean-tune-audit-2026-07-03.md)、[V2 全消融](ablations/eth-1h-ar-v2-full-parameter-ablation-2026-07-06.md)、[V2 高胜率微调](research-notes/eth-1h-ar-v2-ablation-guided-tune-2026-07-06.md) | `NO-GO / not live-ready` |
| `ETH-1H-Adaptive-Regime-V2.1` | registered diagnostic high-win tuned observation | V2 消融引导 high-win observation；prefit `3.7853x / -14.98% / 91.67% / 36`；reused holdout `0.7048x / -19.55% / 50.00% / 4`；full `3.0277x / -19.55% / 87.50% / 40` | [canonical spec](canonical-specs/eth-1h-ar-v2-1-high-win-tuned-spec-2026-07-06.md)、[V2 全消融](ablations/eth-1h-ar-v2-full-parameter-ablation-2026-07-06.md)、[V2.1 微调](research-notes/eth-1h-ar-v2-ablation-guided-tune-2026-07-06.md) | `NO-GO / not live-ready` |
| `ETH-1H-Adaptive-Regime-V3` | registered diagnostic clean tuned observation | V2.1 clean-surface strict-improvement observation；prefit `4.0591x / -12.15% / 100.00% / 42`；reused holdout `0.8706x / -15.70% / 50.00% / 4`；full `3.3084x / -15.70% / 95.65% / 46` | [canonical spec](canonical-specs/eth-1h-ar-v3-clean-tuned-spec-2026-07-07.md)、[V2.1 全消融](ablations/eth-1h-ar-v2-1-full-parameter-ablation-2026-07-07.md)、[V3 clean 微调](research-notes/eth-1h-ar-v2-1-clean-tune-2026-07-07.md) | `NO-GO / not live-ready` |

## V2 登记说明

- `29` 参数 clean interface 与 V1 逐笔完全等价；删除或硬编码 `49/78` 个字段槽。
- V2 clean tuned observation：prefit `3.4333x / -15.02% / 73.33% / 105`；current full `2.6071x / -18.93% / 71.30% / 115`。
- reused holdout `0.4323x / -18.93% / 50.00% / 10`，收益仍为负；邻域 reused-holdout positive `0/66`，bootstrap 原始硬形状命中率 `0%`。
- 结论：登记为 V2 但不 promotion，不生成 live spec；需要冻结参数后的新增 forward trades 才能继续讨论。

## V2.1 登记说明

- V2 全参数消融覆盖 `29/29` 个 clean 参数槽；one-at-a-time 行数（含 baseline）`140`，prefit 严格改善 `2` 行，单字段 high-win gate `0` 行。
- V2 消融引导高胜率微调评估 `202,500` 个组合，可评分 `148,346`，满足 train/validation/prefit `win>=80%`、DD `<20%`、prefit annual 高于 V2 的组合 `65` 个。
- 冻结版本 `ETH-1H-Adaptive-Regime-V2.1`：prefit `3.7853x / -14.98% / 91.67% / 36`；current full `3.0277x / -19.55% / 87.50% / 40`。
- 失败边界：reused holdout `0.7048x / -19.55% / 50.00% / 4` 仍为负；K+2 prefit DD `-20.34%`，double-cost full DD `-21.40%`，因此 V2.1 不是 candidate、paper-live 或 live。

## V3 登记说明

- V2.1 全参数消融覆盖 `29/29` 个 clean 参数槽，one-at-a-time 行数（含 baseline）`140`；`bb_break.ema_htf` 与 `bb_break.max_aligned_funding_bps` 判定为 merged-path inert（无意义参数），硬编码后 clean surface 收敛到 `27` 个可调参数，与 V2.1 逐笔完全等价。
- 在 27 参数干净面上微调：每腿随机 `100,000` 组，组合评估 `160,000`，相对 V2.1“收益更高、胜率更高、回撤更小”的严格改善组合 `5` 个。
- 冻结版本 `ETH-1H-Adaptive-Regime-V3`：prefit `4.0591x / -12.15% / 100.00% / 42`；current full `3.3084x / -15.70% / 95.65% / 46`；三项全部优于 V2.1。
- 失败边界：reused holdout `0.8706x / -15.70% / 50.00% / 4` 仍为负（较 V2.1 的 `-8.35%` 收敛到 `-3.39%` 但未转正）；K+2 下 prefit 退化到 `2.7964x / -16.66% / 90.24%`、holdout 胜率 `25%`。V3 不是 candidate、paper-live 或 live。
- 证据：[V2.1 全消融](ablations/eth-1h-ar-v2-1-full-parameter-ablation-2026-07-07.md)、[V2.1 clean 微调](research-notes/eth-1h-ar-v2-1-clean-tune-2026-07-07.md)。
