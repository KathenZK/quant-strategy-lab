# Decision Log — Binance-4H-EMA-Cross-LightGBM-Event-Selector

## 2026-07-24 家族立项（周期梯度扫描第三点）

- 决策：在 `1h` 基线显示毛期望随周期放大走强（15m ~0 → 1h +0.12 ATR）后，立 `4h` 独立诊断线验证趋势残差的周期梯度。全市场 `4h` 数据由已审计 `1h` Vision 归档重采样（无独立 4h 归档）；`2026H1` 为污染 holdout，裁决只能取前瞻窗口。首个 kill test 为 P1 基线毛/净期望。
- 证据：[1h P1 基线诊断](../1h-ema-cross-lightgbm-event-selector/diagnostics/bin-1h-emax-lgbm-p1-baseline-2026-07-24.md)

## 2026-07-24 P1 基线完成：净期望首次转正，周期梯度确认

- 决策：`4h` 基线（b4_2）全体事件扣全成本净期望 +0.065 ATR，为三个周期中首个转正；成本中位再减半至 0.083 ATR；死叉空头全期净 +0.253、2024/2025 各约 +0.31/+0.34（各约 4 SE，不依赖 2022 单年）；多头跨三周期一致不可靠。周期梯度（毛期望随周期升、成本随周期降、净期望在 1h–4h 间穿零）确认。事件量每侧 ~1.1 万，低于 15m 契约样本门槛，推进建模需在新契约中显式处理。
- 证据：[P1 基线诊断](diagnostics/bin-4h-emax-lgbm-p1-baseline-2026-07-24.md)、[baseline_4h_report.json](artifacts/baseline_4h_report.json)

## 2026-07-24 数据修复：三个梯度基线漏读 legacy 分区，主流币补齐后重跑

- 决策：发现 1h/4h/1d 三条基线的装载 glob 漏读 1h 湖 `date=*` 旧版按日分区，导致 BTC（2023-05 起）、ETH/SOL/BNB/TRX（2024-07 起）、HYPE（2025-05 起）缺失；根因是月度同步的 `remove_legacy_overlap` 把这些键从月度分区剔除、`date=*` 才是主存储，而脚本注释误判其为冗余。修复 glob 后三条基线全量重跑，所有结论方向不变（4h 池空头逐年净期望变化 ≤0.011 ATR）；15m 家族不受影响。首版产物一律留档 `*_v1_missing_majors.*`。
- 证据：[修正后 P1 诊断](diagnostics/bin-4h-emax-lgbm-p1-baseline-2026-07-24.md)（修正记录）、[baseline_4h_report.json](artifacts/baseline_4h_report.json)

## 2026-07-24 P2 对照组 A 组合级回测：预注册回撤判据未过，裸信号形态不可推进

- 决策：按预注册契约跑对照组 A 两变体（A1 未门控 / A2 BTC 日线 EMA96 门控）。A1 全期 +543%（CAGR 38.2%）但最大回撤 −54.3%；A2 回撤 −40.7% 且利润 114% 依赖 2022、2024/2025 山寨熊利润全部丢失；门控方向有效性在 2021 得到验证（−35.1% → +62.0%）。裁决：两变体均触发"回撤 <40%"红线，**裸信号 + 固定风险预算形态不可推进**；按契约进入 V2 打分层（机制研究），目标是压回撤同时保住山寨空头利润。
- 证据：[P2 组合级诊断](diagnostics/bin-4h-emax-lgbm-p2-portfolio-control-a-2026-07-24.md)、[组合契约](specs/bin-4h-emax-portfolio-contract-2026-07-24.md)、[portfolio_control_a_report.json](artifacts/portfolio_control_a_report.json)

## 2026-07-24 V2 打分层验证失败：LightGBM 无法跨年识别死叉质量

- 决策：按预注册契约训练三分类 LightGBM 打分层（扩窗逐年 purged CV）。OOF 秩相关全期 −0.136（要求为正）、可用四年仅一年为正；训练集内 +0.62 vs OOF −0.14，增益 Top10 几乎全为行情状态特征——与 15m P5 尸检同构：**模型学的是行情状态而非交叉质量，且该映射不跨年迁移**。叠加组合回撤 −49.1% 仍未过 40% 红线（其 2021 零交易为退化折伪影）。裁决：核心设想在 4h + 当前特征集下不成立，家族维持 `explore / not promoted / not live-ready`，不注册版本；重启条件（换标签/换特征域/改做显式状态门控）已写入诊断。
- 证据：[V2 打分层诊断](diagnostics/bin-4h-emax-lgbm-v2-scoring-2026-07-24.md)、[V2 契约](specs/bin-4h-emax-v2-scoring-contract-2026-07-24.md)、[v2_training_report.json](artifacts/v2_training_report.json)、[v2_portfolio_report.json](artifacts/v2_portfolio_report.json)
