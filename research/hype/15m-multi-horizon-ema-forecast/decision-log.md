# HYPE-15M-Multi-Horizon-EMA-Forecast Decision Log

## 2026-07-14

保留首轮多参数 EMA forecast 为未编号 `explore` 基线，不登记版本、不推进 promotion：全区间毛收益已为负，手续费和高换手进一步放大亏损。证据见 [基线回测](notes/hype-15m-mhef-baseline-backtest-2026-07-14.md)。

## 2026-07-28

按“多周期趋势分数 → 波动率归一化 → 连续目标仓位 → 趋势增强加仓 → 趋势转弱减仓 → 成本感知无交易区”冻结 V2 observation。完成 `17` 组组件消融、`45` 组逐参数敏感性、`432` 组信号组合和 `480` 组执行组合；冻结候选在 train/tune 净收益 `+10.42% / +5.88%`，但一次性 prefit validation 毛收益 `-9.20%`、净收益 `-11.47%`，零成本 `-9.09%`。判 `NO-GO`，不登记版本、不根据已揭示验证救参数、不读取复用 OOS 选优。证据见 [V2 研究报告](notes/hype-15m-mhef-v2-continuous-target-research-2026-07-28.md)。

同日按用户要求，以冻结候选为中心再做 `71` 组 development-only 全参数消融。仅 `zero-cost` 和改变早期 warmup 的 `calibration_min_bars=2048` 表面上两段不差于 reference，均不是可执行 alpha 改进；`max_position_step≥0.25` 逐 K 路径相同，证明该 slot dormant。优化方向升级为 partial-adjustment aim、非对称入/退出迟滞、风险与成本统一门、multi-fold walk-forward；不得把本轮诊断解释为 validation 后重选候选。证据见 [候选中心消融](notes/hype-15m-mhef-v2-candidate-centered-ablation-2026-07-28.md)。
