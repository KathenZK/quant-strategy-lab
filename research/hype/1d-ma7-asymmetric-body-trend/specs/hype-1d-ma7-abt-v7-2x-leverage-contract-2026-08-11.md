# HYPE-1D-MA7-ABT-V7 固定 2x 杠杆诊断合同

> 冻结时间：2026-08-11（首次运行前）。状态：`diagnostic-only / not promoted / not live-ready`。

## 研究问题

回答一个且仅一个问题：登记的 `HYPE-1D-MA7-Asymmetric-Body-Trend-V7` 保持全部信号、退出、OAPP、PEHC、short cooldown `3d` 与执行顺序不变，只把每次真实入场的目标杠杆从 `1x` 改为固定 `2x`，已暴露历史收益、回撤与尾部风险会怎样。

本轮不搜索杠杆倍数，不修改 V7 的默认 `1x` 身份，不用于 promotion、live spec 或 runner handoff，不生成交易路径 HTML。

## 唯一变量

- Control：exact V7，每次真实入场目标 `1x`。
- Candidate：exact V7，每次自然入场、forced reversal 或 PEHC handoff 入场均以成交成本后的权益为基数，目标 `2x`。
- 成交后数量固定至退出或反手，不逐日再平衡；因此价格逆向移动时 `marked leverage` 可以高于 `2x`。
- PEHC shadow 不占资金、不持有数量、不产生 PnL、手续费或 funding；只有 handoff 接受成为真实 short 时使用 `2x`。
- 除仓位数量外，V7 的 `SMA7/ATR7`、OAPP、RSI6、保护、cooldown、max hold、`PEHC_294` 参数、执行顺序与单仓约束全部不变。

## 数据、执行与成本

- Binance USD-M `HYPEUSDT` perpetual。
- accepted、closed-only 的真实 `1h` 数据聚合完整 UTC 日 K。
- 冻结主窗 `[0,432)`：`2025-05-31` 至 `2026-08-05 UTC` 共432个完整日；terminal open 为 `2026-08-06T00:00:00Z`。
- 日线信号只读已经闭合的数据，最早在下一可执行 open 成交；PEHC 保留 `next_utc_open` 复核。
- 手续费 `0.001/fill`，base 不利滑点 `4 bps/fill`，计真实 Binance funding；压力滑点 `8 bps/fill`。

## 必须输出

1. exact V7 `1x` 与固定 `2x` 的全窗收益、折算年化、真实顺序 `1h` MDD、日内极值 MDD、PF、胜率、交易数、多空贡献、成本、funding 和最大 marked leverage；
2. `8 bps`、funding-off、额外一日 signal lag；
3. 最近 `1d/7d/1m/3m/6m/1y`、8个54日 cold-flat block、90日窗口每30日滚动；
4. `0h–23h` 日界相位；无法形成完整审计窗的相位必须显式记录错误，不能当作通过；
5. 小时 open / funding 顺序下的权益归零检查，以及 maintenance-margin `0.5%/1%/2.5%/5%` 敏感性；这只作简化风险筛查，不冒充 Binance 分层强平模拟。

## 裁决纪律

1. 用户于 2026-08-11 明确要求查看 V7 的 `2x` 表现，本轮只作为 researcher-exposed diagnostic observation。
2. 无论收益多高，结果都不能解锁杠杆、改变 V7 默认 `1x` 身份、创建 live spec、推进 dry-run/live 或授权 runner。
3. 若任一主相位发生权益归零、简化 maintenance breach、极端 marked leverage，或回撤明显超出 `1x`，结论必须优先报告尾部风险，不能只展示复利收益。
4. 本轮不根据结果改止损、cooldown、handoff、OAPP 或杠杆倍数。
