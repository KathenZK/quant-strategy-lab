# BIN-1D-BE-RCR P4 Holding-Transition 结论（2026-08-12）

## 裁决

- P4：`0/6 PASS / HARD-GATE-FAILED / explore / not promoted / not live-ready`
- 样本：`1,811` 个在仓日频 landmarks、`269` 个 danger labels；growth/risk 独立 danger episodes 为 `44/21`
- audit/prospective：未读取；版本：未登记

| feature | growth AUC | risk AUC | BTC AUC | ETH AUC | weakest edge |
|---|---:|---:|---:|---:|---:|
| FAST_OPPOSE5 | 0.452 | 0.399 | 0.386 | 0.449 | -12.9pp |
| MARKET_OPPOSE5 | 0.470 | 0.407 | 0.369 | 0.471 | -9.5pp |
| ROLE_VIOLATION20 | 0.431 | 0.423 | 0.497 | 0.433 | -10.9pp |
| REL_EXTREME_RISE3 | 0.567 | 0.550 | 0.515 | 0.597 | +0.1pp |
| GIVEBACK_ATR14 | 0.467 | 0.434 | 0.399 | 0.471 | -8.3pp |
| ENTRY_LOSS_ATR14 | 0.427 | 0.371 | 0.397 | 0.398 | -17.8pp |

日频短动量反转、role violation、回吐与浮亏均不能提前识别未来三日 `>=8%` adverse path。多个 AUC 低于 0.5，提示简单 trailing/giveback exit 会在随后均值回归前过早离场；这与 P1 快速 EMA 损害收益一致。

因此不建立日频 state-transition exit，不搜索阈值。后续只允许用闭合 `1h` landmarks 检验更早的 intraday hazard；仍需另立冻结合同。

复现：

```bash
.venv/bin/python research/asset-portfolios/1d-btceth-relative-cycle-rotation/scripts/audit_binance_1d_be_rcr_p4_holding_transition.py --run-date 2026-08-12
```
