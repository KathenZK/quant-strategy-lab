# HYPE-1D-MA7-Machine-Learning-Trend Core Ledger

## Family Identity

- Full family name：`HYPE-1D-MA7-Machine-Learning-Trend`
- Alias：`HYPE-1D-MA7-MLT`
- Market：Binance USD-M `HYPEUSDT` perpetual
- Timeframe：UTC `1d`；来源为可信 `1h` 闭合 K 聚合
- Mechanism：训练集内用 Ridge / 小型 LightGBM 学习不同固定持有期的多空成本后收益；和训练集内冻结的 MA 趋势参数搜索基线进行一次性后段验证。
- Collision warning：本家族不是 `HYPE-1D-MA7-ABT-V7.2`，不继承或改写 V7.1。

## Current State

- 状态：`explore / diagnostic-only / not promoted / not live-ready`
- 当前版本：无 registered version
- 当前实验：P0 365d train / 81d locked validation 已完成，裁决 `ML_NO_EDGE`
- 下一门禁：不得复用已揭示 81 日调参；只有未来新增数据或另立多资产 pooled 合同才可启动 P1。P0 不授权 promotion 或 runner。

## Version Rules

- 特征、标签、模型候选、训练/验证切分、执行或选择规则任一实质变化，均须新合同；不得在已揭示验证集上静默重选。
- P0 是 diagnostic experiment，不自动登记版本。

## Version Table

| 版本/实验 | 状态 | 角色 | 证据 | 决策 |
| --- | --- | --- | --- | --- |
| P0 365d train / locked validation | `ML_NO_EDGE / diagnostic-only / not promoted / not live-ready` | ML 与 train-only MA 参数搜索的公平后段比较 | [冻结合同](specs/hype-1d-ma7-mlt-p0-365d-train-validation-contract-2026-08-27.md) · [结果](diagnostics/hype-1d-ma7-mlt-p0-365d-train-validation-2026-08-27.md) · [机器摘要](artifacts/hype_1d_ma7_mlt_p0_365d_train_validation_2026-08-27_summary.json) | ML validation `-38.64%/-52.87%`，弱于规则 `-2.64%/-30.80%` 与买持 `+0.62%`；不登记版本 |

## Shared Assumptions

- 数据：标准数据湖 Binance HYPEUSDT perpetual `1h`，只保留显式闭合且完整的 24 根小时 K 后聚合 UTC 日 K。
- 成本：单边手续费 `0.001` + 不利滑点 `4 bps`；另计实际 funding。
- 时序：日收盘只读取当前及历史；最早下一 UTC open 成交；固定 `1x`、单仓、不加仓。
- P0 的固定持有期没有盘中止损，只是方向/机会识别诊断，因此始终 `not live-ready`。

## Evidence Map

- [P0 合同](specs/hype-1d-ma7-mlt-p0-365d-train-validation-contract-2026-08-27.md)
- [P0 结果](diagnostics/hype-1d-ma7-mlt-p0-365d-train-validation-2026-08-27.md)
- [研究脚本](scripts/run_hype_1d_ma7_mlt_p0.py)
- [Artifacts 索引](artifacts/README.md)
