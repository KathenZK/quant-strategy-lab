# HYPE-1H-Adaptive-Regime-V4 执行压力归因与优化 - 2026-07-10

## 结论

优化前先发现 V4 现有 ensemble 回测不是精确单账户状态机：它先独立模拟两条腿，再合并交易；被另一条腿挡掉的虚拟交易仍会在单腿流中错误触发持仓/冷却，从而压掉后续真实可入场信号。精确联合回放在 base/K+2/8bps 三个场景都比旧近似口径多出 `1` 笔 Stoch 空单，因此旧 V4 指标不是 live runner 可直接复现的事实源。

Base K+1 current full 从旧近似 `22.8128x / -19.11% / 81.08% / 74 trades` 修正为精确联合回放 `20.9748x / -19.11% / 80.00% / 75 trades`；reused holdout 年化由 `13.0662x` 降至 `9.0210x`。

精确联合回放下，K+2 current full 为 `7.8530x / -25.04%`；8bps 为 `14.1032x / -22.46%`。压力失败的结构性原因是固定杠杆与 ATR 宽止损叠加：单笔 DI/Stoch 风险已经接近或超过组合 `20%` 回撤预算。

## 精确状态机对账

| Scenario | Old annual/DD/trades | Exact annual/DD/trades | Path equal |
| --- | ---: | ---: | --- |
| `base_k1` | `22.8128x / -19.11% / 74` | `20.9748x / -19.11% / 75` | `False` |
| `delay_k2` | `8.7014x / -23.56% / 73` | `7.8530x / -25.04% / 74` | `False` |
| `slip_8bps` | `15.3677x / -22.46% / 73` | `14.1032x / -22.46% / 74` | `False` |

## 压力优先搜索协议

- 只用 train / validation / prefit 选择腿与 ensemble；reused holdout/current full 只在冻结后揭示。
- 三个场景都要求 prefit 年化 `>=10x`、胜率 `>=50%`、train/validation/prefit 最大回撤严格小于 `20%`。
- 搜索只改风险机制：DI/Stoch 的硬止损、最长持仓、trailing、固定杠杆或按止损距离封顶的 risk sizing；不按后段坏交易拟合新的指标过滤器。

## 冻结揭示结果

| Candidate | Base full/DD | K+2 full/DD | 8bps full/DD | All current/holdout DD pass | All target pass |
| --- | ---: | ---: | ---: | --- | --- |
| `DI_FIXED_SL4.5_L3_H15_TP1.25__ST_FIXED_SL2_L2_A1_T1_H6` | `15.1089x / -15.26%` | `8.7679x / -21.87%` | `12.8203x / -15.38%` | `False` | `False` |
| `DI_FIXED_SL4.5_L3_H15_TP1.25__ST_RISK_SL2_R0.18_C2_A1_T1_H6` | `15.1089x / -15.26%` | `8.7679x / -21.87%` | `12.8203x / -15.38%` | `False` | `False` |
| `DI_FIXED_SL4.5_L3_H15_TP1.25__ST_FIXED_SL3_L2_A0.75_T1_H8` | `15.7741x / -15.26%` | `7.9619x / -25.24%` | `14.1313x / -15.38%` | `False` | `False` |
| `DI_FIXED_SL4.5_L3_H15_TP1.25__ST_FIXED_SL4_L2_A0.75_T1_H8` | `16.8819x / -15.26%` | `7.5739x / -28.76%` | `15.1120x / -15.38%` | `False` | `False` |
| `DI_FIXED_SL4.5_L3_H15_TP1.25__ST_FIXED_SL3_L2_A1_T1_H6` | `15.7487x / -15.26%` | `8.2910x / -25.39%` | `12.7232x / -17.75%` | `False` | `False` |
| `DI_FIXED_SL4.5_L3_H15_TP1.25__ST_FIXED_SL4_L2_A1_T1_H6` | `15.7487x / -15.26%` | `7.8869x / -28.90%` | `12.1072x / -21.60%` | `False` | `False` |
| `DI_FIXED_SL4.5_L3_H15_TP1.25__HYPE_1H_AR_V4_STOCH` | `16.5756x / -19.11%` | `6.9439x / -28.42%` | `12.4691x / -24.49%` | `False` | `False` |
| `DI_FIXED_SL4.5_L3_H15_TP1.25__ST_FIXED_SL3_L2_A1_T1_H8` | `15.4878x / -19.11%` | `7.2996x / -24.89%` | `12.2531x / -20.78%` | `False` | `False` |
| `DI_FIXED_SL4.5_L3_H15_TP1.25__ST_FIXED_SL4_L2_A1_T1_H8` | `16.5756x / -19.11%` | `6.9439x / -28.42%` | `12.4691x / -24.49%` | `False` | `False` |
| `DI_FIXED_SL4.5_L3_H15_TP1.25__ST_RISK_SL2_R0.15_C2_A1_T1_H6` | `14.8294x / -15.26%` | `8.5933x / -21.87%` | `12.5750x / -15.38%` | `False` | `False` |
| `DI_FIXED_SL4.5_L3_H15_TP1.25__ST_FIXED_SL2_L2_A0.75_T1_H6` | `14.9576x / -15.26%` | `8.8569x / -21.72%` | `13.4122x / -15.38%` | `False` | `False` |
| `DI_FIXED_SL4.5_L3_H15_TP1.25__ST_FIXED_SL3_L2_A0.75_T1_H6` | `15.5909x / -15.26%` | `8.3751x / -25.24%` | `13.9560x / -15.38%` | `False` | `False` |

## 后验回撤修复方向（不是冻结赢家）

冻结榜前 `12` 名没有完整回撤通过行；在全部 `431` 个 prefit pressure-gate 组合中，事后查看 reused holdout/current full 后共有 `35` 行能让三个场景回撤都小于 `20%`。这只能用于定位机制，不能重新包装成未见数据赢家。

代表行 `DI_FIXED_SL4.5_L2.5_H18_TP1.5__ST_FIXED_SL2_L2_A1_T1_H6`：base `14.3901x / -14.20%`；K+2 `7.9815x / -19.64%`；8bps `11.2061x / -18.71%`。

该方向只做三件事：DI 杠杆 `3.0x -> 2.5x`；Stoch 硬止损 `4 ATR -> 2 ATR`；Stoch 最长持仓 `8h -> 6h`。它证明风险预算可以修复回撤，但 K+2 和 reused holdout 年化显著不足，说明剩余问题是延迟后信号边际消失，而不是再调高杠杆可以解决。

## 决策边界

- 本报告先修复研究事实源，不登记新版本、不提升状态。
- 即使找到三个压力场景回撤都小于 `20%` 的冻结诊断行，也必须继续检查 K+2 年化/后段稳定性、逐笔路径、真实 stop-market 滑点和生产 runner 状态恢复。
- 若没有完整 target pass，则只能把结果描述为“回撤修复方向”，不能称为 live-ready。

## 机器证据

- JSON：`artifacts/hype_1h_ar_v4_pressure_optimization_2026-07-10.json`
- 单腿搜索：`artifacts/hype_1h_ar_v4_pressure_optimization_legs_2026-07-10.csv`
- ensemble 搜索：`artifacts/hype_1h_ar_v4_pressure_optimization_ensembles_2026-07-10.csv`
- 精确交易路径：`artifacts/hype_1h_ar_v4_pressure_optimization_trades_2026-07-10.csv`

复现：

```bash
uv run python research/hype/1h-adaptive-regime/scripts/audit_hype_1h_ar_v4_pressure_optimization.py
```
