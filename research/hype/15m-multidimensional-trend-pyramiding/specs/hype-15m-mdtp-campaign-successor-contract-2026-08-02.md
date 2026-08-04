# HYPE-15M-MDTP Campaign Successor 研究合同（2026-08-02）

## 身份与边界

- Family：`HYPE-15M-Multidimensional-Trend-Pyramiding`。
- 研究角色：未登记的 campaign successor，状态为 `explore / not promoted / not live-ready`；本合同不创建 `V2`。
- 标的：Binance USD-M `HYPE/USDT:USDT` perpetual。
- 目标：把旧 V1 的连续目标仓位切换改为低换手、固定数量、目标持有 `3–14 天` 的趋势 campaign。
- V1 与 V35 只作历史对照；不得继承其参数、收益、状态或已揭示 OOS 结论。

## 冻结时间边界

- 历史 Train：`[2025-05-30 10:30 UTC, 2026-02-01 00:00 UTC)`。
- Embargo：`[2026-02-01 00:00 UTC, 2026-02-15 00:00 UTC)`。
- 历史 Validation：`[2026-02-15 00:00 UTC, 2026-08-02 00:00 UTC)`；每个方向只允许揭示一次，揭示后不得修参。
- Prospective OOS：`[2026-08-02 00:00 UTC, 2026-11-02 00:00 UTC)`；本轮锁定但不揭示、不排名、不消融、不回填。
- 仓库现有 HYPE 闭合 `15m` 数据截至 `2026-08-01 15:15 UTC`，早于 prospective OOS 起点。

## 多周期与时序

- `4h`：方向许可和慢速结构退出。
- `1h`：突破、确认、加仓、EXHAUSTING 与利润保护更新。
- `15m`：下一根 open 成交及保护止损触发；不生成趋势方向，不连续调仓。
- `1h/4h` 只使用完整闭合 K；信号在高周期收盘后，于下一可交易 `15m open` 执行。
- 反向许可出现时先退出，禁止同一时点直接反手；必须等待新的完整入场事件。

## 独立多空研究

- Long 与 short 使用相同研究框架但分别搜索、排名、验证和判定。
- 一边通过不得补贴或掩盖另一边失败；最终只允许启用独立通过的一侧。
- 不在 Validation 揭示后根据方向结果删除、翻转或重新镜像规则。

## Campaign 状态与仓位

```text
FLAT -> SEED(35%) -> CORE(70%) -> PYRAMID_1(85%) -> PYRAMID_2(100%)
                                      \-> EXHAUSTING -> FLAT
```

- `1h` Donchian 突破且 `4h` regime 同向时建立 `35%` SEED。
- 后续完整 `1h` 仍站在原突破边界之外，或回调后 reclaim，补到 `70%` CORE。
- 只有 campaign 扣除预计退出成本后的净浮盈为正、趋势仍同向、open risk 允许时，才可加到 `85%` 和 `100%`。
- 最多两次 pyramid add；亏损中禁止加仓，不做连续波动率目标调仓。
- 方向许可弱化时进入 EXHAUSTING，只停止加仓；不得仅因普通分数回落平掉 core。

## 风险、数量与杠杆

- `R0 = campaign 启动时账户权益的 1%`，整个 campaign 固定不漂移。
- 初始完整计划数量由 entry-to-stop 距离、双边预计成本和 `R0` 反推；每次 fill 后保存真实 signed quantity。
- 每次加仓后的 projected stop-out equity 不得低于 `campaign_entry_equity - R0`。
- 名义杠杆 `3x` 是绝对上限，不是目标；每次 fill 后及持仓漂移过程中都记录 effective leverage。
- 压力路径若可能使单 campaign 损失超过 `3%` 账户权益，候选保持 `not live-ready`。
- 费用：base 为 fee `0.001/fill` + adverse slippage `4 bps/fill` + 实际 funding；stress 使用 `8 bps/fill` slippage。

## 止损、MFE 与退出

- 初始 stop 使用 `1h` ATR 与前置结构低/高点的较宽者；只允许收紧。
- 不设固定止盈、不设 `14 天` timeout；趋势继续时允许持有更久。
- `4h` 慢速 Donchian 结构只负责收紧 core stop。
- campaign 净 MFE 达到 `2R0` 后，利润保护目标为 `campaign_entry_equity + 0.5 × peak_net_profit`。
- 结构 stop 与 MFE floor 同时存在时采用保护利润更多的一条。
- stop gap 使用更差 open；其余 stop fill 计 adverse slippage 与 fee。

## 预声明搜索空间

- `4h regime EMA`：`30 / 42 / 60` 根。
- `1h entry Donchian`：`48 / 72 / 96` 根。
- 初始最小 stop：`2.5 / 3.5 × ATR24_1h`，并与前置 `24h` swing stop 取较宽者。
- `4h structural exit Donchian`：`18 / 30 / 42` 根。
- 每个方向共 `3 × 3 × 2 × 3 = 54` 个预声明候选；不得在 Validation 揭示后扩展。

Train 排名顺序固定为：正收益 Train fold 数、最差 fold 净收益、全 Train net Sharpe、全 Train net return、较低换手。至少要有 `5` 个闭合 campaign、无破产、无 `3x` fill-cap 违规，才有资格成为方向候选。

## Validation 与失败纪律

方向候选至少同时满足以下条件，才可称为 `research-pass`，但仍不 promotion：

- Validation base net return `> 0`、Sharpe `> 0`、MDD 不超过 `20%`。
- Validation 至少 `3` 个闭合 campaign；平均持仓不少于 `24h`。
- Validation stress cost 后仍为正。
- 无 open-risk、数量账本、stop 时序或有效杠杆 blocker。
- full / no-pyramid / no-MFE-floor / no-structural-exit 消融能够解释收益来源。

任一方向失败就保持该方向 `explore / not promoted / not live-ready`。不得在同一 Validation 上调整参数；继续研究必须等待 prospective OOS 或提出 materially new 的机制合同。
