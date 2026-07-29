# HYPE-15M-Sequential-Drift-State Core Ledger

## Family Identity

- Full family name：`HYPE-15M-Sequential-Drift-State`
- Alias：`HYPE-15M-SDS`
- Market / exchange / symbol / timeframe：Binance USD-M Futures，`HYPEUSDT` perpetual，`15m`
- Mechanism：每根闭合 K 线更新趋势证据，以迟滞状态机维护 `flat / long / short`；状态变化在下一根 open 执行，持仓期间继续逐 K 判断趋势持续、衰减或反转。
- Boundary：不继承 `HYPE-EMA-TB`、`HYPE-EMA-X`、`HYPE-15M-MMTF` 或 `HYPE-15M-MHEF` 的身份、参数、状态和结论。

## Current State

- 当前主状态：`explore / not promoted / not live-ready`
- 当前版本：无；只有未编号的顺序漂移、回归、breakout-retest 和 Kalman/CUSUM/结构确认诊断。
- 首轮顺序漂移基线在 prefit、锁定后三个月和 full 均为负，且零成本 prefit 仍为负，未达到进入消融的最低研究门槛。
- 第二轮回归趋势状态搜索严格不加载已揭示后三个月；432 个配置中没有一个在满足样本量约束时同时做到 train 和 validation 正收益。
- 第三轮 breakout-retest campaign 同样只读 prefit；384 个配置中有 288 个满足样本量，但 train/validation 同时正收益为 0。
- 第四轮按用户要求测试 causal Kalman + Page CUSUM + Donchian/efficiency 结构状态机；384 个 prefit 配置全部满足样本量，但 train、validation 单段正收益数也均为 0。最不差参考 prefit `-15.36%`，零成本仍为 `-0.70%`。
- 对第四轮最不差失败参考完成 21 个 active 参数、85 个 one-at-a-time 变体的全消融；validation 正收益仍为 0。`max_hold_bars` 全范围 dormant，杠杆只缩放盈亏；严格入场/晚退出只能让 train 转正，validation 继续为负。
- 下一决策门：停止当前四个纯 OHLCV 15m 搜索表面。只有加入 materially new 的真实细粒度执行/订单流信息，或在 `2026-07-28 08:00 UTC` 后积累足够 prospective OOS，才值得重开；不得重用已揭示窗口调参。

## Version Rules

- 未编号 observation：探索机制、失败基线或未达到样本量的候选，不构成策略版本。
- V1：只有用户明确要求登记，且机制、参数、成本、数据范围和执行合同冻结后才创建；登记不代表 promotion。
- Vx.y：同一状态估计与成交路径下的可逐笔对账的小修；更换趋势估计器或入场状态机属于新主版本或新家族评估。

## Version Table

当前无 registered version。

## Shared Assumptions

- 只用闭合 `15m` K 计算状态，下一根 open 执行；单净仓，不重叠。
- Binance 成本：每次 fill fee `0.001` + adverse slippage `4 bps`，另计真实 funding。
- 紧急保护止损按固定 entry ATR，gap 穿越按 bar open；止损后同一趋势 episode 不允许机械重入，必须先离开原状态。
- 数据窗口：`2025-05-30 10:30 UTC` 至 `2026-07-28 07:45 UTC`；首轮 family-local locked OOS 为 `[2026-04-28 08:00, 2026-07-28 08:00 UTC)`，但与其他 HYPE 研究重叠，只能称 reused OOS。

## Evidence Map

- 数据冻结：[报告](diagnostics/hype-15m-sds-data-freeze-2026-07-28.md) · [机器清单](artifacts/hype_15m_sds_dataset_freeze.json)
- 基线与 prefit 搜索：[报告](notes/hype-15m-sds-baseline-and-prefit-search-2026-07-28.md)
- 基线产物：[summary](artifacts/hype_15m_sds_baseline_summary.json) · [cost diagnostic](artifacts/hype_15m_sds_baseline_cost_diagnostic.json) · [trades](artifacts/hype_15m_sds_baseline_trades.csv) · [states](artifacts/hype_15m_sds_baseline_states.parquet)
- 回归搜索产物：[summary](artifacts/hype_15m_sds_regression_prefit_search.json) · [ranking](artifacts/hype_15m_sds_regression_prefit_ranking.csv)
- 回踩重测产物：[summary](artifacts/hype_15m_sds_breakout_retest_prefit_search.json) · [ranking](artifacts/hype_15m_sds_breakout_retest_prefit_ranking.csv)
- Kalman/CUSUM/结构确认：[报告](notes/hype-15m-sds-kalman-cusum-structure-2026-07-28.md) · [contract](artifacts/hype_15m_sds_kcs_prefit_contract.json) · [summary](artifacts/hype_15m_sds_kcs_prefit_search.json) · [ranking](artifacts/hype_15m_sds_kcs_prefit_ranking.csv)
- KCS 全参数消融：[报告](ablations/hype-15m-sds-kcs-full-parameter-ablation-2026-07-28.md) · [contract](artifacts/hype_15m_sds_kcs_full_ablation_contract.json) · [results](artifacts/hype_15m_sds_kcs_full_ablation.csv) · [summary](artifacts/hype_15m_sds_kcs_full_ablation_summary.json)
- 实现：[sds_engine.py](scripts/sds_engine.py) · [KCS script](scripts/research_hype_15m_sds_kalman_cusum_structure.py) · [tests](../../../tests/test_hype_15m_sds.py) · [KCS tests](../../../tests/test_hype_15m_sds_kcs.py)
