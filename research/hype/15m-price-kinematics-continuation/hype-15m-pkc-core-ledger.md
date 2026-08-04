# HYPE-15M-Price-Kinematics-Continuation Core Ledger

## Family Identity

- Full family：`HYPE-15M-Price-Kinematics-Continuation`
- Alias：`HYPE-15M-PKC`
- 市场：Binance USD-M perpetual；`HYPE/USDT:USDT`
- 周期：完整 `15m` 轨迹、每小时主锚点、未来 `1h/3h/6h/12h` 标签
- 机制：只用对数价格的位移、速度、加速度、路径一致性、脉冲集中度和粗糙度验证数小时趋势延续
- 边界：独立于 `HYPE-1H-PKC`、`HYPE-15M-SDS`、传统指标、breakout 和交易状态机

## Current State

- 当前版本：无；只有未编号统计诊断。
- 状态：`explore / diagnostic-only / not promoted / not live-ready`。
- 初始验证：Long/Short 均为 `short-horizon-kinematic-evidence-supported = false`；Full Ridge IC 在 Train 与 Validation 两方向都为 `0/4` horizon 同号，Logit 无一个方向/horizon 通过联合 AUC/Brier 门槛。
- 唯一局部线索：Long 的高脉冲集中度对未来 `3h/6h` 不利，但没有跨足够结构量和 horizon，不能形成策略。
- 下一门：不得从已揭示 Validation 挑 Long、`6h/12h` 或 burst；只有 materially new 合同与 fresh prospective OOS 才能继续。

## Version Rules

- 统计观察和相图不构成版本；研究关系成立也不等于策略或 promotion。
- 改变过去/未来窗口、方向定义、锚点相位或模型属于新的冻结研究轮次。
- 只有用户明确要求登记、且交易逻辑另行冻结后，才允许创建策略 `V1`。

## Version Table

当前无 registered version。

## Shared Assumptions

- 只使用闭合 `15m` 价格；bar open timestamp 加 `15m` 后才视为可见。
- 过去窗口固定 `4/12/24` bars，未来标签固定 `4/12/24/48` bars；方向为过去 `12` bars 位移符号。
- 主锚点为每小时 `:00`，`:15/:30/:45` 只作冻结相位敏感性。
- Prospective OOS 锚点锁定为 `[2026-08-02, 2026-11-02 UTC)`。

## Evidence Map

- [冻结研究合同](specs/hype-15m-pkc-initial-research-contract-2026-08-02.md)
- [初始验证报告](diagnostics/hype-15m-pkc-initial-research-2026-08-02.md)
- [decision-log.md](decision-log.md)
- [scripts/README.md](scripts/README.md)
- [artifacts/README.md](artifacts/README.md)
