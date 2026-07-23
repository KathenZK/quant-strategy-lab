# HYPE-15M-MMTF-V1 全接线消融 — 2026-07-22

## 结论

V1 的主入场、EMA regime、ADX、RVOL、TP、timeout、方向与杠杆均真实改变成交路径；trailing、breakeven、cooldown、`entry_window`、`breakout_atr`、`exit_window` 与 baseline 的逐笔 signature 完全相同，应从 clean surface 删除。hard stop 诊断性移除略增收益，但它是必要尾部保护，不能据此从可执行策略删除。

## 关键结果

| 变体 | 路径变化 | prefit annual | MDD | WR | trades | 解释 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| baseline | - | `1.843x` | `14.11%` | `92.00%` | `100` | V1 |
| remove EMA regime | 是 | `1.035x` | `36.62%` | `85.71%` | `161` | 必要方向过滤 |
| remove ADX | 是 | `0.326x` | `68.50%` | `81.76%` | `318` | 必要趋势强度过滤 |
| remove RVOL | 是 | `0.830x` | `24.38%` | `87.16%` | `148` | 必要量能过滤 |
| remove TP | 是 | `0.804x` | `33.51%` | `35.05%` | `97` | 当前机制无法自然持有趋势 |
| remove timeout | 是 | `1.328x` | `31.00%` | `94.95%` | `99` | timeout 是回撤约束 |
| enable trend exit | 是 | `1.875x` | `12.78%` | `92.00%` | `100` | prefit 小幅改善；validation 路径不变，可进入 tune 邻域 |
| leverage 2.5x | 是 | `2.136x` | `17.56%` | `92.00%` | `100` | 收益与回撤同步放大 |

trailing 与 breakeven 不生效的机制原因明确：V1 的 TP 为 `0.75 ATR`，早于两者 `1.0 ATR` 激活。cooldown 已是 `0`；Keltner entry 不读取 `entry_window/breakout_atr`；`trend_exit=false` 时不读取 `exit_window`。

## Clean 决定

V2 固定 mechanism=`keltner_breakout`、direction=`both`，移除上述 dormant 槽位；保留 EMA、ATR、ADX、RVOL、Keltner distance、hard stop、TP、timeout、leverage，并把 `trend_exit_window: null|N` 表示为一个不产生关闭状态冗余的可选结构。

## 证据

- [消融 CSV](../artifacts/hype_15m_mmtf_v1_ablation_2026-07-22.csv)
- [消融 JSON](../artifacts/hype_15m_mmtf_v1_ablation_2026-07-22.json)
- [复现脚本](../scripts/research_hype_15m_mmtf_v1_ablation.py)

