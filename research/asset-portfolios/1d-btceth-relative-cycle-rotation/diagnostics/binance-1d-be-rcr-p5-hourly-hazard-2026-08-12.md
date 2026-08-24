# BIN-1D-BE-RCR P5 Hourly-Hazard 结论（2026-08-12）

## 裁决

- P5：`0/6 PASS / HARD-GATE-FAILED / explore / not promoted / not live-ready`
- 样本：`5,778` 个 06/12/18 UTC landmarks、`332` 个 danger labels；growth/risk danger episodes 为 `39/20`
- audit/prospective：未读取；版本：未登记

| feature | growth AUC | risk AUC | BTC AUC | ETH AUC | weakest edge |
|---|---:|---:|---:|---:|---:|
| ASSET_OPPOSE6 | 0.502 | 0.464 | 0.505 | 0.481 | -5.1pp |
| ASSET_OPPOSE24 | 0.481 | 0.437 | 0.455 | 0.469 | -6.6pp |
| MARKET_OPPOSE6 | 0.493 | 0.455 | 0.456 | 0.490 | -4.0pp |
| ROLE_VIOLATION24 | 0.473 | 0.432 | 0.485 | 0.451 | -7.1pp |
| VOL_SHOCK6_72 | 0.561 | 0.575 | 0.514 | 0.589 | -0.9pp |
| REL_EXTREME_RISE6 | 0.527 | 0.537 | 0.555 | 0.516 | +0.8pp |

小时级价格动量、relative-role、vol shock 与相对极端增量均未跨 anchor/asset 识别未来 24h `>=8%` adverse path。样本容量和 danger episode 数均充足，因此失败不是低样本 blocker。

至此 price-only 的 entry gate、日频 transition 与小时 hazard 均已受约束失败。下一步只允许检验冻结数据中尚未用于本家族的真实 funding/crowding 状态；若仍无稳定信息，则关闭 `BIN-1D-BE-RCR` 研究线并另立机制家族。

复现：

```bash
.venv/bin/python research/asset-portfolios/1d-btceth-relative-cycle-rotation/scripts/audit_binance_1d_be_rcr_p5_hourly_hazard.py --run-date 2026-08-12
```
