# HYPE-1D-MA7-ABT-V6 固定 3x 杠杆诊断合同

> 冻结时间：2026-08-10（首次运行前）。状态：`diagnostic-only / not promoted / not live-ready`。

## 研究问题

回答一个且仅一个问题：登记的 `HYPE-1D-MA7-Asymmetric-Body-Trend-V6`
（`PEHC_294`）保持全部信号、退出、OAPP、shadow 与 handoff 规则不变，只把每次
实际入场的目标杠杆从 `1x` 改为固定 `3x`，已暴露历史收益、回撤与尾部风险会怎样。

本轮不搜索杠杆倍数，不修改 V6 的默认 `1x` 身份，不登记 V7，不用于 promotion
或 runner handoff。

## 唯一变量

- Control：exact V6 `PEHC_294`，每次实际入场目标 `1x`。
- Candidate：exact V6 `PEHC_294`，每次自然入场、forced reversal 或 PEHC handoff
  入场均以成交成本后的权益为基数，目标 `3x`。
- 成交后数量固定至退出或反手，不逐日再平衡；因此价格逆向移动时
  `marked leverage` 可以高于 `3x`。
- shadow original-long 不占资金、不持有数量、不产生 PnL、手续费或 funding；
  只在 handoff 被接受并成为实际 short 时使用 `3x`。
- 除仓位数量外，V6 的 `SMA7/ATR7`、OAPP、RSI6、保护、cooldown、max hold、
  `PEHC_294` 参数、执行顺序与单仓约束全部不变。

## 数据、执行与成本

- Binance USD-M `HYPEUSDT` perpetual。
- accepted、closed-only 的真实 `1h` 数据聚合完整 UTC 日 K。
- 冻结主窗 `[0,432)`：`2025-05-31` 至 `2026-08-05 UTC` 共 432 个完整日；
  terminal open 为 `2026-08-06T00:00:00Z`。
- 日线信号只读已经闭合的数据，最早在下一可执行 open 成交；PEHC 保留
  `next_utc_open` 复核。
- 手续费 `0.001/fill`，base 不利滑点 `4 bps/fill`，计真实 Binance funding；
  压力滑点 `8 bps/fill`。

## 必须输出

1. exact V6 `1x` 与固定 `3x` 的全窗收益、折算年化、真实顺序 `1h` MDD、
   日内极值 MDD、PF、胜率、交易数、多空贡献、成本、funding 和最大 marked leverage；
2. `8 bps`、funding-off、额外一日 signal lag；
3. 最近 `1d/7d/1m/3m/6m/1y`、8 个 54 日 cold-flat block、90 日窗口每 30 日滚动；
4. `0h–23h` 日界相位；无法形成完整审计窗的相位必须显式记录错误，不能当作通过；
5. 小时 open / funding 顺序下的权益归零检查，以及 maintenance-margin
   `0.5%/1%/2.5%/5%` 敏感性；这只作简化风险筛查，不冒充 Binance 分层强平模拟；
6. 单独生成固定 `3x` 完整交易路径 HTML，包含全价格历史、SMA7、权益、逐笔入退场、
   每笔连线和交易表，并与机器结果逐笔对账。

## 裁决纪律与治理偏差

1. V6 规格与 PEHC 原预注册合同原本要求 `1x` clean prospective PASS 前不运行杠杆。
   用户于 2026-08-10 明确要求查看 V6 的 `3x` 表现，本轮因此只作为一次
   researcher-exposed diagnostic observation；该偏差必须写入决策记录。
2. 无论收益多高，结果都不能解锁杠杆、改变前瞻 observer、修复 V5 的 H FAIL，
   或提升 V6 的状态。
3. 若任一主相位发生权益归零、简化 maintenance breach、极端 marked leverage，
   或回撤明显超出 `1x`，结论必须优先报告尾部风险，不能只展示复利收益。
4. 本轮不根据结果改止损、cooldown、handoff、OAPP 或杠杆倍数。
