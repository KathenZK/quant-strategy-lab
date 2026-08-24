# Binance 月频 Top10 Long-only 可实盘化审计（2026-08-20）

## 裁决

**`NO-GO for promotion / PERFORMANCE_INVALIDATED`。** 现阶段不能交接 runner、不能进入 dry-run、更不能实盘。

原 Top10 的横截面动量仍是值得保留的 alpha 假设；在旧引擎下，`ADV Top10 target12` 是本轮唯一接近运营风险区间的低自由度候选。但执行审计发现原回测存在同 bar 成交、零成交占位 K 线入选、不可成交退出和持仓缺价被当作零收益等硬 blocker。因此本轮所有绩效数字只能作为方向性诊断，不能作为 promotion 或资金配置证据。

本轮没有登记版本，没有生成 live spec，也没有修改 `quant-runner`。

## 研究设计

先保持 `1M Top10` alpha 不动，再依次回答四个问题：

1. **能否用少自由度市场风控降低左尾？** 冻结 `BTC SMA200 + target15 + 月中退出`，并只把 SMA/风险目标邻域当稳定性诊断。
2. **能否用多形成期降低单一 1M regime 集中？** 冻结 `1M/3M/6M` 三袖套等资本 + `target15`，再做逐袖消融。
3. **若新机制失败，纯风险预算最低能走到哪里？** 只读取事前固定的 `target12`，不扫描相邻风险目标。
4. **研究路径能否由 runner 因果复现？** 用真实 15m bar 审计信号可知时间、`00:15 UTC` 成交、成交量/笔数、退出与每日持仓估值。

所有候选沿用点时上市、`ADV>=1000万 USDT`、手续费 `0.001/边`、滑点 `4 bps/边`和逐日资金费。旧引擎公平窗口为 `2020-08-01`–`2026-06-30`；`2024-01-01`–`2026-06-30` 只称 exposed-regime holdout，不是 clean OOS。

## 第一层：市场状态风控失败

冻结主候选为 `ADV Top10 + target15 + BTC SMA200 月初许可 + 月中退出`。

| 旧引擎方向性结果 | 总收益 | CAGR | Sharpe | MDD | 后段收益 | 后段 MDD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BTC SMA200 主候选 | `+45.48%` | `6.55%` | `0.573` | `-24.91%` | `+4.92%` | `-24.91%` |
| 删除月中退出 | `+58.64%` | `8.12%` | `0.650` | `-22.19%` | — | — |

主候选未达到冻结的 Sharpe、CAGR和后段 MDD 参考线；删除月中退出反而全面改善，说明月中 gate 没有提供增量。`SMA150/200/250 × target12/15/18` 邻域 Sharpe 约 `0.47`–`0.65`，没有稳定平台。**不采纳市场 gate。**

## 第二层：多形成期 MH136 失败

| 旧引擎方向性结果 | 总收益 | CAGR | Sharpe | MDD | 后段收益 | 后段 MDD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `1M+3M+6M` 等权袖套 target15 | `+96.65%` | `12.12%` | `0.759` | `-28.27%` | `+23.55%` | `-14.54%` |
| 删除 6M，仅 `1M+3M` | `+99.78%` | `12.42%` | `0.787` | `-28.08%` | — | — |
| all-listed 控制 | `+84.48%` | `10.91%` | `0.693` | `-30.34%` | — | — |
| `2x` 成本 | `+92.56%` | `11.72%` | `0.739` | `-28.51%` | — | — |
| 延迟 1d | `+79.18%` | `10.37%` | `0.669` | `-28.48%` | — | — |

主候选未过 Sharpe/MDD，五个完整 12m cohort 仅两个为正；删除 6M 后还被整体支配。**不采纳 MH136，也不从消融结果挑 `1M+3M` 作为新 winner。**

## 第三层：target12 只保留为风险预算假设

在不改 alpha 的前提下，旧引擎中的 `ADV Top10 target12` 给出：

