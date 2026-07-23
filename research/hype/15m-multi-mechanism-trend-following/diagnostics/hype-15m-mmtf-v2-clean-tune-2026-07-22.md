# HYPE-15M-MMTF V2 Clean Tune — 2026-07-22

## 结论

V2 与 V1 逐笔完全等价后，只对消融保留参数运行风险轮 `24,000` 组、联合轮 `36,000` 组，并对最接近目标的 `240` 组做 30d rolling audit。prefit、validation 与 joint 硬目标通过项均为 `0`。最终冻结 V3，locked OOS 在此阶段仍未访问。

## V3 相对 V2

EMA/ATR/ADX/RVOL/Keltner、TP、timeout 与关闭的 trend-exit 均保持不变；hard stop `6 -> 8 ATR`，leverage `2x -> 3x`。这两项提高了 prefit 收益并把回撤推近但未超过 20% 门槛。

| 区间 | annual factor | CAGR | MDD | WR | trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| V3 prefit | `2.573x` | `157.33%` | `18.07%` | `92.00%` | `100` | `3.835` |
| V3 validation 90d | `3.979x` | `297.87%` | `12.52%` | `100.00%` | `26` | `inf` |

14 个 rolling 30d 窗口中 `13/14` 正收益、零交易窗口 `0`、中位交易数 `9`、中位收益 `10.03%`、最差收益 `-2.06%`。这些窗口参与最终形状筛选，属于 prefit 稳定性诊断，不伪称 prospective OOS；真正未复用 OOS 是随后一次性揭示的最后三个月。

## 证据

- [机器摘要](../artifacts/hype_15m_mmtf_v2_clean_tune_2026-07-22.json)
- [调优前沿](../artifacts/hype_15m_mmtf_v2_clean_tune_frontier_2026-07-22.csv)
- [rolling audit](../artifacts/hype_15m_mmtf_v2_clean_tune_rolling_2026-07-22.csv)
- [复现脚本](../scripts/research_hype_15m_mmtf_v2_clean_tune.py)

