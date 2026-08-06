# HYPE-15M-Multi-Timeframe-Probe-Pyramiding Core Ledger

## Family Identity

- Full family：`HYPE-15M-Multi-Timeframe-Probe-Pyramiding`
- Alias：`HYPE-15M-MTPP`
- 市场：Binance USD-M perpetual；`HYPE/USDT:USDT`
- 周期：闭合 `1w/1d` 定假设、`4h/1h/15m` 择时、下一根 `15m open` 执行
- 机制：日周假设 + RSI/KDJ 位置 + 试仓 + 真实浮盈确认 + 回踩恢复滚仓 + 迟滞保护
- 边界：不是延续概率模型，不继承 MDTP、PKTSC、HTO、MII 或其他 HYPE 家族状态

## Current State

- 当前版本：无；只有预先冻结的初始机制诊断。
- 状态：`explore / diagnostic-only / not promoted / not live-ready`。
- 风险口径：止损距离与账户风险分离；同一价格路径比较 `1%/3%/10%` 计划风险，`10%` 是用户容忍上限而非默认推荐值，实际 leverage 仍不得超过 `3x`。
- 完整机制：Long/Short `trader_full` 在 `1%` 风险下分别 `-4.08%/-5.61%`，零成本也负；平均持有 `27.0/30.6h`，动态 stop 使数日 campaign 重新变成约一天并反复试单。
- 局部线索：无动态 stop 的 Short `timed_pyramid` 在 `1%/3%` 风险下 `+5.37%/+13.87%`、平均持有 `101.9h`；但只有 23 个 campaign、五段 `3/5` 为正，配对增量 bootstrap CI 跨零，不构成 support。
- 风险结论：提高到 `10%` 不改变 stop 次数，只把完整政策放大到 Long/Short `-30.81%/-42.61%`、MDD `-49.48%/-46.91%`；部分 arm 还出现 effective leverage `>3x`。
- 下一门：淘汰本轮动态 stop；Short 试仓/盈利确认/回踩加仓只可作为独立跨资产或 prospective 假设，本轮不创建版本、不 promotion。

## Version Rules

- 本轮 historical diagnostic 不构成 registered version。
- 改变日周假设、RSI/KDJ 触发、结构止损、确认层级、MFE 保护、风险预算或执行时序都属于新冻结轮次。
- 只有用户明确要求登记且 prospective OOS、执行和风险门禁通过后，才允许创建 `V1`；登记不等于 promotion。

## Version Table

当前无 registered version。

## Shared Assumptions

- 数据：Binance 闭合 `15m` OHLCV 聚合更高周期；高周期只在闭合后可见；实际 funding。
- 执行：闭合 `15m` 产生动作，下一根 open 成交；stop 从设定后的下一根开始生效，gap 按更差 open。
- 成本：fee `0.001/fill`、base adverse slippage `4 bps/fill`、stress `8 bps/fill`。
- 风险：同一路径比较计划风险 `1%/3%/10%`；最大 fill/effective leverage `3x`；亏损中禁止加仓。
- Prospective OOS：`[2026-08-02, 2026-11-02 UTC)` 保持未揭示。

## Evidence Map

- Spec：[初始研究合同](specs/hype-15m-mtpp-initial-research-contract-2026-08-03.md)
- Diagnostics：[初始研究](diagnostics/hype-15m-mtpp-initial-research-2026-08-03.md)
- Scripts / artifacts：[scripts/README.md](scripts/README.md) · [artifacts/README.md](artifacts/README.md)