- 总收益 `+94.82%`、CAGR `11.94%`、年化波动 `13.44%`、Sharpe `0.906`、MDD `-25.073%`；MDD 仍比 `-25%` 参考线差约 `7 bps`。
- 后段收益 `+39.71%`、Sharpe `1.047`、MDD `-13.18%`；all-listed 控制为 `+92.01%`、Sharpe `0.887`、MDD `-27.45%`。
- `2x` 成本仍约 `+90.34%`；延迟 1d 约 `+77.43%`。相对同风险预算全市场等权基准，年化算术超额 `7.75%`、IR `0.948`，月度 bootstrap 年化超额 `p05/median/p95 = 1.51%/7.51%/14.33%`。
- 月度 bootstrap 中，终值收益 `p05=+18.05%`、Sharpe `p05=0.284`；但时间顺序不被 bootstrap 保留，不能替代真实 cohort。
- 五个完整非重叠 12m cohort 收益依次为 `+33.92% / -5.85% / -6.57% / +21.54% / -2.83%`，只有 `2/5` 为正，失败集中在 `2021-08`–`2023-07` 和 `2024-08`–`2025-07`。
- 按单笔不超过前 30 日 ADV 的 `0.5%` 估算，容量上限最小值约 `$0.95m`、`p05` 约 `$6.46m`、中位约 `$48.62m`。这是历史容量诊断，不是下单额度。

所以 target12 只能解释为“用约 13% 平均 gross exposure 换取可接受账户波动”的 sizing 方案；它没有创造 alpha，也没有解决 12m 时间稳定性。更重要的是，以下执行审计使这些数字失去有效性。

## 第四层：执行审计发现硬 blocker

### 1. 信号与成交发生在同一根日线开盘

上一完整月的最后一根 `15m` K 只有在新月 `00:00 UTC` 后才能确认闭合，但旧引擎把新信号成交在同一日 `00:00` open。因果可执行基准至少应从 `00:15 UTC` open 开始，并让旧仓承担前 15 分钟真实收益。

### 2. 零成交占位 K 线被当成可成交价格

旧引擎只检查开盘价非空，没有要求 `volume>0`、`trade_count>0` 或合约状态为 `TRADING`。原 target12 有四次不可成交入场：

| 月份 | symbol | `00:15` open | volume | trades |
| --- | --- | ---: | ---: | ---: |
| 2024-09 | FRONT | `0.8996` | `0` | `0` |
| 2025-04 | BNX | `2.0` | `0` | `0` |
| 2025-05 | ALPACA | `1.19` | `0` | `0` |
| 2025-08 | LOKA | `0.11323` | `0` | `0` |

