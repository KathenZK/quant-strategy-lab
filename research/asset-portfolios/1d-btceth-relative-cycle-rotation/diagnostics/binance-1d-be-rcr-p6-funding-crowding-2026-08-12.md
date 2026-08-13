# BIN-1D-BE-RCR P6 Funding/Crowding 结论（2026-08-12）

## 裁决

- P6：`0/6 PASS`
- family：`research line closed / HARD-GATE-FAILED / explore / not promoted / not live-ready`
- audit/prospective：从未读取；版本：从未登记

P6 复用 SHA256 锁定的 `5,778` 个 P5 landmarks、`332` 个 danger labels与 growth/risk `39/20` 个 danger episodes。

| feature | growth AUC | risk AUC | BTC AUC | ETH AUC | weakest edge |
|---|---:|---:|---:|---:|---:|
| POSITION_CROWD24 | 0.692 | 0.647 | 0.754 | 0.664 | +4.56pp |
| POSITION_CROWD7Z | 0.564 | 0.583 | 0.599 | 0.567 | +2.01pp |
| MARKET_CROWD7Z | 0.549 | 0.585 | 0.577 | 0.558 | +0.94pp |
| RELATIVE_CROWD_ROLE7Z | 0.522 | 0.502 | 0.542 | 0.512 | -4.04pp |
| FUNDING_ACCEL24 | 0.551 | 0.550 | 0.552 | 0.553 | +0.13pp |
| CROSS_CROWD_ABS7Z | 0.529 | 0.553 | 0.520 | 0.542 | -0.54pp |

`POSITION_CROWD24` 具有跨 anchor/asset 排序信息，但四 strata 的最弱经济分层仅 `4.56pp < 8pp`，未过预注册门槛。它不能被描述为共享 exit signal，也不能在已揭示 development 上继续追 threshold。

## Family 关闭理由

本家族已依次完成：P0 `7,560` 配置、P1 `184` 保护 overlays、P2/P3 entry attribution/conversion、P4 日频 transition、P5 小时 price hazard、P6 funding omitted-state。收益端只有 growth control 超过 `20x`，但 ordered MDD 始终至少 `-69.66%`；risk control 最好仍为 `8.61x/-30.76%`。所有受约束风险修复均未达到 `20x/20%`。

因此关闭 `BIN-1D-BE-RCR` 当前研究线，不揭示 audit，不建立 prospective runner，不登记版本。后续探索必须是机制上独立的新 family，并重新冻结合同；不得将 P6 边缘 funding 排序包装成 RCR V1。

复现：

```bash
.venv/bin/python research/asset-portfolios/1d-btceth-relative-cycle-rotation/scripts/audit_binance_1d_be_rcr_p6_funding_crowding.py --run-date 2026-08-12
```
