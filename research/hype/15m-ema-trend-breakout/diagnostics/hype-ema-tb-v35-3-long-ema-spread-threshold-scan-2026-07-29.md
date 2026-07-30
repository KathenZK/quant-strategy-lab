# HYPE-EMA-TB-V35.3 多头 ema_spread 弱多过滤扫描

日期：2026-07-29  
状态：diagnostic only；V35.3 保持 `registered / not promoted / not live-ready`；不修改 runner

## 问题

满仓复盘里两笔弱多（薄 `ema_spread`、低 MFE）贡献了大部分“没走出来”的亏损：

| 实盘/研究多单 | signal | ema_spread | vol | MFE | 结局 |
| --- | --- | ---: | ---: | ---: | --- |
| 7/15 13:00 entry | 12:30 | 0.00648 | 0.65 | 0.30 | indicator_exit ≈ `-3.8%` |
| 7/21 05:45 entry | 05:15 | 0.00584 | 1.53 | 1.27 | SL ≈ `-10.4%` |

候选规则：多头额外要求 `ema_spread >= threshold`（基线仍是 `> 0`）。空头与 V35.3 分批/非对称止损不变。

## 数据与成本

- Binance HYPEUSDT 永续 `15m`：`2025-05-30 10:30` ~ `2026-07-29 02:45`，`40,770` 根闭合 K，质量门通过
- 成本 `0.00085`/fill，含 funding
- full 窗为样本内敏感性；`1d/7d/1m/3m/6m/1y` 仅审计

## Full 结果

| threshold | 收益 | MaxDD | Sharpe | 笔数 | 多单 | 挡住基线多信号 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `0.000`（V35.3） | **+9434.54%** | **-22.88%** | **4.69** | 116 | 87 | 0 |
| `0.005` | +6665.85% | -26.24% | 4.41 | 114 | 85 | 11 |
| `0.008` | +6726.73% | -22.88% | 4.45 | 114 | 85 | 30 |
| `0.010` | +5887.96% | -23.36% | 4.37 | 110 | 81 | 55 |
| `0.012` | +6012.77% | -29.34% | 4.41 | 108 | 79 | 75 |
| `0.015` | +6033.39% | -26.07% | 4.43 | 103 | 74 | 99 |
| `0.020` | +3348.10% | -29.32% | 3.97 | 99 | 70 | 138 |

对两笔弱多的命中：

| threshold | 挡住 7/15 | 挡住 7/21 |
| ---: | --- | --- |
| `0.005` | 否（0.00648 ≥ 0.005） | 否（0.00584 ≥ 0.005） |
| `≥ 0.008` | 是 | 是 |

注意：`vol<1` **挡不住** 7/21（vol≈1.53）；只有抬 `ema_spread` 才能同时砍掉这两笔。

## 近期分片（审计）

| 窗口 | thr=0 | thr=0.008 | thr=0.010 |
| --- | ---: | ---: | ---: |
| `7d` | -1.23% / -12.06% | -1.23% / -12.06% | -1.23% / -12.06% |
| `1m` | +8.28% / -17.81% | +9.87% / -18.03% | +13.94% / -14.60% |
| `3m` | +151.23% / -21.49% | +134.47% / -21.49% | +123.96% / -23.36% |
| `6m` | +650.64% / -21.49% | +427.27% / -21.49% | +402.78% / -23.36% |
| `1y` | +8707.74% / -21.49% | +6206.34% / -21.49% | +5431.51% / -23.36% |

`0.010` 在最近 `1m` 看起来更好，但 `3m/6m/1y/full` 全面让渡，且 MaxDD 在中长期不改善；不能单凭近期窗把 spread 门槛写进冻结版。

## 判断

1. **能挡住两笔已知弱多的最低整数档是 `0.008`**，不是口头常用的 `0.005`；`0.005` 对这两笔无效。
2. 即便 `0.008` 保住 full MaxDD `-22.88%`，full 收益仍从 `+9435%` 掉到 `+6727%`（约少 `2708pp`），并挡住 30 个基线多信号——其中多数不是 7 月弱多。
3. `0.010` 更狠：收益再降到 `+5888%`，MaxDD 略恶化到 `-23.36%`，**不是免费午餐**。
4. 因此：**不把弱多 `ema_spread` 门槛热改进 V35.3**；若继续研究，应与多头对称分批一起做新版本，而不是单独抬 spread 门槛。
5. 实盘临时风控仍优先：`max_allocation` 降到 `2.0` + 保持空头分批 + 少 manual。

## 证据

- 复现脚本：[research_hype_ema_tb_v35_3_long_ema_spread_threshold_scan.py](../scripts/research_hype_ema_tb_v35_3_long_ema_spread_threshold_scan.py)
- 汇总 JSON：[hype_ema_tb_v35_3_long_ema_spread_threshold_scan_2026-07-29.json](../artifacts/hype_ema_tb_v35_3_long_ema_spread_threshold_scan_2026-07-29.json)
- 逐笔 trades：[hype_ema_tb_v35_3_long_ema_spread_threshold_scan_2026-07-29_trades.csv](../artifacts/hype_ema_tb_v35_3_long_ema_spread_threshold_scan_2026-07-29_trades.csv)
- 权益：[hype_ema_tb_v35_3_long_ema_spread_threshold_scan_2026-07-29_equity.csv](../artifacts/hype_ema_tb_v35_3_long_ema_spread_threshold_scan_2026-07-29_equity.csv)
- 被挡多信号清单：[hype_ema_tb_v35_3_long_ema_spread_threshold_scan_2026-07-29_filtered_longs.csv](../artifacts/hype_ema_tb_v35_3_long_ema_spread_threshold_scan_2026-07-29_filtered_longs.csv)
- 姊妹回放：[hype-ema-tb-v35-3-giveaway-partial-replay-2026-07-29.md](hype-ema-tb-v35-3-giveaway-partial-replay-2026-07-29.md)
