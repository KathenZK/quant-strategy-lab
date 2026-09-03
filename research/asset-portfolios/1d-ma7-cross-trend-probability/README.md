# Binance-1D-MA7-Cross-Trend-Probability

- Alias：`BIN-1D-MA7-CTP`
- 市场/周期：Binance USD-M 永续完整 UTC 日K。
- 机制：收盘严格穿越 SMA7 后，判断下一 UTC open 起 20 日是否先到顺向 `+2 ATR` 而非逆向 `-1 ATR`。
- 边界：不是 `BIN-1D-CATL` 一般 asset-day 模型，不是 `BIN-1D-TPSA` / `BIN-1D-MA7-RC` / HYPE P0-P8；本轮封存 `HYPE/USDT:USDT`，保留 `HYPER/USDT:USDT`。
- 当前状态：`explore / diagnostic-only / not promoted / not live-ready`；P5 裁决 `NO_NEW_INCREMENT_B0_REMAINS_REFERENCE`，RSI6/完整周线与 G3 删除在 2025+ 复用验证集未形成统计确认增量；P4 裁决 `FULL_B0_REMAINS_REFERENCE`，两个预注册压缩模型未通过全部非劣门槛；P3R 裁决 `SUGGESTIVE_CONTEXT_INCREMENT_ONLY`；P2 裁决 `SIGNAL_EXPLAINED_BY_MA7_CORE`。

## 入口

- [主账](binance-1d-ma7-ctp-core-ledger.md)
- [决策记录](decision-log.md)
- [P0 冻结口径](specs/binance-1d-ma7-cross-trend-probability-contract-2026-08-31.md)
- [P1 冻结合同](specs/binance-1d-ma7-ctp-p1-cross-conditioned-entry-model-contract-2026-09-01.md)
- [P1 报告](diagnostics/binance-1d-ma7-ctp-p1-cross-conditioned-entry-model-2026-09-01.md)
- [P1 审计](diagnostics/binance-1d-ma7-ctp-p1-modeling-audit-2026-09-01.md)
- [P2 冻结合同](specs/binance-1d-ma7-ctp-p2-pooled-minimal-stability-contract-2026-09-01.md)
- [P2 报告](diagnostics/binance-1d-ma7-ctp-p2-pooled-minimal-stability-2026-09-01.md)
- [P2 审计](diagnostics/binance-1d-ma7-ctp-p2-modeling-audit-2026-09-01.md)
- [P3 冻结合同](specs/binance-1d-ma7-ctp-p3-context-feature-block-audit-contract-2026-09-01.md)
- [P3 数据门禁报告](diagnostics/binance-1d-ma7-ctp-p3-context-feature-block-audit-2026-09-01.md)
- [P3 审计](diagnostics/binance-1d-ma7-ctp-p3-modeling-audit-2026-09-01.md)
- [P3R 修复合同](specs/binance-1d-ma7-ctp-p3r-time-boundary-repair-context-feature-block-audit-contract-2026-09-02.md)
- [P3R 报告](diagnostics/binance-1d-ma7-ctp-p3r-context-feature-block-audit-2026-09-02.md)
- [P3R 审计](diagnostics/binance-1d-ma7-ctp-p3r-modeling-audit-2026-09-02.md)
- [P4 压缩消融合同](specs/binance-1d-ma7-ctp-p4-core-factor-ablation-compression-contract-2026-09-02.md)
- [P4 报告](diagnostics/binance-1d-ma7-ctp-p4-core-factor-ablation-compression-2026-09-02.md)
- [P4 审计](diagnostics/binance-1d-ma7-ctp-p4-modeling-audit-2026-09-02.md)
- [P5 RSI6/周线验证合同](specs/binance-1d-ma7-ctp-p5-oscillator-weekly-validation-contract-2026-09-02.md)
- [P5 报告](diagnostics/binance-1d-ma7-ctp-p5-oscillator-weekly-validation-2026-09-02.md)
- [P5 建模审计](diagnostics/binance-1d-ma7-ctp-p5-modeling-audit-2026-09-02.md)
- [P5 周线因果审计](diagnostics/binance-1d-ma7-ctp-p5-weekly-causality-audit-2026-09-02.md)
- [P5 独立验收与修复审计](diagnostics/binance-1d-ma7-ctp-p5-independent-acceptance-audit-2026-09-02.md)
- [全市场 SCOUT](diagnostics/binance-1d-ma7-cross-trend-probability-all-market-2026-08-31.md)
- [产物索引](artifacts/README.md)
