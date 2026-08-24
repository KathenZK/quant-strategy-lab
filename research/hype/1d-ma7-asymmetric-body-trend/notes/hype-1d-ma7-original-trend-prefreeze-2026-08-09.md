# HYPE 1D MA7 原始趋势状态机：冻结前语义记录

> 日期：2026-08-09。状态：`explore / not promoted / not live-ready`。本文不是冻结合同，不登记版本，也不得据此运行历史选择。现有 `HYPE-1D-MA7-ABT-V1` 至 `V4` 保持不变，仅作为对照。

## 研究目标

把用户的原始想法还原成一个对称、因果、可执行的 UTC 日线状态机：

1. 前 `N` 个完整日收盘位于各自 `SMA7` 的同一侧；当日收盘 fresh cross 到另一侧时，视为新趋势事件；
2. 持仓后用方向性 `SMA7` slope 和 `SMA7 ± 0.75×ATR7` 容错带判断继续持有、退出或反手；
3. 空头增加 Wilder `RSI6` 主动止盈，避免等到重新上穿 MA7 才归还大段利润；
4. 多头过热后下穿 MA7 时，研究 `RSI6 > 70` 记忆能否作为提前止盈并反手空的独立通道；
5. 不继承 V4 的 post-reveal 参数与结论，不把新行为静默写回任何已登记版本。

## 已确认的不变口径

- Binance USD-M `HYPEUSDT` perpetual，信号周期为完整 UTC `1d`；
- `SMA7` 为七个完整日收盘的简单平均；`ATR7` 为日线 true range 的七日简单平均；`RSI6` 使用 Wilder/TradingView RMA；
- 收盘信号最早在下一 UTC 日 open 执行；反手必须先平旧仓、再开新仓并计两次 fill；
- 单仓、约 `1x`、非加仓，成交间数量固定；
- 手续费 `0.001/fill`、基准不利滑点 `4 bps/fill`、压力 `8 bps/fill`，实际 funding；
- 现有本地完整日截至 `2026-08-05`，全部只可作为 researcher-exposed development；新 prospective 必须从最终合同冻结后的第一个完整 UTC 日 flat-start。

## 必须由用户确认的语义

1. 空头止盈阈值原句为“连续数日 RSI6 在 70 以下”，是否应为常用的严格 `<30`；是否仅在空单已有浮盈时触发；触发后是否只平空转 flat。
2. 持仓轻微穿过 MA7、但尚未越过 `0.75×ATR7` 容错带时，fresh cross 是否进入 armed 状态；armed 是否一直有效到重新穿回 MA7 才取消。
3. slope 消失但价格仍在容错带内时，是继续持仓还是次开平仓转 flat；若平仓，不能在没有目标侧确认时自动反手。
4. 连续若干日 `RSI6 >70` 后 fresh down-cross，是否允许在尚未越过下容错带前提前 `long -> short`；是否还要求目标侧 slope。
5. fresh cross 是否直接入场而不要求 slope，还是 slope 也是入场过滤。用户最新描述更接近“cross 直接入场，slope 是持仓条件”，但运行前必须明确。
6. 原始核心是否完全不继承 V4 的 intraday trailing、hard stop、max hold 和 cooldown。建议核心臂不继承，另设执行保护臂，避免风险层改变 alpha 定义。

## 预声明实验结构

用户确认后先冻结以下互斥模块臂，不在结果揭示后临时融合：

- `A_CORE`：fresh cross + slope + `0.75×ATR7` 容错核心；
- `B_SHORT_RSI_EXIT`：A + 空头 RSI6 主动止盈；
- `C_OVERBOUGHT_REVERSAL`：A + 多头过热记忆提前反手空；
- `D_BOTH_RSI`：A + 两个 RSI6 模块；
- `E_EXECUTION_PROTECTION`：最终选定 alpha 臂 + 独立风险保护，不参与 alpha 模块选择。

主值暂定 `N_cross=1`、`N_RSI=3`；`N_cross={2,3}`、`N_RSI={2,4}` 只能作敏感性检查，不用邻域赢家改写最终身份。

## 运行禁令

在上述语义完成确认并写成冻结合同以前：

- 不得读取历史绩效来选择任何歧义答案；
- 不得生成候选排名或登记 V5；
- 只允许实现参数化状态机、因果单元测试和数据质量 fail-closed 检查；
- 所有默认配置必须显式标为 draft，不能被报告称为策略结果。

