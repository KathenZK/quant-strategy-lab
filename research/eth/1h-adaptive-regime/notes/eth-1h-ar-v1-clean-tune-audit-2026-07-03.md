# ETH-1H-Adaptive-Regime-V1 Clean 微调审计 - 2026-07-03

## 结论

得到一个在 prefit 同时满足“相对 V1 收益更高、回撤更小、胜率适中”且通过 K+2/8 bps 选择门槛的 clean tuned observation；但最近三个月 reused holdout 收益仍为负，原始 10x 目标也未达到。该 observation 后续按用户要求登记为 `ETH-1H-Adaptive-Regime-V2`，状态仍为 `registered tuned observation / NO-GO / not live-ready`。

## 选择来源

- 参数来自 29 个 active clean 参数的 prefit-only 搜索；OOS 不参与选择。
- 冻结规则要求 prefit 年化高于 V1、DD 更小、胜率位于 55%-85%，并通过 K+2 与 8 bps 稳健排序。
- 最近三个月已在 V1 阶段解锁，本报告只作 reused holdout 失败审计。

## V1 对比

| Window | V1 annual / DD / win / trades | Clean tune annual / DD / win / trades |
| --- | --- | --- |
| `train` | `2.8190x` / `-16.29%` / `72.46%` / `69` | `3.8425x` / `-15.02%` / `72.60%` / `73` |
| `validation` | `2.7959x` / `-11.43%` / `69.70%` / `33` | `2.7855x` / `-10.56%` / `75.00%` / `32` |
| `prefit` | `2.8109x` / `-16.29%` / `71.57%` / `102` | `3.4333x` / `-15.02%` / `73.33%` / `105` |
| `reused_holdout` | `0.5196x` / `-20.87%` / `14.29%` / `7` | `0.4323x` / `-18.93%` / `50.00%` / `10` |
| `current_full` | `2.2462x` / `-20.87%` / `67.89%` / `109` | `2.6071x` / `-18.93%` / `71.30%` / `115` |

## 延迟与成本

| Scenario | Prefit annual / DD / win / trades | Reused holdout annual / DD / win / trades | Current full annual / DD / win / trades |
| --- | --- | --- | --- |
| `base_k1` | `3.4333x` / `-15.02%` / `73.33%` / `105` | `0.4323x` / `-18.93%` / `50.00%` / `10` | `2.6071x` / `-18.93%` / `71.30%` / `115` |
| `delay_k2` | `2.5862x` / `-19.55%` / `67.96%` / `103` | `0.8715x` / `-11.93%` / `45.45%` / `11` | `2.2383x` / `-19.55%` / `65.79%` / `114` |
| `delay_k3` | `2.3904x` / `-25.10%` / `63.11%` / `103` | `0.4299x` / `-23.13%` / `36.36%` / `11` | `1.9032x` / `-25.10%` / `60.53%` / `114` |
| `slip_8bps` | `3.0156x` / `-15.57%` / `71.70%` / `106` | `0.4180x` / `-19.61%` / `50.00%` / `10` | `2.3194x` / `-19.61%` / `69.83%` / `116` |
| `slip_12bps` | `2.8690x` / `-15.90%` / `71.70%` / `106` | `0.4042x` / `-20.20%` / `50.00%` / `10` | `2.2113x` / `-20.20%` / `69.83%` / `116` |
| `fee12_slip8` | `2.8911x` / `-15.85%` / `71.70%` / `106` | `0.4059x` / `-20.20%` / `50.00%` / `10` | `2.2274x` / `-20.20%` / `69.83%` / `116` |
| `double_cost` | `2.4416x` / `-17.37%` / `69.81%` / `106` | `0.3607x` / `-22.51%` / `50.00%` / `10` | `1.8938x` / `-22.51%` / `68.10%` / `116` |

## 参数邻域与序列稳健性

- one-at-a-time / exposure 邻域：`66`。
- 仍满足相对 V1 严格改善且 K+2 prefit 全窗口 gate：`42`。
- reused holdout 为正、DD<20%、win>=50%：`0`；该数字只作复用审计，不用于选参。
- 月度块：`23`；负收益块：`4`。
- bootstrap 10,000 次 annual 5/50/95：`[1.7227525030669304, 2.624306958965028, 3.901139916342917]`；DD 5/50/95：`[-0.3396595717336821, -0.2150377289934416, -0.1475649635740507]`。

## 实盘边界

- 成交状态机可表达：闭合 K、下一根 open、立即保护、stop-first、gap-open、单仓。
- 合约 tick `0.01`、market step `0.001`、min notional `20` USDT。
- 当前没有 production runner、重启恢复、交易所订单/仓位对账、missing-bar fail-closed、kill switch 和真实 stop-market 滑点证据。
- 最近三个月 reused holdout 收益为负；即使补齐 runner 也不能绕过该失败。
- 下一步证据必须来自冻结参数后的新增 forward trades；不得再把 2026-04-03 至 2026-07-03 当作新鲜 OOS。

## 机器证据

- `artifacts/eth_1h_ar_v1_clean_tune_audit_2026-07-03.json`
- `artifacts/eth_1h_ar_v1_clean_tune_neighborhood_2026-07-03.csv`
- `artifacts/eth_1h_ar_v1_clean_tune_monthly_2026-07-03.csv`
- `artifacts/eth_1h_ar_v1_clean_tune_trades_2026-07-03.csv`

复现：

```bash
uv run python research/eth/1h-adaptive-regime/scripts/audit_eth_1h_ar_v1_clean_tune.py
```
