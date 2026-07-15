# BIN-15M-AS6S-V6 mark联合状态未来OOS冻结规格

## 版本身份与状态

- 完整版本：`Binance-15M-Asset-Specific-Six-Strategy-Selector-V6`（`BIN-15M-AS6S-V6`）。
- 状态：`registered / not promoted / not live-ready`。
- 角色：15条资产专属腿、真实mark保护退出、六币全局单仓的双路线观察版本。
- 主观察：`nonpreemptive`；对照观察：`strong_breakout_preemptive`。
- 本冻结不授权持续`dry-run`或`live`，也不表示未来OOS已经通过。

## 数据与冻结边界

- 市场：Binance USD-M Futures perpetual。
- 币种：`BTCUSDT / ETHUSDT / SOLUSDT / BNBUSDT / TRXUSDT / HYPEUSDT`。
- 信号周期：资产专属`15m / 1h`；高周期特征只使用闭合K线。
- 研究选择截止：`2026-07-14T09:00:00Z`，不含该时刻。
- 当前三个月`[2026-04-14T09:00:00Z, 2026-07-14T09:00:00Z)`只作为已复用诊断窗口。
- 最终未来OOS：`[2026-07-14T09:00:00Z, 2026-10-14T09:00:00Z)`；必须等完整窗口到期后一次性读取。
- 冻结后禁止修改腿、参数、scale、路由、抢占阈值、状态机、成交模型或历史数据，也禁止查看部分未来窗口。

## 账户与路由

- 两条路线均为15条腿、六币全局单仓、允许空仓、多空双向。
- `nonpreemptive`：持仓期间其他信号直接丢弃，不排队、不修改被阻塞腿状态；账户scale `0.75`，最大有效杠杆`2.25x`。
- `strong_breakout_preemptive`：只有达到entry-time strength阈值`0.75`、高于当前机会`0.05`且当前持仓至少`1h`的强突破可以抢占；账户scale `0.75`，最大有效杠杆`2.25x`。
- 同时信号排序只允许使用入场时可知字段：入场时间、entry-time strength和sleeve id；`exit_ts / exit_reason / return / MAE`禁止参与入场仲裁。
- 只有账户实际接受的交易创建持仓并在真实退出后更新cooldown；未成交信号不创建虚拟占仓。

完整15条腿配置不在本文重复，机器事实源为[冻结清单](../artifacts/binance_as6s_v6_mark_joint_future_oos_freeze_2026-07-15.json)的`config_by_route`。

## 成交与保护语义

- 信号和入场基于Binance trade OHLC；信号在K线收盘后确定，基础入场为下一根K线开盘（K+1），另测K+2延迟压力。
- 止损、止盈和trail保护触发使用Binance 15分钟mark-price OHLC。
- 跳空穿越保护价时按同一15分钟trade open成交并施加不利滑点。
- 非跳空触发时，按同K线`trade_open / mark_open`基差映射触发价，限制在trade high/low内，再施加不利滑点。
- 同一根K线同时触发止损和止盈时采用stop-first。
- trailing只在策略K线闭合后更新，从下一根15分钟保护K线生效。
- 1小时腿的保护检查展开到其持仓期间每根15分钟mark K线，不把1小时内触发延迟到小时收盘。

## 成本与资金费

- 手续费：每次成交按notional的`0.001`。
- 基础滑点：每次成交`4 bps`不利滑点。
- 压力滑点：每次成交`8 bps`不利滑点。
- funding：使用Binance历史funding，按实际持仓区间累计。
- 压力场景：`base 4bps K+1 / stress 8bps K+1 / base 4bps K+2`。

## 冻结开发样本指标

| 路线 | scale | full笔数 | full胜率 | full年化倍数 | full最大回撤 | 当前3m收益 | 当前3m胜率 | 当前频率 | 最低压力胜率 | 最低压力回撤 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `nonpreemptive` | 0.75 | 634 | 85.65% | 31.078x | -17.99% | +132.15% | 83.50% | 1.132/日 | 81.25% | -18.38% |
| `strong_breakout_preemptive` | 0.75 | 568 | 85.21% | 30.817x | -17.04% | +190.22% | 86.02% | 1.022/日 | 81.82% | -18.33% |

以上都是开发样本观察，不是未来OOS结果。最终账户审计中两条路线均无可删除腿；scale邻域7/7通过硬门槛、5/7通过研究缓冲；134个固定scale单腿替换中，两条路线各34个通过全部研究缓冲。证据见[最终联合结果](../diagnostics/binance-as6s-v6-mark-clean-rsi-joint-refine-2026-07-15.md)与[最终账户审计](../diagnostics/binance-as6s-v6-mark-clean-rsi-joint-candidate-audit-2026-07-15.md)。

## 最终OOS一次性门禁

每条路线均必须同时满足：

- base、8bps、K+2在full和未来3m OOS的胜率均`>=80%`；
- base、8bps、K+2在full和未来3m OOS的最大回撤均严格`<20%`；
- base、8bps、K+2在full和未来3m OOS收益均为正；
- base未来OOS交易数`>=30`；
- base未来OOS开仓频率在`1–2单/日`；
- 冻结清单、trade/funding/mark数据快照和历史重建对拍全部通过。

一次性揭示程序：[reveal_binance_as6s_v6_mark_joint_future_oos.py](../scripts/reveal_binance_as6s_v6_mark_joint_future_oos.py)。在窗口到期前只能运行`--check-only`或仅读取冻结点以前数据的`--historical-parity`。
