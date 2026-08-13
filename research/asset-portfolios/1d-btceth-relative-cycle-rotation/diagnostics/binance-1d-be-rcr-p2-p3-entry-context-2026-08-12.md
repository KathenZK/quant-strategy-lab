# BIN-1D-BE-RCR P2/P3 Entry-Context 结论（2026-08-12）

## P2 attribution

六个预注册 risk scores 中，`RELATIVE_EXTREME20` 为唯一 PASS：

| 维度 | AUC / edge |
|---|---:|
| growth anchor AUC | `0.6203` |
| risk anchor AUC | `0.6732` |
| BTC pooled AUC | `0.6049` |
| ETH pooled AUC | `0.5997` |
| 四 strata 最弱 tail-rate edge | `12.5pp` |

其余 `FAST_OPPOSE5/10`、`MARKET_OPPOSE5`、`VOL_SHOCK7_28`、`CROSS_DISAGREE5` 均未跨 anchor 与资产通过。P2 只证明相对动量极端状态与尾部交易有关，不构成可交易门禁。

## P3 economic conversion

P3 在 exact growth/risk controls 上预注册 `threshold∈{1.0,1.5,2.0,2.5,3.0}` 的共享 entry gate，共 `10/10` 配置：

- base `>=20x && ordered MDD<=20%`：`0`；
- 最高收益：growth `threshold=1.5`，`21.3284x / -69.6600%`；
- 最低 MDD：risk `threshold=2.0`，`8.6109x / -30.7607%`，与 control 路径相同；
- audit/prospective 未读取，版本未登记。

P2 的分类信息没有改善决定最大回撤的持仓内路径；P3 为 `HARD-GATE-FAILED / explore / not promoted / not live-ready`。不得扩大 threshold 或叠加 P1 stop 救援。下一研究问题应转向持仓期间、可实时观测且早于尾部发生的 state transition，而不是入场 gate。

## 复现

```bash
.venv/bin/python research/asset-portfolios/1d-btceth-relative-cycle-rotation/scripts/audit_binance_1d_be_rcr_p2_entry_context.py --run-date 2026-08-12
.venv/bin/python research/asset-portfolios/1d-btceth-relative-cycle-rotation/scripts/search_binance_1d_be_rcr_p3_relative_extreme_gate.py --run-date 2026-08-12
```
