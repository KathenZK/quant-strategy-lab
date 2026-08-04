# HYPE-1H-Price-Kinematic-Trend-Survival-Control Core Ledger

## Family Identity

- Full family：`HYPE-1H-Price-Kinematic-Trend-Survival-Control`
- Alias：`HYPE-1H-PKTSC`
- 市场：Binance USD-M perpetual；`HYPE/USDT:USDT`
- 周期：完整 `1h` 轨迹、每 `4h` 决策、目标 `3–14d` campaign
- 机制：纯价格 causal walk-forward 延续概率 + 固定 quantity 风险账本 + 离散加减仓 + 半 MFE 保护
- 边界：不继承 PKC、SDS、MDTP、EMA、Donchian、ATR 或任何已揭示候选参数与状态

## Current State

- 当前版本：无；只有未编号的双门禁统计与仓位控制诊断。
- 状态：`explore / diagnostic-only / not promoted / not live-ready`。
- 延续预测：Long/Short 均失败。Long Full IC 仅 `2/4` 为正且 `24h` 概率顶底组差 `-6.56pp`；Short Full IC `4/4` 为正但顶底组只差 `+1.56pp`。两边四个 horizon 的 Full Brier 全部差于逐次训练基准，bootstrap 区间均跨零。
- 动态控制：Long/Short 均失败。动态标准成本分别 `-3.10%/-2.06%`，差于同路径固定 `35%` 种子仓 `-2.08%/-1.70%`；零成本仍为 `-1.83%/-1.39%`。加减仓非 dormant，但配对增量均为负且区间跨零。
- 行为诊断：37/34 个 campaign 平均仅持有 `12.2h/15.3h`，多数被概率或方向更新退出，未实现 `3–14d`；半 MFE 保护机械正确，但 Long 只有 3 笔达 `2R`、Short 为 0。
- 下一门：停止在已揭示历史上调整概率阈值、窗口或层级；只保留 prospective OOS，或引入 materially new 的非价格外部信息。

## Version Rules

- 统计模型、历史 walk-forward 或控制消融不构成策略版本。
- 只有用户明确要求登记、prospective OOS 与交易执行门禁通过后，才允许创建 `V1`；登记不等于 promotion。
- 改变价格窗口、标签、阈值、层级、风险、退出或模型属于新冻结轮次，不得覆盖本轮。

## Version Table

当前无 registered version。

## Shared Assumptions

- 数据：连续 Binance `15m` 聚合完整 `1h`；信号在闭合小时后、下一小时 open 执行；实际 funding。
- 价格状态：`6h/24h/72h/168h/336h`；过去 `24h` 位移定义方向；每 `4h` 更新。
- 风险：完整计划 `R0=1%` entry equity，灾难上限 `3%`，填单与有效杠杆上限 `3x`；层级 `35/70/85/100%`。
- 成本：fee `0.001/fill`、base adverse slippage `4 bps/fill`、stress `8 bps/fill`。
- Prospective OOS：`[2026-08-02, 2026-11-02 UTC)`，本轮保持未揭示。

## Evidence Map

- Spec：[初始研究合同](specs/hype-1h-pktsc-initial-research-contract-2026-08-03.md)
- Diagnostics：[初始双门禁验证](diagnostics/hype-1h-pktsc-initial-research-2026-08-03.md)
- Scripts / artifacts：[scripts/README.md](scripts/README.md) · [artifacts/README.md](artifacts/README.md)
