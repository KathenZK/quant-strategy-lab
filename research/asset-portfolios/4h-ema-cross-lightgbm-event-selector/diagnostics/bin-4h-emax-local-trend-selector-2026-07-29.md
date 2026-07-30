# BIN-4H-EMAX 局部+趋势选择器移植诊断（2026-07-29）

- 契约：[`bin-4h-emax-local-trend-selector-contract-2026-07-29.md`](../specs/bin-4h-emax-local-trend-selector-contract-2026-07-29.md)；脚本：[`research_local_trend_selector.py`](../scripts/research_local_trend_selector.py)；产物：[`local_trend_selector_report.json`](../artifacts/local_trend_selector/local_trend_selector_report.json)。
- 与已失败的 [V2 打分层](bin-4h-emax-lgbm-v2-scoring-2026-07-24.md)的区别：V2 喂行情态/市场特征（OOS 秩相关塌方，判定为行情记忆）；本移植只喂局部形态 + 本币多日趋势（15m a2 特征集），事件与成本模型不变（15,413 个 pool 事件，成本均值 0.093 ATR）。

## 结果（B4_2 净 ATR，OOF 2022–2025，purge 17 天）

- 十分位（1→10）：+0.087、−0.073、+0.111、−0.006、+0.118、+0.010、+0.103、+0.055、+0.203、**+0.367**；Spearman 0.564（**Gate A 未过**：中间桶乱序，每桶每年仅约 385 个事件，噪声主导）。
- 顶桶：净 **+0.367**（毛 +0.467，成本 0.094），1,229 事件，多头占 45%；逐年 2022 +0.707、2023 +0.051、2024 +0.593、2025 +0.085 → **4/4 年为正，Gate B 首次通过**。
- 重要性前列：`d1_price_to_slow`、`ret_30d`、`d1_gap_atr`、`ret_7d`（全部为多日趋势族）。

## 跨周期标度表（同一选择器、同一特征集）

| 刻度 | 顶桶净 ATR | 顶桶毛 ATR | 成本均值 | Gate A / B |
|---|---|---|---|---|
| 15m（a2） | −0.134 | +0.167 | 0.420 | 过 / 不过 |
| 1h | +0.030 | +0.219 | 0.197 | 过 / 不过 |
| 4h | **+0.367** | +0.467 | 0.093 | 不过 / **过** |

## 增补：K 族蜡烛形态（同日）

按 [4h K 族契约](../specs/bin-4h-emax-k-candle-supplement-contract-2026-07-29.md)在 local+trend 之上加 18 个蜡烛形态特征（[`research_k_candle_supplement.py`](../scripts/research_k_candle_supplement.py)、[`k_supplement_report.json`](../artifacts/k_candle_supplement/k_supplement_report.json)）：顶桶净 +0.287（基准 +0.367），2023 年翻负（−0.055），Spearman 0.636。判定：K 族在 4h 为**轻微稀释**——62 个特征对 1.5 万事件噪声占优；后续 4h 正式立项应保持 local+trend 的精简特征集，不纳入 K 族。

## 判定与边界

- 预注册双门未全过（Gate A 失败），按契约不改家族状态，维持 `archived`；不得据此直接推进组合回测或 promotion。
- 但这是该机制线首个"顶桶四年全正且大幅越过成本墙"的 OOF 证据，且驱动特征是本币多日趋势（趋势末端/趋势健康度），不是行情态记忆；与 V2 的失败模式（喂市场特征、秩相关塌方）形成对照。
- 已知边界：顶桶事件仅 1,229 个（年均 ~300），单事件期望不等于组合可变现收益；4h 家族此前的组合级回测（对照组 A）曾因回撤超限失败，任何推进都必须重走组合级验证与逼空月分析。
- 后续若立项：应新开正式研究契约（含组合级资金约束回测、并发、2026H1 之后的前瞻 OOS），不得复用本诊断作为晋升证据。
