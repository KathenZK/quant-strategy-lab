# Binance-1H-Multi-Leg-Six-Asset-Selector Core Ledger

## Family Identity

- Full family name：`Binance-1H-Multi-Leg-Six-Asset-Selector`
- Short id：`BIN-1H-ML6AS`
- Market：Binance USD-M Futures perpetual
- Symbols：`BTCUSDT / ETHUSDT / SOLUSDT / BNBUSDT / TRXUSDT / HYPEUSDT`
- Timeframe：`4h` regime + `1h` signal/execution
- Mechanism：六币三交易臂（趋势回调、突破延续、均值回归），比较独立臂仲裁与币内多腿融合，以及非抢占/抢占两种全局单仓状态机。
- Collision warning：不是 `Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble` 的版本或 observation。

## Current State

- Status：`explore / not promoted / not live-ready`。
- Registered version：无。
- Current gate：数据湖质量门禁已通过；四条预拟合冻结路线均在首次锁定 OOS 揭示中失败，没有可登记策略。
- Promotion boundary：用户当前只要求研究；没有版本登记、runner 交接或 promotion 授权。

## Version Rules

- 数据诊断、搜索失败行和未冻结比较均为 observation，不获得版本号。
- 只有用户明确要求登记/冻结为 `Vx` 时，才把成分臂、参数、评分、仲裁、持仓抢占规则、成本、窗口与证据一起登记。
- 抢占与非抢占状态机若交易路径不同，登记时必须分别冻结身份，不得只用一个模糊版本名覆盖。

## Version Table

当前没有登记版本。

## Shared Assumptions

- 最近三个月按数据集末端锁定为 OOS，任何参数、评分权重、抢占阈值或候选筛选不得读取该窗口结果。
- Binance 成本：手续费 `0.001/fill`、基础滑点 `4 bps/fill`，并计入真实历史 funding；另做 `8 bps/fill` 压力。
- 多空双向，单笔暴露不超过 `3x`；允许空仓。
- 最终硬门槛：full 与 OOS 胜率均 `>=80%`，full trades `>=200`，OOS trades `>=30`，full 与 OOS 最大回撤均严格 `<20%`。

## Evidence Map

- 数据同步与质量审计脚本：[scripts/sync_and_audit_binance_six_asset_1h_data.py](scripts/sync_and_audit_binance_six_asset_1h_data.py)
- 数据质量报告：[diagnostics/binance-six-asset-1h-data-quality-2026-07-14.md](diagnostics/binance-six-asset-1h-data-quality-2026-07-14.md)
- 数据质量产物：[artifacts/binance_six_asset_1h_data_quality_2026-07-14.json](artifacts/binance_six_asset_1h_data_quality_2026-07-14.json)
- 预拟合冻结产物：[artifacts/binance_1h_ml6as_prefit_search_2026-07-14.json](artifacts/binance_1h_ml6as_prefit_search_2026-07-14.json)
- 锁定 OOS 研究报告：[diagnostics/binance-1h-ml6as-prefit-oos-failure-2026-07-14.md](diagnostics/binance-1h-ml6as-prefit-oos-failure-2026-07-14.md)
- 首次揭示产物：[artifacts/binance_1h_ml6as_oos_reveal_2026-07-14.json](artifacts/binance_1h_ml6as_oos_reveal_2026-07-14.json)
- 逐笔交易产物：[artifacts/binance_1h_ml6as_revealed_trades_2026-07-14.csv](artifacts/binance_1h_ml6as_revealed_trades_2026-07-14.csv)
- 失败表面消融：[ablations/binance-1h-ml6as-frozen-surface-ablation-2026-07-14.md](ablations/binance-1h-ml6as-frozen-surface-ablation-2026-07-14.md)
- 后验失败表面产物：[artifacts/binance_1h_ml6as_failure_surface_2026-07-14.json](artifacts/binance_1h_ml6as_failure_surface_2026-07-14.json)

## 2026-07-14 Locked OOS Observation

- 首次揭示前冻结 SHA-256：`cc02c1228b8232338bd0280263b7079635a6ad0815aab1c80af4c6f2b32e6c6d`。
- 预拟合搜索：`72,000` 组单臂参数试验；四条冻结路线预拟合胜率 `83.49%–85.07%`、回撤 `16.89%`。
- 锁定 OOS：四条路线交易数 `94–99`，胜率 `53.19%–54.55%`，收益 `-28.78%–-37.84%`，回撤 `33.32%–38.63%`。
- 后验诊断：`5,200` 组账户路由和 `126` 组单单元局部扰动均无 OOS 胜率 `>=80%` 或 OOS 正收益行。
- 结论：不登记版本，不生成 live spec，不向 runner 交接；已揭示 OOS 不再用于候选选择。
