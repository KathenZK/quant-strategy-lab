# HYPE-15M-MMTF V1 多机制广搜 — 2026-07-22

## 结论

只使用 locked OOS 之前的数据评估 `48,000` 组配置（stage1 `30,000`，多目标邻域 stage2 `18,000`），硬目标联合通过项为 `0`。按照预先冻结的交易数、收益、胜率、回撤和 validation 联合距离，最接近目标且满足样本门槛的原始基线登记为 `HYPE-15M-MMTF-V1`：`registered / not promoted / not live-ready`。

## 搜索范围

- 机制：Donchian breakout、Keltner breakout、EMA pullback continuation、time-series momentum、range-expansion breakout。
- 方向：双向、long-only、short-only。
- 过滤：EMA regime、ADX14、RVOL96。
- 退出/风控：ATR hard stop、固定 ATR TP、trailing、breakeven、timeout、趋势失效退出、cooldown。
- 风险：`1.5x/2x/2.5x/3x`；所有候选使用 fee、slippage 和 funding 后净值。
- 搜索保留 `2,617` 条多目标前沿，不以单一 scalar 提前裁掉各机制。

## V1 冻结结果

| 区间 | 净值倍数 | 年化净值倍数 | MDD | 胜率 | 交易数 | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| prefit 全段 | `1.7286x` | `1.8427x` | `14.11%` | `92.00%` | `100` | `3.472` |
| 内部 validation 90d | `1.2556x` | `2.5186x` | `8.35%` | `100.00%` | `26` | `inf` |

V1 的 `100` 笔由 `92` 次 TP、`7` 次 timeout、`1` 次 stop 构成；long `48` 笔、short `52` 笔。高胜率来自 `0.75 ATR` 小 TP 对 `6 ATR` 宽 hard stop 的非对称结构，8 笔亏损平均 `-2.84%`、最差 `-8.08%`（均为账户净收益口径）。因此它是需要消融验证的原始基线，不是已证明的高质量 alpha。

## 机制前沿

在 prefit trades `>=100`、validation trades `>=20`、prefit MDD `<20%` 的约束下，各机制最高 prefit 年化净值倍数分别约为：Donchian `0.87x`、Keltner `1.84x`、EMA continuation `1.17x`、time-series momentum `1.48x`、range expansion `1.31x`。当前主要缺口是年化收益而不是胜率或回撤。

## 证据

- 冻结配置与搜索计数：[hype_15m_mmtf_v1_search_2026-07-22.json](../artifacts/hype_15m_mmtf_v1_search_2026-07-22.json)
- 多目标前沿：[hype_15m_mmtf_v1_search_2026-07-22_frontier.csv](../artifacts/hype_15m_mmtf_v1_search_2026-07-22_frontier.csv)
- prefit trades：[hype_15m_mmtf_v1_search_2026-07-22_prefit_trades.csv](../artifacts/hype_15m_mmtf_v1_search_2026-07-22_prefit_trades.csv)
- 复现脚本：[research_hype_15m_mmtf_v1_search.py](../scripts/research_hype_15m_mmtf_v1_search.py)

