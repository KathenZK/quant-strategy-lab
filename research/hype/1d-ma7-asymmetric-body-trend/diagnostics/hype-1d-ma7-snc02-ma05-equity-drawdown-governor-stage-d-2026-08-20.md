# HYPE-1D-MA7-SNC02 MA05 权益回撤节流 Stage D 诊断

> 日期：2026-08-20。状态：`diagnostic-only / stopped after trend-first reprioritization / not promoted / not live-ready`。

## 结论

四个权益回撤节流臂均未通过预冻结组合门。0.25x两臂将真实1h MDD压到 `-18.61%/-18.93%`，但低风险状态占比超过92%，总收益仅 `+10.48%/+11.38%`，额外1日lag均为负，最新08-09 long只得到约 `+6.53%`。0.5x两臂收益为 `+72.36%/+44.55%`，但MDD仍为 `-22.40%/-23.70%`，且最新趋势约减半。

| Arm | 收益 | 1h MDD | 低风险状态 | 最新long | 裁决 |
|---|---:|---:|---:|---:|---|
| `DG08_L50_R04` | +72.36% | -22.40% | 87.67% | +13.05% | MDD/lag/趋势失败 |
| `DG10_L50_R05` | +44.55% | -23.70% | 89.46% | +13.05% | MDD/lag/收益失败 |
| `DG08_L25_R04` | +10.48% | -18.61% | 92.83% | +6.53% | 收益/lag/趋势失败 |
| `DG10_L25_R05` | +11.38% | -18.93% | 92.38% | +6.53% | 收益/lag/趋势失败 |

节流状态依赖旧权益高水位，回撤后长期无法恢复1x，因此本质上接近持续低仓位，不是“亏损时少承担、趋势恢复后吃满”的机制。用户随后明确将完整趋势捕获设为第一目标，本风险路线到此停止；原计划Stage E在任何结果产生前取消。

## 证据

- [冻结合同](../specs/hype-1d-ma7-snc02-ma05-equity-drawdown-governor-stage-d-contract-2026-08-20.md)
- [机器证据](../artifacts/hype_1d_ma7_snc02_ma05_equity_drawdown_governor_stage_d_2026-08-20.json)及其[SHA256](../artifacts/hype_1d_ma7_snc02_ma05_equity_drawdown_governor_stage_d_2026-08-20.json.sha256)
- [可执行脚本](../scripts/research_hype_1d_ma7_snc02_ma05_equity_drawdown_governor_stage_d.py)
