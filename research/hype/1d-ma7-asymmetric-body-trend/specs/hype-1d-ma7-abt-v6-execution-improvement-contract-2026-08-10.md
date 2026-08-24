# HYPE-1D-MA7-ABT-V6 执行层优化诊断合同

> 冻结时间：2026-08-10（首次运行前）。状态：`diagnostic-only / not promoted / not live-ready`。

## 研究问题

只探索执行层，不优化持仓逻辑：登记的 `HYPE-1D-MA7-Asymmetric-Body-Trend-V6`
（`PEHC_294`）保持信号、OAPP、PEHC、保护止损、cooldown、max hold、RSI6、
MA7/ATR7、funding 与单仓约束不变；只把信号出现后的实际成交方式改为“更优限价 +
超时市价兜底”，看能否改善 exact V6 `1x` 的边际收益和真实 `1h` 回撤。

本轮不研究杠杆，不登记 V7，不推进 runner，不生成交易路径 HTML。

## 固定成交模型

- 数据：Binance USD-M `HYPEUSDT` perpetual；UTC `1d` 信号，真实 `1h` high/low/open
  判断触价与风险。
- 限价成交：保留手续费 `0.001/fill`，不加 `4 bps` 不利市价滑点。
- 市价兜底：手续费 `0.001/fill` + `4 bps` 不利市价滑点；压力场景兜底滑点为 `8 bps`。
- 入场优化适用自然入场、forced reversal 和 PEHC handoff 实际入场；shadow 原long不占资金，
  不产生执行优化。
- 出场优化只适用非保护性退出；`protective_stop` 不延迟，仍立即执行。
- 等待退出限价期间，如果保护止损先触发，按保护止损退出；否则限价触及则按限价退出，
  未触及则超时市价兜底。
- 若优化导致成交时间越过下一笔已排定交易、terminal 或不可重放边界，该候选必须显式失败，
  不能静默重排信号。

## 固定候选

限价距离使用 `k * ATR7(signal_day)`，`k in {0.05, 0.10, 0.20}`；
超时使用 `{6h, 24h}`。三组模式：

1. `entry-only`：只优化入场。
2. `exit-only`：只优化非保护性退出。
3. `entry+exit`：同时优化入场与非保护性退出。

合计18个固定候选；不得按结果追加阈值、timeout或混合规则。

## 必须输出

1. exact V6 control 与18个候选的全窗收益、真实顺序 `1h` MDD、日内极值 MDD、PF、
   胜率、交易数、多空笔数、成本、funding、最大 marked leverage。
2. 限价成交次数、兜底次数、平均改善、放弃/失败原因、是否改变逐笔行为和 PEHC 事件。
3. `8 bps`、funding-off、额外一日 signal lag。
4. 最近 `1d/7d/1m/3m/6m/1y`、8个54日 cold-flat block、13个90日滚动窗口。
5. 核心链条事件变化：`protective_stop`、`handoff_accept`、`long_mfe`、`short_rsi`、
   `shadow_start`。

## 通过门

候选只有同时满足以下条件才记为 `PASS_DIAGNOSTIC_ONLY`：

- 全窗收益高于 exact V6。
- 真实顺序 `1h` MDD 不大于 exact V6。
- `8 bps`、funding-off、lag 不出现收益与MDD双劣。
- 8个 cold-flat block 中不出现相对 V6 的双劣块。
- 核心链条没有被削弱。
- 成交改善不只来自极少数不可稳定复现的触价。

任何失败都不改变 V6，且不得继续在同一已暴露历史上调 execution 参数救援。
