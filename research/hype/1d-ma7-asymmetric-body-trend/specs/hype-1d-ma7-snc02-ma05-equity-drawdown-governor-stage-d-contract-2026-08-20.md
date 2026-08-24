# HYPE-1D-MA7-SNC02 MA05 权益回撤节流 Stage D 冻结合同

> 冻结日期：2026-08-20。状态：`diagnostic-only / explore / not promoted / not live-ready`。本合同在首次运行 Stage D 结果前写入；结果揭示后不得新增阈值、修改恢复带或门槛并重称预注册结果。

## 1. 研究问题与边界

Stage B 证明固定0.5x可把回撤压到 `-19.50%`，但会把总收益和最新趋势收益都近似砍半；确认扩仓会在短暂延伸后追高放大反转。Stage C 证明固定单笔ATR stop也无法处理跨多笔交易的连续亏损链。Stage D 因此只测试一个系统级假设：

> 正常状态保留 `MA05_1X`；只有策略权益已经从历史高点形成可观回撤时才降低当前和后续仓位，权益恢复后再回到1x。

所有臂固定 exact SNC02、`MA05=0.5ATR7`结构退出、无硬stop、无保本、无部分止盈、无试仓确认。信号和退出路径不因仓位改变；本层只改变实际quantity和成本。全部历史已揭示，只作机制诊断，不登记版本、不promotion、不修改V7.1或runner。

## 2. 固定实验臂

| Arm | 降风险触发 | 低风险目标 | 恢复1x阈值 |
|---|---:|---:|---:|
| `MA05_CTRL` | 无 | 1.00x | 无 |
| `DG08_L50_R04` | 日收盘权益DD `<= -8%` | 0.50x | DD `>= -4%` |
| `DG10_L50_R05` | 日收盘权益DD `<= -10%` | 0.50x | DD `>= -5%` |
| `DG08_L25_R04` | 日收盘权益DD `<= -8%` | 0.25x | DD `>= -4%` |
| `DG10_L25_R05` | 日收盘权益DD `<= -10%` | 0.25x | DD `>= -5%` |

这是首次结果前冻结的2×2有限网格。不得运行后补搜9%、低风险0.4x或其他恢复带。

## 3. 权益高水位与状态机

- 每个flat-start回测窗口从 `equity=1.0`、`HWM=1.0`、正常状态1x开始；不继承窗外仓位或高水位。
- 每个完整UTC日结束后，以当日close对当前实际quantity作只读mark，得到 `daily_marked_equity`；该mark只用于状态判断，不虚构成交或改写小时回放的mark顺序。
- `HWM=max(previous_HWM, daily_marked_equity)`；`DD=daily_marked_equity/HWM-1`。
- 正常状态在DD达到冻结触发线时，目标状态切到低风险；低风险状态只有DD恢复到冻结恢复线以内才回1x。中间区域保持原状态，形成hysteresis。
- 状态切换于下一UTC open执行：若仍持仓，按当时权益和价格rebalance；若flat，只更新后续fresh signal的入场目标。低风险状态覆盖当前仓位与之后新仓。
- 降风险不是止盈或平仓，不改变campaign身份；resize成本、turnover、funding与余仓PnL全部计入原campaign。

## 4. 同时事件与执行延迟

同一UTC open若风险状态切换与SNC02/MA05动作重合：

1. 先使冻结的目标风险状态生效；
2. 再执行原信号路径：平旧仓后，新仓直接按新状态目标入场；
3. 若仍是同一持仓，再rebalance到新状态目标，避免无意义的先调仓后平仓。

额外 `1d lag` 压力统一延迟SNC02、MA05和风险状态切换一个完整日。状态判断仍逐日发生；待执行状态按其原判断日排队，不使用未来信息。funding按实际事件时点和实际quantity计入。

## 5. 数据、成本与窗口

- 市场：Binance USDⓈ-M perpetual `HYPEUSDT`；信号与状态 `1d`，风险回放 `1h`，UTC。
- 主窗：扩展 `2025-05-31 -> 2026-08-20 terminal`；同时报告canonical `2025-05-31 -> 2026-08-06`。
- 成本：手续费 `0.001/fill`，基础滑点 `4bps/fill`，实际funding；压力为 `8bps`、funding-off、额外 `1d lag`。
- 最近flat-start：`1d/7d/1m/3m/6m/1y`；年度flat-start：2025 partial、2026 YTD。
- 风险：按小时open、funding pre/post、entry/exit/resize实际顺序计算chronological `1h` MDD。

## 6. 首次运行前冻结的判定

以 `MA05_CTRL` 与其2026-08-09 long为参照：

- `MDD20_PASS`：扩展窗真实1h MDD `>= -20%`。
- `ROBUSTNESS_PASS`：扩展窗净收益 `>0`、PF `>=1`、8bps净收益 `>0`、额外1日lag净收益 `>0`。
- `RETURN_RETENTION_PASS`：扩展窗净收益至少为control的 `50%`。
- `LATEST_TREND_CAPTURE_PASS`：存在2026-08-09 long、截至terminal仍持有，且campaign净收益至少为control同笔的 `60%`。
- `CONTINUATION_CANDIDATE`：同时满足上述四项。

另报告低风险时间占比、降风险/恢复次数、最近long入场和终点时的风险状态。若多个臂通过，优先低风险暴露更少且收益保留更高者；通过仍只代表post-reveal风险候选，不代表新alpha、版本或上线资格。

## 7. 产物

- 研究脚本：`scripts/research_hype_1d_ma7_snc02_ma05_equity_drawdown_governor_stage_d.py`
- 机器证据：`artifacts/hype_1d_ma7_snc02_ma05_equity_drawdown_governor_stage_d_2026-08-20.json`
- 诊断报告：`diagnostics/hype-1d-ma7-snc02-ma05-equity-drawdown-governor-stage-d-2026-08-20.md`
