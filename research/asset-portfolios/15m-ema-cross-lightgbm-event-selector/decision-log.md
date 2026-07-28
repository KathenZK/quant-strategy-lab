# Decision Log — Binance-15M-EMA-Cross-LightGBM-Event-Selector

## 2026-07-23 家族立项与研究契约冻结

- 决策：新建全市场 `15m` EMA21/96 交叉事件 + LightGBM 事件质量选择器家族，冻结研究契约（信号定义、成本模型、数据窗、锁定 OOS `2026-01-01`–`2026-06-30 UTC`、bracket 预注册规则、阶段 kill gate）。EMA 参数不搜索；bracket 从预注册候选 `{TP2/SL1, TP3/SL1.5, TP4/SL2}` 中只按标签分布指标（不看收益）选定。
- 证据：[冻结研究契约](specs/bin-15m-emax-lgbm-research-contract-2026-07-23.md)

## 2026-07-24 P0 数据基建完成，未触发 kill gate

- 决策：790 合约 `15m` Vision 归档全量落湖并通过冻结审计（零重复键、零 OHLC 违规），遗留日分区零改动（HYPE 15m 分区已被 MMTF 按 SHA256 冻结）；`XMR_USDT_USDT` 非标准导入与代币化股票精简 schema 文件记为已知异常，由币池规则自动排除。数据可用于研究面。
- 证据：[P0 数据冻结诊断](diagnostics/bin-15m-emax-lgbm-p0-data-freeze-2026-07-24.md)

## 2026-07-24 Bracket 预注册选择：冻结 TP4/SL2

- 决策：按预注册规则（只看标签分布，不看收益）从 `{TP2/SL1, TP3/SL1.5, TP4/SL2}` 中选定 `TP4/SL2`。三组候选超时占比均远低于 1/3（0.04%/0.58%/2.97%）且最小类占比均 <15%，触发后备分支"超时占比最接近 1/3"，机械选出最宽一组。P1 各 kill gate 全部通过（每侧事件 21.3 万 ≥5 万；交易池成本 >0.8 ATR 占比 6.5% <50%；净结果离散度 2.83 ATR）。
- 证据：[baseline_a_report.json](artifacts/baseline_a_report.json)、[P1 基线诊断](diagnostics/bin-15m-emax-lgbm-p1-baseline-2026-07-24.md)

## 2026-07-24 P2/P3 完成：阈值口径高分组通过，decile 口径多头不达标

- 决策：60 特征数据集与两套 walk-forward LightGBM 完成；`score>0.75` 高分组 OOF 净期望 5/5 折为正（+0.25 ATR），P3 按组合层交易口径判通过并进入 P4；HYPE 零样本留币测试失败与高分事件密度逐折收缩记为风险。
- 证据：[P2/P3 诊断](diagnostics/bin-15m-emax-lgbm-p2-p3-model-2026-07-24.md)

## 2026-07-24 P4 组合级回测通过，冻结 τ=0.75

- 决策：τ 在折 1–4 选定 0.75，确认折（2025）132 笔 +13.0%、PF 1.38、DD 5.8%、1.5x 成本 +11.2%、远优于基线 A（−223%）；P4 gate 通过，进入 P5 冻结与锁定 OOS 一次性揭示。
- 证据：[P4 诊断](diagnostics/bin-15m-emax-lgbm-p4-portfolio-2026-07-24.md)、[portfolio_report.json](artifacts/model_v1/portfolio_report.json)

## 2026-07-24 P5 锁定 OOS 揭示 HARD-GATE-FAILED，研究线归档

- 决策：一次性揭示 `2026-01`–`2026-06` 锁定 OOS，冻结候选半年仅 4 笔交易（净收益 −1.62%、PF 0、全败），6 项硬门槛 4 项失败，判定 `HARD-GATE-FAILED`。失败机理为校准分数分布 OOS 整体下移（多头 τ 之上事件归零），即契约预警的 FML 式死法。按预注册规则研究线归档（`archived`）：不注册版本、V2/V3 不开工、P6 前瞻观察不挂、已揭示窗口不得用于再调参。
- 证据：[P5 揭示诊断](diagnostics/bin-15m-emax-lgbm-p5-locked-oos-reveal-2026-07-24.md)、[locked_oos_reveal.json](artifacts/model_v1/locked_oos_reveal.json)、[oos_score_drift.json](artifacts/model_v1/oos_score_drift.json)
