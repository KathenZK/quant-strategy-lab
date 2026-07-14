# ETH-1H-Adaptive-Regime 主账

## 家族身份

- 完整名称：`ETH-1H-Adaptive-Regime`
- 短 id：`ETH-1H-AR`
- 市场：Binance USD-M Futures `ETHUSDT` perpetual
- 周期：`1h`
- 独立性：不继承任何 BTC、HYPE 或其他资产策略的版本号。

## 当前状态

`V4 registered high-win strategy refined observation / NO-GO / not promoted / not live-ready`

V4 已按用户要求登记为 V3 高胜率频率搜索后的全策略风险重配观察值。版本登记只冻结可复现身份；由于 K+3 / 高成本压力仍有失败边界，且没有 `2026-07-03` 之后的 fresh forward 与生产执行证据，不构成 promotion，也不生成 live spec。

## 版本规则

- `V1`：首轮 `600,768` 组广搜的 prefit 冻结冠军，保留原始 `StrategyConfig` 字段面，用作 registered baseline。
- `V2`：V1 全参数消融后生成的 `29` 参数 clean interface 上的 prefit-only tuned observation。
- `V2.1`：V2 全参数消融域上的 high-win guided tuned observation。
- `V3`：V2.1 全参数消融后删除 `2` 个 inert 字段，在 `27` 参数 clean surface 上得到的严格改善 observation。
- `V4`：在 V3 的 `27` 参数 clean surface 上做高胜率频率搜索，再对稳健候选做两腿杠杆重配；目标是交易数上升、胜率只允许小幅下降、DD 尽量压在 `20%` 内。
- `candidate`、`paper-live`、`dry-run`、`handoff` 或 `live` 需要新增 forward trades、成本/延迟/邻域审计、生产状态机和 live-executable 边界通过；V4 当前不满足。

## 版本表

| 版本 | 状态 | 规则与指标 | 证据 | live-readiness |
| --- | --- | --- | --- | --- |
| `ETH-1H-Adaptive-Regime-V1` | registered baseline | BB breakout long + RSI reversal both；prefit `2.8109x / -16.29% / 71.57% / 102`；locked OOS `0.5196x / -20.87% / 14.29% / 7`；full `2.2462x / -20.87% / 67.89% / 109` | [version spec](specs/eth-1h-ar-v1-baseline-spec.md)、[首轮搜索](diagnostics/eth-1h-adaptive-regime-search-2026-07-03.md)、[全消融](ablations/eth-1h-ar-v1-full-parameter-ablation-2026-07-03.md)、[clean tune](notes/eth-1h-ar-v1-clean-parameter-tune-2026-07-03.md)、[最终审计](notes/eth-1h-ar-v1-clean-tune-audit-2026-07-03.md) | `NO-GO / not live-ready` |
| `ETH-1H-Adaptive-Regime-V2` | registered tuned observation | V1 clean interface tuned observation；prefit `3.4333x / -15.02% / 73.33% / 105`；reused holdout `0.4323x / -18.93% / 50.00% / 10`；full `2.6071x / -18.93% / 71.30% / 115` | [version spec](specs/eth-1h-ar-v2-clean-tuned-spec-2026-07-06.md)、[V1 全消融](ablations/eth-1h-ar-v1-full-parameter-ablation-2026-07-03.md)、[clean tune](notes/eth-1h-ar-v1-clean-parameter-tune-2026-07-03.md)、[最终审计](notes/eth-1h-ar-v1-clean-tune-audit-2026-07-03.md)、[V2 全消融](ablations/eth-1h-ar-v2-full-parameter-ablation-2026-07-06.md)、[V2 高胜率微调](notes/eth-1h-ar-v2-ablation-guided-tune-2026-07-06.md) | `NO-GO / not live-ready` |
| `ETH-1H-Adaptive-Regime-V2.1` | registered high-win tuned observation | V2 消融引导 high-win observation；prefit `3.7853x / -14.98% / 91.67% / 36`；reused holdout `0.7048x / -19.55% / 50.00% / 4`；full `3.0277x / -19.55% / 87.50% / 40` | [version spec](specs/eth-1h-ar-v2-1-high-win-tuned-spec-2026-07-06.md)、[V2 全消融](ablations/eth-1h-ar-v2-full-parameter-ablation-2026-07-06.md)、[V2.1 微调](notes/eth-1h-ar-v2-ablation-guided-tune-2026-07-06.md) | `NO-GO / not live-ready` |
| `ETH-1H-Adaptive-Regime-V3` | registered clean tuned observation | V2.1 clean-surface strict-improvement observation；prefit `4.0591x / -12.15% / 100.00% / 42`；reused holdout `0.8706x / -15.70% / 50.00% / 4`；full `3.3084x / -15.70% / 95.65% / 46` | [version spec](specs/eth-1h-ar-v3-clean-tuned-spec-2026-07-07.md)、[V2.1 全消融](ablations/eth-1h-ar-v2-1-full-parameter-ablation-2026-07-07.md)、[V3 clean 微调](notes/eth-1h-ar-v2-1-clean-tune-2026-07-07.md) | `NO-GO / not live-ready` |
| `ETH-1H-Adaptive-Regime-V4` | registered high-win strategy refined observation | V3 clean surface 高胜率频率搜索 + 杠杆重配；prefit `5.4898x / -14.29% / 91.04% / 67`；reused holdout `1.0601x / -17.08% / 66.67% / 12`；full `4.4124x / -17.08% / 87.34% / 79` | [version spec](specs/eth-1h-ar-v4-high-win-strategy-refined-spec-2026-07-13.md)、[频率优化](notes/eth-1h-ar-v3-high-win-frequency-tune-2026-07-13.md)、[全策略风险优化](notes/eth-1h-ar-v3-high-win-strategy-refine-2026-07-13.md)、[复现入口](scripts/eth_1h_ar_v4.py) | `NO-GO / not live-ready` |

## V4 登记说明

- 来源 observation：`ETH-1H-AR-V3-HIGH-WIN-STRATEGY-REFINE-2026-07-13`。
- 相对 V3：prefit 交易 `42 -> 67`，current full `46 -> 79`；current-full 胜率 `95.65% -> 87.34%`（下降约 `8.3` 个百分点，但仍高胜率）；current-full DD `-15.70% -> -17.08%`；reused holdout 只读从 `-3.39%` 转为 `+1.46%`。
- 失败边界：K+3 prefit DD `-23.85%`；`12 bps` / `fee12_slip8` / `double_cost` 下 reused holdout 只读略负；没有 fresh forward 与 runner 证据。
- 结论：登记为 V4，但不 promotion，不生成 live spec。
