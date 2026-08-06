# BIN-15M-TSM 锁定 OOS 一次性揭示（2026-07-28）

> 状态：`archived / HARD-GATE-FAILED`
>
> 裁决：五项硬门槛四过一败——段级 PF `1.162 < 1.2`，按[契约](../specs/bin-15m-tsm-research-contract-2026-07-28.md)第 9 节判 **HARD-GATE-FAILED**，家族归档。不得用已揭示窗口调参重试；本窗口（`2026-01-01`–`2026-06-30`，三次 reused holdout after 本次）对任何后继线永久失效。

## 1. 口径

- OOS 窗口 `2026-01-01`–`2026-06-30 UTC`；状态机跑全历史以携带真实入窗状态，只对 OOS 计分；组合与段级核算口径同 [P2](bin-15m-tsm-p2-portfolio-baseline-2026-07-28.md)/[P1](bin-15m-tsm-p1-segment-baseline-2026-07-28.md)（含 funding，费用 `0.001`+`4 bps`/次）。
- PF 口径在揭示前冻结于[脚本](../scripts/reveal_locked_oos_once.py)文档：OOS 内闭合段（含入窗前开仓、含档尾强平 6 段）名义净收益的盈亏比；日度收益 PF 仅报告。
- 揭示已落防重跑标记（`artifacts/LOCKED_OOS_REVEALED.json`）。

## 2. 硬门槛裁决

| 门槛 | 冻结要求 | 实测 | 判定 |
|---|---|---:|---|
| 闭合段数 | ≥ 200 | 1,779 | 通过 |
| 组合净收益 | > 0 | `+6.97%` | 通过 |
| 段级 PF | ≥ 1.2 | **1.162** | **失败** |
| 组合 MaxDD | ≤ 20% | `−12.1%` | 通过 |
| 1.5x 成本净收益 | > 0 | `+4.60%` | 通过 |

**结论：HARD-GATE-FAILED，家族归档。**

## 3. 揭示窗口全貌（事后记录，不构成任何重试依据）

- 组合月度净：1 月 `+5.3%`、2 月 `+2.0%`、3 月 `−2.9%`、4 月 `−1.0%`、5 月 `−0.0%`、6 月 `+3.7%`；OOS Sharpe（日度年化）`0.77`，高于开发窗 `0.67`；日度收益 PF `1.136`。
- 段级：1,779 段、净期望 `+1.26 ATR`、胜率 38.3%；**多空换位**：多头 `−1.83 ATR`、空头 `+4.11 ATR`——与开发窗多头主导（`+4.20` vs `+0.87`）完全相反，与 1d emax 家族"近期空头侧更强"的独立观察一致。
- pool_exit 占 26%（466/1,779），显著高于开发窗的 12.6%：2026H1 池边界摩擦上升。

## 4. 诚实解读

1. 失败是按预注册字面判的：组合层四项全过、OOS Sharpe 不低于开发窗，机制方向上并未崩溃；但段级盈亏质量（PF 1.16）低于事前认定"值得继续投入"的线。二次 reused holdout 本就证据降级，边缘结果按失败处理正是该设计的目的。
2. 多空换位说明开发窗测得的"多头主导"并非稳定结构，而是 2020–2024 牛市偏置的一部分；任何后继研究不得再把多头侧期望当作先验。
3. 本失败**不**推翻 P1 的尺度结论（4h 等效核 ≫ 1d/4d 核、平面平坦），该测量仍然有效并已归档在 [P1 诊断](bin-15m-tsm-p1-segment-baseline-2026-07-28.md)。

## 5. 后继约束

- 本家族按契约归档；任何延续（如前瞻观察窗、机制变体）都是**新契约新家族线**，只能用 `2026-07` 之后的前瞻数据作检验，绝不允许触碰本已揭示窗口。

## 6. 证据

- 揭示脚本（一次性）：[reveal_locked_oos_once.py](../scripts/reveal_locked_oos_once.py)
- 揭示报告：[bin_15m_tsm_locked_oos_reveal_2026-07-28.json](../artifacts/bin_15m_tsm_locked_oos_reveal_2026-07-28.json) · [OOS 段级 parquet](../artifacts/bin_15m_tsm_locked_oos_segments_2026-07-28.parquet) · [OOS 净值 parquet](../artifacts/bin_15m_tsm_locked_oos_equity_2026-07-28.parquet)
- 上游：[P2 诊断](bin-15m-tsm-p2-portfolio-baseline-2026-07-28.md) · [P1 诊断](bin-15m-tsm-p1-segment-baseline-2026-07-28.md) · [契约](../specs/bin-15m-tsm-research-contract-2026-07-28.md)