本地原始 FRONT 数据在 `2024-09-01 00:00` 至 `2024-09-11 09:45 UTC` 共 1000 根 15m bar 都保持 `0.8996`，且成交量、quote volume、trade count 全为 0；这不是可成交市场。Binance 的 [FRONT→SLF 官方公告](https://www.binance.com/en/support/announcement/detail/3ab5488a00e04d4fb338c77ea28326a8) 也说明 symbol 生命周期事件必须进入点时资格账，不能只凭 K 线存在推断可交易。

### 3. 不可成交退出和持仓缺价被静默成零收益

原引擎的价格路径对普通日收益、换仓日前半段和后半段都使用 `.fillna(0)`。这会把“无法估值/无法退出”变成“当天没有盈亏”。执行审计计数如下：

| 路径 | invalid entry | invalid exit | held missing close | 合计 |
| --- | ---: | ---: | ---: | ---: |
| 原 target12 / `00:00` | 4 | 5 | 32 | **41** |
| `00:15` 可成交入选后 | 0 | 2 | 13 | **15** |

顺延掉不可成交入场后，FRONT 被 BOND 替换，绩效方向变化不大：公平窗口指示性总收益 `+94.27%`、Sharpe `0.903`、MDD `-24.86%`。但仍有 BNX、VIDT 不可成交退出，以及 `FTM/KNC/MANA/MKR` 三天和 BNX 一天共 13 个持仓缺价单元，因此 `performance_valid=false`。小的绩效差异不等于问题不重要；它说明的是错误没有在这段样本里造成巨大数值变化，而不是执行语义已经成立。

## Gate 矩阵

| 门禁 | 结果 | 裁决 |
| --- | --- | --- |
| alpha 方向性 | target12 对等风险市场基准有正超额 | 保留假设，不是有效绩效 |
| MDD | 旧引擎 `-25.073%` | 未过冻结 `-25%` 线 |
| 时间稳定性 | 完整 12m cohort `2/5` 为正 | 失败 |
| 市场 gate | Sharpe/CAGR/后段 MDD 失败 | 不采纳 |
| MH136 | Sharpe/MDD/cohort/消融失败 | 不采纳 |
| 成本与容量 | 方向性压力尚可，小资金容量不是首要问题 | 仅诊断 |
| closed-bar 时序 | `00:00` 同 bar 成交 | 硬 blocker |
| entry/exit/估值完整性 | 原路径 41 个、修正入选后仍 15 个 blocker | 硬 blocker |
| runner parity / 状态机 | 未实现 | 未通过 |
| prospective evidence | 无 | 未通过 |

## 变成可实盘策略的最短路径

1. **先修数据与生命周期，不再调参。** 按[执行语义修复合同](../specs/binance-1d-mcsm-long10-execution-repair-contract-2026-08-20.md)建立点时合约状态账，补齐持仓缺口，禁止持仓收益 `fillna(0)`。
2. **冻结重跑一个候选。** 只重跑 `ADV Top10 target12`，使用 `00:15` 后真实可成交价、不可成交顺延、实际退出和逐笔成本；四类 blocker 必须全为 0。
3. **重新判定 alpha 是否存在。** 原绩效作废后，重新看全段、all-listed、等风险市场基准、五个 12m cohort、2x 成本、1d 延迟、bootstrap 和容量；不得用当前数字作先验救援。
4. **若研究门禁通过，再实现 runner parity。** 需要实时 universe/lifecycle snapshot、闭合 15m 信号、目标订单与实际成交分离、资金费/手续费/滑点账、partial fill、拒单、断流、重启恢复和逐日权益对账。
5. **先影子再 dry-run，最后才考虑 live。** 至少跨多个真实月初完成 research-to-runner reconciliation；新的 prospective 月份才是晋升证据。初始资金上限必须由历史最差流动性、订单参与率和交易所最小下单单位共同决定，而不是由历史收益决定。

## 可复现证据

- [主候选合同](../specs/binance-1d-mcsm-long10-liveability-candidate-contract-2026-08-20.md)
- [MH136 合同](../specs/binance-1d-mcsm-mh136-liveability-contract-2026-08-20.md)
- [target12 风险预算合同](../specs/binance-1d-mcsm-long10-tv12-risk-budget-contract-2026-08-20.md)
- [执行修复合同](../specs/binance-1d-mcsm-long10-execution-repair-contract-2026-08-20.md)
- [Long10 可实盘化汇总](../artifacts/binance-1d-mcsm-long10-liveability-2026-08-20-summary.json)
- [MH136 汇总](../artifacts/binance-1d-mcsm-mh136-liveability-2026-08-20-summary.json)
- [执行时序汇总](../artifacts/binance-1d-mcsm-long10-target12-execution-timing-2026-08-20-summary.json)
- [执行 blocker 明细](../artifacts/binance-1d-mcsm-long10-target12-execution-timing-2026-08-20-blockers.csv)
- [可实盘化脚本](../scripts/research_binance_1d_mcsm_long10_liveability.py)
- [MH136 脚本](../scripts/research_binance_1d_mcsm_mh136_liveability.py)
- [执行时序审计脚本](../scripts/audit_binance_1d_mcsm_long10_target12_execution_timing.py)
