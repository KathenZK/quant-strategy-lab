# Decision Log — Binance-15M-EMA-Cross-LightGBM-Event-Selector

## 2026-07-29 K 族增补：蜡烛形态三尺度零增量，五族特征测毕

- 决策：按预注册契约补测 18 个蜡烛形态特征（信号 K/日线/周线实体、影线、吞没）。15m 顶桶净 −0.141 与 a2 持平；4h 同步验证为轻微稀释（+0.367 → +0.287）。周线实体/影线进重要性前 15 但与趋势特征（7 天收益、区间位置）冗余。判定：K 族关闭；至此局部形态、多日趋势、量价新表达、衍生品持仓、蜡烛形态五族全部测毕，15m 极限终判不变，4h 正式立项应保持精简特征集。
- 证据：[15m K 族契约](specs/bin-15m-emax-k-candle-supplement-contract-2026-07-29.md)、[双消融诊断 3.9 节](diagnostics/bin-15m-emax-feature-ablation-2026-07-29.md)、[k_supplement_report.json](artifacts/k_candle_supplement/k_supplement_report.json)、[4h K 族报告](../4h-ema-cross-lightgbm-event-selector/artifacts/k_candle_supplement/k_supplement_report.json)

## 2026-07-29 A/F 特征增补：两族新数据零增量，15m 极限终判成立

- 决策：按预注册契约补齐最后两族可行特征——F（量价分布/90d 动量/VWAP，现有 K 线）与 A（OI/多空比，范围化同步 Vision metrics 571 币约 1 亿行，explore 级落 `data/normalized/derivatives_metrics/`）。F 轮顶桶净 −0.144、A 终轮 −0.135，均与 a2（−0.134）噪声带内重合；新特征进入重要性前列但与趋势特征冗余。判定：四族特征给满后 15m 可识别毛优势钉死 ≈+0.17 ATR < 成本墙 0.30+，特征方向对 15m 彻底关闭；按契约后续路径执行 1h/4h 移植（1h 顶桶净转正 +0.030 但 2/4 年正；4h +0.367 四年全正过 Gate B、Gate A 未过），机制线活路移交 4h 家族评估。家族维持 `archived`。
- 证据：[A/F 增补契约](specs/bin-15m-emax-af-feature-supplement-contract-2026-07-29.md)、[双消融诊断 3.7/3.8 节](diagnostics/bin-15m-emax-feature-ablation-2026-07-29.md)、[a_supplement_report.json](artifacts/af_supplement/a_supplement_report.json)、[metrics_sync_report.json](artifacts/af_supplement/metrics_sync_report.json)、[4h 移植诊断](../4h-ema-cross-lightgbm-event-selector/diagnostics/bin-4h-emax-local-trend-selector-2026-07-29.md)

## 2026-07-29 换对消融：EMA30/120 不改判，死因对信号对参数稳健

- 决策：按预注册契约把信号对换成 EMA30/120（其余全部冻结）重测。裸基线毛/净（+0.040/−0.376）与 EMA21/96（+0.041/−0.379）几乎重合，local+trend 打分顶桶净 −0.165 / 毛 +0.140 还略差于 21/96 的 a2（−0.134/+0.167），Gate B 未过。判定：换对关闭，"15m 事件信息量/成本比不足"对 EMA 参数选择稳健；家族维持 `archived`。
- 证据：[换对契约](specs/bin-15m-emax-ema-pair-ablation-contract-2026-07-29.md)、[双消融诊断 3.6 节](diagnostics/bin-15m-emax-feature-ablation-2026-07-29.md)、[ema_pair_report.json](artifacts/ema_pair_ablation/ema_pair_report.json)

## 2026-07-29 增补 a2：补齐多日趋势特征后特征假设最终关闭

- 决策：主消融核对清单发现本币价格特征最长仅 24h 的真实缺口，按增补契约加入 7 个多日趋势特征（7d/30d 动量、30d 区间位置、日线 EMA 状态）重跑局部变体。新特征登顶重要性榜（前 2 名），顶桶净 −0.175 → −0.134、毛 +0.125 → +0.167，但四个 OOF 年仍全负。判定：局部信息给满后可识别优势上限 ≈ 成本墙的 56%，特征假设关闭，死因维持"信息量/成本比"；家族维持 `archived`。
- 证据：[增补契约](specs/bin-15m-emax-feature-ablation-a2-addendum-2026-07-29.md)、[双消融诊断 3.5 节](diagnostics/bin-15m-emax-feature-ablation-2026-07-29.md)、[feature_ablation_a2_report.json](artifacts/feature_ablation/feature_ablation_a2_report.json)

## 2026-07-29 死因复核：特征/标签双消融证伪"特征构造有问题"假设

- 决策：应用户质疑，对归档家族做 2×2 消融（局部形态 vs 全特征 × 绝对 vs 组内相对标签，契约先冻结，2026H1 未触碰）。结果：仅局部特征即可完美排序交叉（十分位 Spearman 1.0，顶桶毛期望 +0.125 ATR、逐年为正），证实"高质量交叉可识别"的直觉；但该优势仅为 0.30 ATR 成本墙的一半，顶桶净 −0.175，四个 OOF 年全负；相对标签使结果进一步恶化，证明唯一超过成本的成分是行情状态。死因维持"信息量/成本比"，非特征表达；家族维持 `archived`。约 +0.1~0.2 ATR 的入场时点改善量级为"日线趋势 × 15m 触发"类新线提供了定量依据。
- 证据：[双消融诊断](diagnostics/bin-15m-emax-feature-ablation-2026-07-29.md)、[消融契约](specs/bin-15m-emax-feature-ablation-contract-2026-07-29.md)、[feature_ablation_report.json](artifacts/feature_ablation/feature_ablation_report.json)

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
