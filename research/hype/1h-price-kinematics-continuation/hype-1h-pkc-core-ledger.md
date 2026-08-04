# HYPE-1H-Price-Kinematics-Continuation Core Ledger

## Family Identity

- Full family：`HYPE-1H-Price-Kinematics-Continuation`
- Alias：`HYPE-1H-PKC`
- 市场：Binance USD-M perpetual；`HYPE/USDT:USDT`
- 周期：完整 `1h` 轨迹、固定 `4h` 观察锚点、未来 `3d/7d/14d` 标签
- 机制：只用对数价格变化的位移、速度、加速度、路径长度、一致性、脉冲集中度与粗糙度验证趋势延续
- 边界：独立于 `HYPE-15M-SDS`、`HYPE-15M-MDTP`、EMA、Donchian、breakout 与任何交易状态机

## Current State

- 当前版本：无；只有未编号的统计诊断。
- 状态：`explore / diagnostic-only / not promoted / not live-ready`。
- 初始验证：Long/Short 均为 `kinematic-evidence-supported = false`；两个方向都没有任何结构量在至少两个未来尺度上获得 expected-sign block-bootstrap 支持，且 Train OOF 与 Validation Full Ridge IC 只有 `1/3` horizon 同号。
- 关键观察：Train 偏向下跌延续，Validation 偏向上涨延续；市场阶段方向漂移压过局部 `6h/24h/72h` 运动学关系。
- 下一门：不得用已揭示 Validation 挑选 Short `7d/14d` 或增加窗口；只有 materially new、事前冻结的纯价格表示与新的 prospective OOS 才能继续。

## Version Rules

- 统计观察、相图或失败假设不构成版本。
- 只有用户明确要求登记、且交易逻辑另行冻结后，才允许创建策略 `V1`；研究关系成立不等于 promotion。
- 改变观察频率、过去窗口、未来标签、方向定义或模型属于新冻结研究轮次，不得覆盖本轮。

## Version Table

当前无 registered version。

## Shared Assumptions

- 只使用完整闭合 `1h` 价格轨迹；`1h` 由无缺口的 Binance `15m` K 聚合。
- 主观察锚点为每个 UTC `00/04/08/12/16/20` 时点；其余三个小时相位只作冻结敏感性审计。
- 过去窗口固定为 `6h/24h/72h`，未来标签固定为 `72h/168h/336h`。
- 历史 Validation 不用于改公式、阈值或模型；prospective OOS 锚点窗口锁定为 `[2026-08-02, 2026-11-02 UTC)`。

## Evidence Map

- [冻结研究合同](specs/hype-1h-pkc-initial-research-contract-2026-08-02.md)
- [初始验证报告](diagnostics/hype-1h-pkc-initial-research-2026-08-02.md)
- [decision-log.md](decision-log.md)
- [scripts/README.md](scripts/README.md)
- [artifacts/README.md](artifacts/README.md)
