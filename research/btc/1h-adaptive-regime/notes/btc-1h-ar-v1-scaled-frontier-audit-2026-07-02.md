# BTC-1H-Adaptive-Regime-V1 缩放前沿审计 - 2026-07-02

## 结论

得到一个同时满足“相对 V1 收益更高、回撤更小、胜率适中”且 K+2 prefit 回撤低于 20% 的缩放前沿观察。它通过 reused holdout 与成本压力，但由于 reused holdout 已解锁、没有新增 forward trades 和生产 runner，状态仍为 `audit observation / not live-ready`。

2026-07-03 按用户要求，该观察已在 `btc-1h-ar-core-ledger.md` 登记为 `BTC-1H-Adaptive-Regime-V2`。此次登记只固定版本身份和参数，不改变 `not live-ready` 结论。

## 选择来源

- 来源参数是在第一次 prefit-only 稳健排序中冻结的 soft frontier；OOS 不参与选择。
- 原曝光 Keltner `2.0x`、CCI `3.0x`；其 K+2 prefit DD 为 `-21.77%`。
- 统一乘以 `0.90`，得到 Keltner `1.8x`、CCI `2.7x`；缩放规则只读取 prefit K+2 DD。

## V1 对比

| Window | V1 annual / DD / win / trades | Scaled frontier annual / DD / win / trades |
| --- | --- | --- |
| `train` | `2.5774x` / `-15.13%` / `68.00%` / `50` | `3.6068x` / `-13.99%` / `86.49%` / `37` |
| `validation` | `3.3339x` / `-18.68%` / `68.75%` / `32` | `2.5108x` / `-10.29%` / `82.76%` / `29` |
| `prefit` | `2.8204x` / `-18.68%` / `68.29%` / `82` | `3.1773x` / `-13.99%` / `84.85%` / `66` |
| `reused_holdout` | `0.1695x` / `-42.73%` / `38.46%` / `13` | `1.5232x` / `-13.48%` / `81.82%` / `11` |
| `current_full` | `1.9412x` / `-42.73%` / `64.21%` / `95` | `2.8817x` / `-13.99%` / `84.42%` / `77` |

## 延迟与成本

| Scenario | Prefit annual / DD / win / trades | Reused holdout annual / DD / win / trades | Current full annual / DD / win / trades |
| --- | --- | --- | --- |
| `base_k1` | `3.1773x` / `-13.99%` / `84.85%` / `66` | `1.5232x` / `-13.48%` / `81.82%` / `11` | `2.8817x` / `-13.99%` / `84.42%` / `77` |
| `delay_k2` | `2.4993x` / `-19.70%` / `80.30%` / `66` | `1.6648x` / `-14.10%` / `84.62%` / `13` | `2.3680x` / `-19.70%` / `81.01%` / `79` |
| `delay_k3` | `1.6338x` / `-25.44%` / `74.63%` / `67` | `2.1302x` / `-13.16%` / `91.67%` / `12` | `1.6924x` / `-25.44%` / `77.22%` / `79` |
| `slip_8bps` | `3.0702x` / `-14.28%` / `84.85%` / `66` | `1.4719x` / `-13.58%` / `81.82%` / `11` | `2.7845x` / `-14.28%` / `84.42%` / `77` |
| `slip_12bps` | `2.8598x` / `-14.60%` / `83.33%` / `66` | `1.4220x` / `-13.68%` / `81.82%` / `11` | `2.6063x` / `-14.60%` / `83.12%` / `77` |
| `fee12_slip8` | `2.9673x` / `-14.60%` / `84.85%` / `66` | `1.4222x` / `-13.69%` / `81.82%` / `11` | `2.6911x` / `-14.60%` / `84.42%` / `77` |
| `double_cost` | `2.5884x` / `-16.17%` / `83.33%` / `66` | `1.2394x` / `-14.12%` / `81.82%` / `11` | `2.3472x` / `-16.17%` / `83.12%` / `77` |

## 参数邻域与序列稳健性

- one-at-a-time / exposure 邻域：`55`。
- 仍满足相对 V1 严格改善且 K+2 prefit 全窗口 gate：`24`。
- reused holdout 为正、DD<20%、win>=50%：`53`；该数字只作复用审计，不用于选参。
- 月度块：`23`；负收益块：`3`。
- bootstrap 10,000 次 annual 5/50/95：`[1.9095699811215405, 2.787432492717694, 4.086778975950987]`；DD 5/50/95：`[-0.25102192904807774, -0.1687803453060019, -0.12061077399649542]`。

## 实盘边界

- 成交状态机可表达：闭合 K、下一根 open、立即保护、stop-first、gap-open、单仓。
- 合约 tick `0.10`、market step `0.001`、min notional `50` USDT。
- 当前没有 production runner、重启恢复、交易所订单/仓位对账、missing-bar fail-closed、kill switch 和真实 stop-market 滑点证据。
- 下一步证据必须来自冻结参数后的新增 forward trades；不得再把 2026-04-02 至 2026-07-02 当作新鲜 OOS。

## 机器证据

- `artifacts/btc_1h_ar_v1_scaled_frontier_audit_2026-07-02.json`
- `artifacts/btc_1h_ar_v1_scaled_frontier_neighborhood_2026-07-02.csv`
- `artifacts/btc_1h_ar_v1_scaled_frontier_monthly_2026-07-02.csv`
- `artifacts/btc_1h_ar_v1_scaled_frontier_trades_2026-07-02.csv`

复现：

```bash
uv run research/btc/1h-adaptive-regime/scripts/audit_btc_1h_ar_v1_scaled_frontier.py
```
