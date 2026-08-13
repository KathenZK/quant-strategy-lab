# BIN-1H-BE-CILL P0 Development 搜索结论（2026-08-12）

## 裁决

- P0：`HARD-GATE-FAILED / research line closed / explore / not promoted / not live-ready`
- `2,160/2,160` ordered `1h` 配置完成；base `>=20x/MDD<=20%` 为 `0`
- audit/prospective：未读取；版本：未登记

| frontier | net equity | ordered MDD | trades | zero-cost/funding equity |
|---|---:|---:|---:|---:|
| growth | `1.2920x` | `-21.78%` | 41 | `1.4943x` |
| risk | `1.1046x` | `-10.94%` | 13 | `1.1536x` |

growth 参数：`vol=168, impulse=3, gap=0.5, follower_cap=0.5, catchup=0.5, hold=48, stop=0, cooldown=6`。risk 只把 `impulse` 提至 4、hold 缩至 12。

## 成本与 arm attribution

- growth：net `1.2920x`，无 fee/slippage 但含 funding `1.4485x`，完全 price-only gross `1.4943x`；成本有影响，但毛 alpha 仍与 20x 相差数量级。
- growth long-only `1.1055x/-21.78%`，short-only `1.1254x/-10.94%`；BTC follower `1.0643x/-22.07%`，ETH follower `1.1915x/-10.94%`。
- risk 仅 13 笔且 long/short `12/1`，不满足跨方向容量门禁。

因此失败属于 lead–lag edge 太弱与容量不足，而非 cost-only blocker。当前 family 直接关闭，不扩 impulse/gap/hold，不揭示 audit/prospective。

复现：

```bash
.venv/bin/python research/asset-portfolios/1h-btceth-cross-impulse-lead-lag/scripts/search_binance_1h_be_cill_p0.py --run-date 2026-08-12
.venv/bin/python research/asset-portfolios/1h-btceth-cross-impulse-lead-lag/scripts/diagnose_binance_1h_be_cill_p0_frontiers.py --run-date 2026-08-12
```

完整交互路径：[growth frontier](../artifacts/binance_1h_be_cill_p0_growth_frontier_trade_path_2026-08-12.html)；[risk frontier](../artifacts/binance_1h_be_cill_p0_risk_frontier_trade_path_2026-08-12.html)。
