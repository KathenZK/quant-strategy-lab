# Artifacts

本目录保留 `2026-08-18` 文献基线的最小可审计证据：固定配置、数据审计、汇总指标、
月末信号、日路径、分年/分月结果、最近切片、方向 episodes、SHA256 清单和自包含交互图。

输入行情是本地数据湖 `local-dataset`，不复制进 Git；来源版本、下载 URL、CSV SHA256、
UTC/session-date 范围和质量 blocker 由 data-audit JSON 与诊断报告记录。所有数值产物都可由
[回测脚本](../scripts/research_gold_1d_multi_speed_tsmom.py)重新生成。

`recent-extension-2026-08-18` 是 Yahoo `GC=F` 的独立近期段，覆盖 2021-12 至最后完整月
2026-07，并保留 2020-01 起的预热数据。该段不与 Stooq 基线硬拼，包含 Buy&Hold 对照、
交互净值和独立校验清单。
