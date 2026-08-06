# Decision Log

- `2026-07-31`：建立独立 `HYPE-15M-Multidimensional-Trend-Pyramiding` 家族并冻结 V1 初始框架；V35 仅作对照，不继承其身份或状态。[规格](specs/hype-15m-mdtp-v1-spec.md)
- `2026-07-31`：V1 在标准 Binance 成本下 full 净亏 `-64.39%`，五个不重叠滚动 test fold 全亏，27 行邻近阈值网格无正收益区域，结论为 `NO-GO / not promoted / not live-ready`；不进入纸面交易，也不在已揭示历史上继续阈值救援。[初始研究](diagnostics/hype-15m-mdtp-v1-initial-research-2026-07-31.md)
- `2026-08-02`：修复 legacy raw parity 后，六币同参数标准成本全部亏损，HYPE 反而是相对较好标的；失败主因确认为不足 `2 bps/fill` 的弱单位换手优势、高频状态切换和不完整 quantity/open-risk 合同。V1 保持 `explore / not promoted / not live-ready`，不登记事后修补版本。[失败复审](diagnostics/hype-15m-mdtp-v1-failure-audit-2026-08-02.md)
- `2026-08-02`：按用户确认的 `3–14d`、long/short 独立、`1% R0`、`3x cap`、`35/70/85/100%` 与 `2R 后保留一半 MFE` 合同完成 campaign successor。低换手与 quantity/open-risk 目标通过，但 Long 选中行 Train 为负、Short Validation 连 gross 失败；不登记 V2，不重用已揭示 Validation。[初始研究](diagnostics/hype-15m-mdtp-campaign-successor-initial-research-2026-08-02.md)
