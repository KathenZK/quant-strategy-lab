# ETH-1H-Adaptive-Regime 主账

## 家族身份

- 完整名称：`ETH-1H-Adaptive-Regime`
- 短 id：`ETH-1H-AR`
- 市场：Binance USD-M Futures `ETHUSDT` perpetual
- 周期：`1h`
- 独立性：不继承任何 BTC、HYPE 或其他资产策略的版本号。

## 当前状态

`V1 registered diagnostic baseline / NO-GO / not promoted / not live-ready`

V1 已按用户要求登记，但最近三个月 locked OOS 明确失败。版本登记冻结身份，不构成 promotion，也不生成 live spec。

## 版本表

| 版本 | 状态 | 规则与指标 | 证据 | live-readiness |
| --- | --- | --- | --- | --- |
| `ETH-1H-Adaptive-Regime-V1` | registered diagnostic baseline | BB breakout long + RSI reversal both；prefit `2.8109x / -16.29% / 71.57% / 102`；locked OOS `0.5196x / -20.87% / 14.29% / 7`；full `2.2462x / -20.87% / 67.89% / 109` | [canonical spec](canonical-specs/eth-1h-ar-v1-baseline-spec.md)、[首轮搜索](diagnostics/eth-1h-adaptive-regime-search-2026-07-03.md)、[全消融](ablations/eth-1h-ar-v1-full-parameter-ablation-2026-07-03.md)、[clean tune](research-notes/eth-1h-ar-v1-clean-parameter-tune-2026-07-03.md)、[最终审计](research-notes/eth-1h-ar-v1-clean-tune-audit-2026-07-03.md) | `NO-GO / not live-ready` |

## V1 后续观察（不登记新版本）

- `33` 参数 clean interface 与 V1 逐笔完全等价；删除或硬编码 `45/78` 个字段槽。
- clean tuned observation：prefit `3.4333x / -15.02% / 73.33% / 105`；current full `2.6071x / -18.93% / 71.30% / 115`。
- reused holdout `0.4323x / -18.93% / 50.00% / 10`，收益仍为负；邻域 reused-holdout positive `0/66`，bootstrap 原始硬形状命中率 `0%`。
- 结论：不登记 V1.1/V2，不生成 live spec；需要冻结参数后的新增 forward trades 才能继续讨论。
