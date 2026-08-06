# Binance-15M-EMA-Cross-LightGBM-Event-Selector

- 完整家族名：`Binance-15M-EMA-Cross-LightGBM-Event-Selector`
- 别名：`BIN-15M-EMAX-LGBM`
- 市场：Binance USD-M、USDT perpetual、point-in-time 动态全市场币池、`15m`
- 机制：已闭合 `15m` K 线上 `EMA21/EMA96` 交叉产生方向事件（金叉只做多、死叉只做空），LightGBM 三分类（先止盈/先止损/超时）对事件质量打分，组合层只交易高分事件；固定 ATR bracket + 96 根超时出场。
- 防串线：不是 [`BIN-1H-CSLGBM`](../1h-cross-sectional-lightgbm-selector/README.md)、[`BIN-1H-MHCSML`](../1h-multi-horizon-cross-sectional-ml-allocator/README.md) 或 [`HYPE-15M-FML`](../../hype/15m-factor-ml/README.md) 的版本增量；事件驱动 + bracket 出场，非定时调仓；HYPE 零样本表现只是辅助观察，不是本家族的主目标。

## 当前状态

- 状态：`archived`（2026-07-24 锁定 OOS 揭示 `HARD-GATE-FAILED`，按预注册规则归档）
- 未注册任何版本；身份与终局裁决见 [binance-15m-emax-lgbm-core-ledger.md](binance-15m-emax-lgbm-core-ledger.md)。失败机理：校准分数分布 OOS 整体下移，τ 之上事件近零——与 `HYPE-15M-FML` 同型死法。
- 已揭示窗口 `2026-01`–`2026-06` 不得用于本机制再调参；重开视同新研究线，须声明改变了什么假设。

## 入口

- 主账：[binance-15m-emax-lgbm-core-ledger.md](binance-15m-emax-lgbm-core-ledger.md)
- 裁决报告：[P5 锁定 OOS 揭示诊断](diagnostics/bin-15m-emax-lgbm-p5-locked-oos-reveal-2026-07-24.md)
- 死因复核（2026-07-29）：[特征/标签双消融诊断](diagnostics/bin-15m-emax-feature-ablation-2026-07-29.md)——局部形态信息真实（毛 +0.13 ATR）但仅为成本一半，"特征构造有问题"假设按预注册判据不成立
- 冻结研究契约：[bin-15m-emax-lgbm-research-contract-2026-07-23.md](specs/bin-15m-emax-lgbm-research-contract-2026-07-23.md)
- 决策日志：[decision-log.md](decision-log.md)
- 脚本：[scripts/README.md](scripts/README.md)；产物：[artifacts/README.md](artifacts/README.md)
