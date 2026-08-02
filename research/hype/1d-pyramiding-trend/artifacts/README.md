# Artifacts

本目录保存 `HYPE-1D-PT` 的搜索摘要、prefit frontier、冻结 primary 的逐 campaign 交易与权益路径。JSON 是机器可读结论源，CSV 用于独立复核和绘图；参数选择只允许使用文件名含 `prefit-frontier` 的 prefit 指标，不得回看 OOS 后再调参。

- [hype-1d-pt-search-2026-07-22.json](hype-1d-pt-search-2026-07-22.json)：数据质量、冻结边界、搜索计数、120 个 frozen prefit observation 的 OOS/压力结果。
- [hype-1d-pt-prefit-frontier-2026-07-22.csv](hype-1d-pt-prefit-frontier-2026-07-22.csv)：只含 prefit 指标的多目标 frontier。
- [hype-1d-pt-frozen-candidate-trades-2026-07-22.csv](hype-1d-pt-frozen-candidate-trades-2026-07-22.csv)：joint-nearest observation 的逐 campaign 记录。
- [hype-1d-pt-frozen-candidate-path-2026-07-22.csv](hype-1d-pt-frozen-candidate-path-2026-07-22.csv)：joint-nearest observation 的权益/仓位路径。
- [hype-1d-pt-ma7-ma30-search-2026-07-30.json](hype-1d-pt-ma7-ma30-search-2026-07-30.json)：固定 `MA7/MA30` 的数据质量、搜索面、示例变体和 160 个冻结 observation 审计。
- [hype-1d-pt-ma7-ma30-prefit-frontier-2026-07-30.csv](hype-1d-pt-ma7-ma30-prefit-frontier-2026-07-30.csv)：只含 prefit 指标的 role-balanced frontier。
- [hype-1d-pt-ma7-ma30-primary-trades-2026-07-30.csv](hype-1d-pt-ma7-ma30-primary-trades-2026-07-30.csv) · [路径](hype-1d-pt-ma7-ma30-primary-path-2026-07-30.csv)：冻结联合 primary 的逐 campaign 与权益/仓位路径。
- [hype-1d-pt-ma7-ma30-prefit-ablation-2026-07-30.csv](hype-1d-pt-ma7-ma30-prefit-ablation-2026-07-30.csv) · [滚动审计](hype-1d-pt-ma7-ma30-rolling-audit-2026-07-30.csv)：prefit 部件消融与 90 天滚动窗口。
