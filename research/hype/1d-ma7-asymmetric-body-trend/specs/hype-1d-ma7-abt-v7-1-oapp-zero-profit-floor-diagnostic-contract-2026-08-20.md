# HYPE-1D-MA7-ABT-V7.1 OAPP 零利润回吐诊断合同

> 冻结日期：2026-08-20。状态：`diagnostic-only / not promoted / not live-ready`。本合同响应用户提出的“只要没回吐到0就一直持有”，不修改 V7.1，也不授权 runner 变更。

## 1. 唯一解释与候选

本轮把用户表述限定为 long OAPP 的最小改动，不覆盖 native MA7 exit、`1.5ATR` protective/trailing stop、short RSI、cooldown、PEHC、成本、funding 或 next-open 执行。

唯一新增候选 `ZPF`（zero-profit floor）：

1. long 的最高收盘浮盈曾达到原 OAPP 激活条件 `0.5×ATR7` 后，停止按“峰值浮盈回吐10%×2日”锁盈；
2. 只要日线 signal close 仍高于 entry price，OAPP 不退出；
3. signal close 首次回到 entry price 或以下时，产生原 OAPP exit reason，并在下一 UTC 日 open 全平；
4. 因 next-open 执行、手续费、滑点和 funding，`ZPF` 不是保本承诺；信号到0后实际成交可以亏损；
5. native MA7 或 1h protective stop 若更早触发，仍按 V7.1 原优先级退出。

## 2. 控制与审计

- 控制：exact `HYPE-1D-MA7-ABT-V7.1`。
- 已知对照：V7.1 全参数消融中的 long OAPP off；不重新搜索参数。
- Canonical 窗必须复现控制 `+711.04% / -18.40% / 20笔`。
- 扩展窗必须复现 `2026-08-09 55.113` 开多与控制的 `2026-08-16 56.894` OAPP 平仓。
- 对 ZPF 报告 canonical、扩展窗、8bps、额外1日lag、funding-off、近期切片、OAPP/PEHC次数和改变的 long episode。
- 单独报告 8 月事件反事实是否退出、首次成熟退出或 terminal-censored 状态。

## 3. 判定

- 若 ZPF 与 OAPP off 路径等价，应明确写“本样本中等价于关闭 OAPP”，不得包装成独立改进。
- 若 canonical 收益下降、MDD超过20%或 PEHC 贡献明显消失，不建议替换 V7.1。
- 8月事件已揭示，只能验证规则行为，不能作为晋升证据。
- 本轮只能给出 `KEEP V7.1`、`SHADOW ZPF` 或 `NO-GO ZPF`；不得登记 V7.2。
