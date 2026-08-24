# BIN-1D-BE-LRMR P0 Development 搜索结论（2026-08-12）

## 裁决

- P0：`HARD-GATE-FAILED / research line closed / explore / not promoted / not live-ready`
- `15,288/15,288` 个合法配置完成；`equity>=20x && daily MDD<=20%` 为 `0`
- audit/prospective：未读取；版本：未登记

双腿 control 对账 PASS：固定 control 的 fast/detailed daily equity 与 hourly terminal equity 绝对差 `<1e-12`，pair count 完全一致；ordered MDD 采用每小时两腿同时最不利极值。

| frontier | daily equity | daily MDD | conservative ordered MDD | pairs |
|---|---:|---:|---:|---:|
| growth | `1.5471x` | `-37.85%` | `-44.88%` | 19 |
| risk | `1.0325x` | `-3.12%` | `-19.66%` | 8 |

growth 参数为 `lookback=120, entry=2, exit=0, stop=0, max_hold=60, cooldown=7`；risk 参数为 `lookback=180, entry=3, exit=0, stop=0, max_hold=3, cooldown=7`。

## Arm attribution

| frontier | arm | equity | ordered MDD |
|---|---|---:|---:|
| growth | long BTC / short ETH | `1.0378x` | `-45.06%` |
| growth | short BTC / long ETH | `1.4908x` | `-24.17%` |
| risk | long BTC / short ETH | `1.0120x` | `-19.66%` |
| risk | short BTC / long ETH | `1.0203x` | `-7.48%` |

收益主要来自 short-BTC/long-ETH arm，但即使单独保留也只有 `1.49x/-24.17%`；另一方向近乎无 alpha。市场中性结构能压低部分方向风险，却没有接近 `20x` 的经济增长，且 conservative intrahour MDD 显著高于 close-only MDD。

差距不属于 threshold 或成本微调可修复范围，因此 P0 后直接关闭当前 family，不做消融/调参救援，不揭示 audit/prospective。

复现：

```bash
.venv/bin/python research/asset-portfolios/1d-btceth-log-ratio-mean-reversion/scripts/search_binance_1d_be_lrmr_p0.py --run-date 2026-08-12
.venv/bin/python research/asset-portfolios/1d-btceth-log-ratio-mean-reversion/scripts/diagnose_binance_1d_be_lrmr_p0_frontiers.py --run-date 2026-08-12
```

完整双腿交互路径：[growth frontier](../artifacts/binance_1d_be_lrmr_p0_growth_frontier_trade_path_2026-08-12.html)；[risk frontier](../artifacts/binance_1d_be_lrmr_p0_risk_frontier_trade_path_2026-08-12.html)。
