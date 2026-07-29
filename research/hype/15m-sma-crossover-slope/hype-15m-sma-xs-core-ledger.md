# HYPE-15M-SMA-Crossover-Slope Core Ledger

## Family Identity

- Full family name：`HYPE-15M-SMA-Crossover-Slope`
- Alias：`HYPE-15M-SMA-XS`
- Market / exchange / symbol / timeframe：Binance USD-M Futures，`HYPEUSDT` perpetual，`15m`
- Mechanism：`SMA30/SMA120` 交叉在下一根 open 开仓；反向交叉翻仓，或由闭合 K 上的 ATR 归一化斜率转向提前平仓。
- Boundary：这是截图驱动的独立 SMA30/120 简化研究，不是 `HYPE-EMA-X`、`HYPE-EMA-TB` 或任何现有 V35/V18 的版本。

## Current State

- 当前主状态：`explore / not promoted / not live-ready`
- 当前版本：无；只有未编号的交叉基线和斜率退出诊断。
- 冻结的 37 个候选在 prefit train 与 validation 中没有一个同时为正；最不差的参考配置仍为 prefit `-65.15%`、最大回撤 `-71.70%`。
- 锁定最近三个月及截图窗口为正，分别为 `+40.29%` 与 `+13.83%`，但这是已冻结规则的 reused OOS 诊断，不能覆盖 prefit 失败或用于事后晋升。
- 下一决策门：停止调斜率退出。若继续，必须改变入场机制以拒绝震荡假交叉，并重新冻结 prospective OOS；不得用已揭示后三个月挑阈值。

## Version Rules

- 未编号 observation：截图复现、失败基线、斜率定义比较和 prefit 搜索，不构成策略版本。
- V1：只有用户明确要求登记，且入场过滤、退出、成本、风险和执行合同冻结后才创建；登记不代表 promotion。
- 新版本触发：改变 SMA 周期、由交叉即入场改为交叉后确认、加入 regime 过滤或改变重入规则，都需要新的冻结规格。

## Version Table

当前无 registered version。

## Shared Assumptions

- `SMA30/SMA120` 均只使用闭合 `15m` close；信号在下一根 open 成交，单净仓，1x。
- 金叉开多、死叉开空；斜率退出后保持空仓，必须等新的交叉，不在同一 regime 追单。
- Binance 每次 fill fee `0.001` + adverse slippage `4 bps`，另计真实 funding。
- 本轮为用户要求的精确简化机制，不含固定止损；因此不能视为可上线风险合同。
- 数据为 `2025-05-30 10:30 UTC` 至 `2026-07-28 07:45 UTC`；family-local locked OOS 为 `[2026-04-28 08:00, 2026-07-28 08:00 UTC)`，与其他 HYPE 研究重叠，只能称 reused OOS。

## Evidence Map

- 数据冻结：[报告](diagnostics/hype-15m-sma-xs-data-freeze-2026-07-28.md) · [机器清单](artifacts/hype_15m_sma_xs_dataset_freeze.json)
- 首轮报告：[baseline and slope exits](notes/hype-15m-sma-xs-baseline-and-slope-exits-2026-07-28.md)
- 搜索与揭示：[prefit selection](artifacts/hype_15m_sma_xs_prefit_selection.json) · [prefit ranking](artifacts/hype_15m_sma_xs_prefit_ranking.csv) · [one-time reveal](artifacts/hype_15m_sma_xs_one_time_reveal.json)
- 逐笔与状态：[trades](artifacts/hype_15m_sma_xs_selected_trades.csv) · [states](artifacts/hype_15m_sma_xs_selected_states.parquet)
- 实现：[sma_xs_engine.py](scripts/sma_xs_engine.py) · [tests](../../../tests/test_hype_15m_sma_xs.py)
