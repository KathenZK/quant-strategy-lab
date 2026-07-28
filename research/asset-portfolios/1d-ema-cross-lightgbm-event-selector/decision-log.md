# Decision Log — Binance-1D-EMA-Cross-LightGBM-Event-Selector

## 2026-07-24 家族立项（周期梯度扫描第四点）

- 决策：在 15m/1h/4h 梯度显示毛期望随周期走强、净期望在 1h–4h 间穿零后，立 `1d` 诊断线确认趋势残差是否继续走强或在 4h 见顶。`1d` 数据由已审计 `1h` 归档重采样；96 根超时 = 96 天、暖机 384 天，事件量预期再降一个量级；`2026H1` 为污染 holdout。
- 证据：[4h P1 基线诊断](../4h-ema-cross-lightgbm-event-selector/diagnostics/bin-4h-emax-lgbm-p1-baseline-2026-07-24.md)

## 2026-07-24 P1 基线完成：梯度第四点确认，日线净期望 +0.41 ATR、空头逐年全正

- 决策：`1d` 基线（b4_2）全体净期望 +0.414 ATR（毛 +0.447、成本中位 0.034）；死叉空头交易池 2021–2025 逐年全正、全体空头净 +0.761；周期梯度四点单调，趋势残差未在 4h 见顶。样本量为主要瓶颈（池内 1,484 事件、空头单年 107–198），推进需新契约显式处理小样本、聚簇与逼空尾部。
- 证据：[P1 基线诊断](diagnostics/bin-1d-emax-lgbm-p1-baseline-2026-07-24.md)、[baseline_1d_report.json](artifacts/baseline_1d_report.json)

## 2026-07-27 P2 组合级判定：事件级优势不可收割，判据未过，机制家族关账

- 决策：预注册资金框架下（同 4h P2：10 万、0.5% 风险/笔、20 并发、2× 杠杆；A2 用市场宽度门控）A1/A2 全期仅 +11.9%/+13.4%、2022 利润占比 383%/348%（判据 <70% 决定性未过）、回撤 −35.7%/−35.3%。根因：死叉信号成簇 + 96 天超时导致容量逆向选择（2023–2025 被容量跳过的事件平均 +0.9～+2.1 ATR，实际成交为负），叠加反波动率仓位放大坏信号。1d 为周期梯度最后候选，EMA 交叉机制家族四周期在当前证据下全部关账；重启须预注册变更出场/容量假设的新诊断线。
- 证据：[P2 组合级诊断](diagnostics/bin-1d-emax-lgbm-p2-portfolio-control-a-2026-07-27.md)、[组合级契约](specs/bin-1d-emax-portfolio-contract-2026-07-27.md)、[portfolio_control_a_report.json](artifacts/portfolio_control_a_report.json)

## 2026-07-24 数据修复：基线漏读 legacy 分区，补齐主流币后重跑

- 决策：装载 glob 漏读 1h 湖 `date=*` 旧版按日分区（六个主流币的主存储），基线重跑后全体净 +0.414 → +0.398、池内空头 +0.761 → +0.733，空头逐年仍全正，结论方向不变。首版产物留档 `*_v1_missing_majors.*`；根因与修复详见 4h 家族同日修复条目。
- 证据：[P1 修正记录](diagnostics/bin-1d-emax-lgbm-p1-baseline-2026-07-24.md)
