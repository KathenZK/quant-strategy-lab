# BIN-1D-BE-CPPR P0 Partial-Profit Runner 裁决

## 结论

COST control与每个fraction的neutral shadow-router terminal/MDD均在`1e-12`内对账。三个partial fractions全部完成，`0` hard-base pass，P0 `HARD-GATE-FAILED`并关闭research line；audit/prospective未读取。

| Fraction | Base | Ordered MDD | Stress | Delay | Partial events |
| ---: | ---: | ---: | ---: | ---: | ---: |
| `25%` | `16.4626x` | `-31.87%` | `16.1239x/-31.87%` | `6.4944x/-34.80%` | 22 |
| `50%` | `10.4789x` | `-30.00%` | `10.2641x/-30.00%` | `5.3271x/-33.27%` | 22 |
| `75%` | `6.6693x` | `-29.25%` | `6.5325x/-29.34%` | `4.9979x/-31.92%` | 22 |

Growth frontier为25%，risk frontier为75%。减仓越多，MDD单调改善但收益快速下降；即使75%仍比20%硬门差`9.25pp`。25%臂距离20x还差`3.54x`且MDD仍超标`11.87pp`。

## 结构归因

- partial机制按预期工作：三臂均有22次next-open bank，runner quantity、fee、funding与final exit已进入同一小时台账。
- 风险改善不是伪造：从COST control `-35.22%`改善到`-29.25%`；但锁定现金的代价直接减少大趋势复利。
- `0–25%`之间即便插值，也不可能把`35.22%` MDD降到`20%`；`>75%`趋向已失败的full early exit，不能通过增加fraction网格救参。
- 结论支持“早止盈后需要因果continuation handoff”，而不是继续寻找减仓比例。

## 治理裁决

- `research line closed / HARD-GATE-FAILED / explore / not promoted / not live-ready`；
- 不增加fraction、不改activation/giveback/confirm、不做第二次partial或trailing resize；
- audit/prospective未读取，无版本、无handoff；
- 后继若继续，必须另立profit-exit handoff continuity family，用full early exit + 单次fresh continuation re-entry，不能静默写回CPPR。

## 证据

- [冻结合同](../specs/binance-1d-be-cppr-p0-contract-2026-08-12.md)
- [机器摘要](../artifacts/binance_1d_be_cppr_p0_2026-08-12.json) — SHA256 `bee07dde4310160bdea2db454f36cc956add8ebed7ea6f95aa24f6954edf0875`
- [四路metrics](../artifacts/binance_1d_be_cppr_p0_2026-08-12_metrics.csv) — SHA256 `357308d45cb4ea560f69391913989c0a954f7baf0baecde4ff5c5ee142396015`
- [Growth完整路径](../artifacts/binance_1d_be_cppr_p0_growth_frontier_trade_path_2026-08-12.html) — 30条routed legs与22个partial markers
- [Risk完整路径](../artifacts/binance_1d_be_cppr_p0_risk_frontier_trade_path_2026-08-12.html)
- [研究脚本](../scripts/research_binance_1d_be_cppr_p0.py) · [HTML脚本](../scripts/render_binance_1d_be_cppr_p0_trade_paths.py) · [测试](../../../../tests/test_binance_1d_be_cppr_p0.py)
