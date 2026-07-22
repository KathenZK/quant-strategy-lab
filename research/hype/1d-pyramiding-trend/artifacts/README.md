# Artifacts

本目录保存 `HYPE-1D-PT` 的搜索摘要、prefit frontier、冻结 primary 的逐 campaign 交易与权益路径。JSON 是机器可读结论源，CSV 用于独立复核和绘图；参数选择只允许使用文件名含 `prefit-frontier` 的 prefit 指标，不得回看 OOS 后再调参。

- [hype-1d-pt-search-2026-07-22.json](hype-1d-pt-search-2026-07-22.json)：数据质量、冻结边界、搜索计数、120 个 frozen prefit observation 的 OOS/压力结果。
- [hype-1d-pt-prefit-frontier-2026-07-22.csv](hype-1d-pt-prefit-frontier-2026-07-22.csv)：只含 prefit 指标的多目标 frontier。
- [hype-1d-pt-frozen-candidate-trades-2026-07-22.csv](hype-1d-pt-frozen-candidate-trades-2026-07-22.csv)：joint-nearest observation 的逐 campaign 记录。
- [hype-1d-pt-frozen-candidate-path-2026-07-22.csv](hype-1d-pt-frozen-candidate-path-2026-07-22.csv)：joint-nearest observation 的权益/仓位路径。
