# HYPE 1D MA7 MLT P7：跨资产 survival-only 覆盖合同

## 1. 研究问题

P7 是 P6 之后的新诊断实验，不修改 P6，也不修改冻结的 `HYPE-1D-MA7-ABT-V7.1`。P6 已证明：在同一 365 日 HYPE 样本上同时学习补入、存活和反手，会把事后趋势路径记住，时间外推接近随机。

P7 只回答一个更窄的问题：用 BTC/ETH/BNB/SOL 的同定义 MA7 root 存活标签训练一个 `SURVIVAL_3D` 头，再把冻结概率覆盖到 HYPE 的 exact V7.1 非保护性日线退出上，能否在不新增交易的前提下提高持有效率。

本轮明确不做：

- 补入 / supplemental entry
- 直接反手
- 新特征、新阈值、新模型搜索
- 把 HYPE 价格放入训练池
- 读取 HYPE 后 81 日，除非开发门禁全部通过

## 2. 数据隔离

- 供体资产：Binance USD-M `BTCUSDT`、`ETHUSDT`、`BNBUSDT`、`SOLUSDT` perpetual。
- 供体 1h 来源：2026-08-28 刷新的两年闭合 K 线 artifacts（`research/{btc,eth,bnb,sol}/1h-adaptive-regime/artifacts/*_binance_1h_closed_klines_2y.parquet`）；物理截断 `ts <= 2026-05-31 00:00 UTC`。不混入更早的湖内分区。
- 供体日 K：只保留显式闭合且完整的 24 根小时 K 后聚合的 UTC 日；资金费率同步截断。
- HYPE 开发上下文仍只加载前 365 个完整 UTC 日：特征日 `2025-05-31` 至 `2026-05-30`，终点开盘 `2026-05-31 00:00 UTC`。
- HYPE reused holdout 终点冻结为 `2026-08-20 00:00 UTC`（81 个完整日）。即使数据湖此后又多出完整日，也不得并入本轮 holdout。
- HYPE 后 81 日 reused holdout 保持锁定，直到门禁通过。
- 训练标签的未来 3 日只进入 `y`；边界处不完整样本必须 censor。
- 日历 OOF 与内部确认拟合都不得使用 `2026-03-12` 及之后的供体日（与 HYPE 前 285 / 后 80 日边界对齐），并额外 purge 3 日。
- 完整供体拟合（截止训练终点）只用于报告 HYPE 365 日迁移覆盖，不参与门禁。

## 3. 标签、特征与模型

- 标签沿用 P6 `SURVIVAL_3D`：当前 stable direction 与 raw-cross root 同向，且未来 3 日至少 2 日仍同向则为 1。
- 特征冻结为 P6 survival 的 36 项：P5 `B1_ROOT_PATH` 23 项 + 6 个穿越/root 描述 + 7 个持仓生命周期特征。
- 模型冻结为 P6 ExtraTrees：600 棵树，`max_depth=5`，`min_samples_leaf=6`，`max_features=0.75`，类别平衡，随机种子 `20260828`。
- 不搜索特征块、阈值、树深或持有天数。

## 4. 冻结交易策略

- exact V7.1 的入场、方向、1.0x 和小时级 protective stop 保持不变。
- 只有 `long_mfe_fraction_trail_exit`、`ma7_slope_exit`、`short_rsi_take_profit`、`max_hold` 且退出发生在 UTC 00:00 的交易可由 survival 考虑延长。
- 原退出前一日 `P(survival_3d) >= 0.60` 才启动延长。
- 延长后，连续两日概率 `< 0.35`、出现反向 root、到达下一笔 V7.1 入场或样本终点时退出。
- 不得取消或延长 protective stop。

## 5. 成本、回放与 OOF

- HYPE 覆盖与 V7.1 均使用 1.0x、单仓、手续费 `0.001`、不利滑点 `4 bps` 和实际 funding。
- 供体 OOF 为日历扩展窗，测试区间：
  - `[2025-10-03, 2025-11-12)`
  - `[2025-11-12, 2025-12-22)`
  - `[2025-12-22, 2026-01-31)`
  - `[2026-01-31, 2026-03-12)`
- 每折只能使用测试起点前且额外 purge 3 日的供体样本。
- 报告供体总体 OOF 与分资产 OOF；分资产 OOF 不得用于选择。

## 6. 开发门禁

只有以下条件全部满足，才允许读取 HYPE 后 81 日：

1. 供体合并 OOF AUC `>= 0.60`；
2. HYPE 最后 80 日内部确认净收益严格高于同期 V7.1；
3. 内部确认按天趋势覆盖不低于 V7.1；
4. 内部确认 1h MDD 不比 V7.1 恶化超过 2 个百分点；
5. 内部确认交易数等于 V7.1（本轮禁止新增交易）。

门禁失败状态为 `DEVELOPMENT_FAILED_HOLDOUT_LOCKED`。门禁通过后若 reused holdout 未同时提高净收益和趋势覆盖，裁决 `V7_1_NOT_BEATEN`；若同时提高且 MDD 不恶化超过 2 个百分点，裁决 `EDUCATIONAL_REUSED_HOLDOUT_WIN`。

无论结果如何，P7 都是 `diagnostic-only / not promoted / not live-ready`。
