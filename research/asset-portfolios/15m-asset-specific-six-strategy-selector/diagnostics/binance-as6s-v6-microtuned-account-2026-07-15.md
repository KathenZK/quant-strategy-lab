# BIN-15M-AS6S V6 微调账户重组（2026-07-15）

V5历史基线先按联合状态重新生成并与冻结结果对拍，然后每条腿在V5基线、最多7个稳健微调配置和删除之间做坐标搜索；排序额外偏好胜率、回撤与频率缓冲。所有结果严格截止 `2026-07-14T09:00Z`。

- V5基线对拍：`PASS`（553笔路径口径及核心指标一致）。
- 硬门槛：base/8bps/K+2的full与当前3m均要求胜率>=80%、回撤<20%、收益>0；当前3m和六币全活跃期频率均为1-2单/天；有效杠杆<=3x。
- scale选择：在通过硬门槛的scale中，优先要求所有门禁窗口回撤优于-18.5%，保留约1.5个百分点缓冲。

| 路线 | hard pass | scale | 有效最大杠杆 | full年化倍数 | full胜率 | full回撤 | 当前3m收益 | 当前3m胜率 | 当前频率 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `nonpreemptive` | `True` | 0.57 | 1.71x | 15.827x | 85.98% | -17.96% | +151.25% | 84.38% | 1.055/日 |
| `strong_breakout_preemptive` | `True` | 0.66 | 1.98x | 20.212x | 85.88% | -17.75% | +163.82% | 84.54% | 1.066/日 |

本轮仍是开发样本观察；即便hard pass，也必须继续做账户级参数消融、邻域稳定性、mark-price执行偏差和独立未来三个月OOS。

结构化结果：[`binance_as6s_v6_microtuned_account_2026-07-15.json`](../artifacts/binance_as6s_v6_microtuned_account_2026-07-15.json)；交易路径：[`binance_as6s_v6_microtuned_account_trades_2026-07-15.csv`](../artifacts/binance_as6s_v6_microtuned_account_trades_2026-07-15.csv)。
