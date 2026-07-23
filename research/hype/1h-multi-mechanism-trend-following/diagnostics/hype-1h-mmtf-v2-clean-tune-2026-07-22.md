# HYPE-1H-MMTF V2 Clean Surface 调优 — 2026-07-22

## 协议

V2 先通过逐笔 SHA 验证与 V1 exact equal，再只在 12 个有效参数上调优。风险轮 `24,000` 个、信号/风险联合轮 `36,000` 个；共 `60,000` 个 prefit-only 候选。前 `240` 个候选完成 14 个滚动 30d 窗口审计，locked OOS 未加载。

## 结果

- Prefit 目标通过 `0`；validation 代理通过 `132`；联合通过 `0`。
- 冻结 V3：prefit `7.3616x / +497.28% / 19.83% MDD / 88.33% / 60 trades / PF 4.794`。
- 内部 90d validation：`13.8849x / +91.22% / 13.80% / 88.24% / 17 / PF 8.472`。
- 14 个滚动 30d 窗口：正收益 `13/14`、零交易 `0`、交易数中位数 `5.5`、收益中位数 `+20.92%`、最差 `-13.79%`。

V3 胜率、prefit 回撤和 prefit/validation 样本数符合形状门槛，但年化仍未达到 `20x`，因此冻结为 diagnostic version 后进入稳健性与一次性 OOS 审计，不 promotion。

机器证据：[tune JSON](../artifacts/hype_1h_mmtf_v2_clean_tune_2026-07-22.json) · [frontier](../artifacts/hype_1h_mmtf_v2_clean_tune_frontier_2026-07-22.csv) · [rolling audit](../artifacts/hype_1h_mmtf_v2_clean_tune_rolling_2026-07-22.csv)
