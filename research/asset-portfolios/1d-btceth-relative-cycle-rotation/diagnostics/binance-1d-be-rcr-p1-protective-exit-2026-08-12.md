# BIN-1D-BE-RCR P1 Protective-Exit 结论（2026-08-12）

## 裁决

- P1：`HARD-GATE-FAILED / explore / not promoted / not live-ready`
- `184/184` 个冻结 overlay 完成；base `>=20x && ordered MDD<=20%` 为 `0`
- audit/prospective：均未读取
- 登记版本：无

两个无保护 exact controls 以 `1e-12` 容差完成 parity：growth `21.2605x/-69.6600%`，risk `8.6109x/-30.7607%`。

## Overlay 前沿

| 结果 | anchor | 保护 | equity | ordered MDD |
|---|---|---|---:|---:|
| 最高收益 | growth | `stop=4ATR, EMA=0, cooldown=7` | `14.1870x` | `-71.1539%` |
| 最低回撤 | risk | `stop=0, EMA5, state_change` | `1.5092x` | `-26.0732%` |

- growth anchor 的 `92` 个 overlay，最高收益 `14.1870x`、最低 MDD `-44.2924%`；
- risk anchor 的 `92` 个 overlay，最高收益 `8.6109x`、最低 MDD `-26.0732%`；
- 固定 stop 不能解决跨日 gap/方向误判，快速 EMA 虽小幅修复 MDD，却把长期趋势收益剪掉；
- base screen 为 0，因此按合同没有启动 stress/delay，也没有唯一候选。

## Side/asset exact ablation

| anchor | variant | equity | ordered MDD |
|---|---|---:|---:|
| growth | BTC only | `14.1373x` | `-34.83%` |
| growth | ETH only | `1.5039x` | `-69.66%` |
| growth | ETH long | `1.0213x` | `-69.66%` |
| growth | ETH short | `1.4725x` | `-52.84%` |
| risk | long only | `8.2405x` | `-30.76%` |
| risk | short only | `1.0449x` | `-41.47%` |

growth control 的收益主要来自 BTC sleeves，而最深尾部由 ETH sleeves 贡献；risk control 则几乎全部收益来自 long，short sleeve 不提供有效保护。简单删腿仍没有 `20x/20%` 组合，因此这些只作为下一信息归因的因果路由，不得登记为候选。

下一阶段应预注册 entry-context 信息测试，区分“BTC 可持续趋势”与“ETH 高 beta squeeze/反转”状态；不得继续扩大 stop/EMA/cooldown 参数。

## 复现

```bash
.venv/bin/python research/asset-portfolios/1d-btceth-relative-cycle-rotation/scripts/search_binance_1d_be_rcr_p1_protective_exit.py --run-date 2026-08-12
.venv/bin/python research/asset-portfolios/1d-btceth-relative-cycle-rotation/scripts/diagnose_binance_1d_be_rcr_side_attribution.py --run-date 2026-08-12
```
