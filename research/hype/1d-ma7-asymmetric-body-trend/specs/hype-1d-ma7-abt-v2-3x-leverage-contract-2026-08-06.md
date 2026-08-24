# HYPE-1D-MA7-ABT-V2 3x 杠杆诊断合同

> 冻结时间：2026-08-06（首次 3x 运行前）。状态：`explore / diagnostic-only / not promoted / not live-ready`。

## 研究问题

保持已登记 [V2](hype-1d-ma7-abt-v2-spec.md) 的信号、trailing-stop 反手、退出和执行路径不变，只把每次入场目标从约 `1x` 改为约 `3x`，观察复利收益、回撤、成本、实际杠杆漂移和简化破产风险。

## 冻结杠杆合同

- `L1`：登记的约 `1x` V2 基准。
- `L3`：每次自然入场或 trailing-stop 反手入场，按扣除该次成交成本后的权益建立约 `3x` 名义；
- 持仓期间数量固定，不做每日再平衡，不把实际杠杆硬钳制在 `3x`；
- 平多后反手空仍是两次独立成交；开空时按平多后的权益重新建立 `3x`；
- 下一次退出或反手前不因权益变化主动减仓；
- SMA7、ATR7、多空参数、V2 反手时序、funding、手续费和滑点不变。

## 风险模型边界

- 用组成日 K 的真实 `1h` open/high/low 检查 stop 与权益路径；若 adverse equity `<=0`，记 `intraday_bankruptcy`；
- 回测未包含 Binance 实际 maintenance-margin tier、提前强平价格、liquidation fee、保险基金或 ADL；
- `bankrupt_intraday=false` 不能解释为实盘不会强平；最大实际 intraday leverage 必须单列；
- V2 多头首日仍无 hard stop，是 3x 的重要执行风险。

## 数据、成本与检查

- Binance USD-M `HYPEUSDT` perpetual accepted `1h` 数据聚合 UTC `1d`，真实 event-time funding；
- 手续费 `0.001/fill`，基准不利滑点 `4 bps/fill`，压力 `8 bps/fill`；
- 使用冻结历史 `2025-05-31` 至 `2026-07-30 UTC`，另报告最新延伸；
- 报告 prefit、最后 `90d` flat-start、full、`8 bps`、额外延迟一天、zero-funding、近期 `1d/7d/1m/3m/6m/1y`、90 日滚动窗口和 `12h` 相位检查。

## 判定口径

该诊断不设置“收益越高即通过”的 promotion 判定。重点回答：

1. 3x 是否发生简化 intraday bankruptcy；
2. MDD 是否超过 `-50%`，实际杠杆是否明显漂过 `3x`；
3. 压力、延迟、后 90 日和 `12h` 相位是否仍为正；
4. 收益是否由少数已揭示反手事件进一步集中。

无论结果如何，3x 都只作为 V2 的 official observation，不自动成为 V2 默认仓位或新版本。
