# BIN-1D-MA7-DSML 决策记录

## 2026-08-10 — 从局部价格确认转入独立 derivatives structure

LMML、RHT、VIPR 已连续否定 maturity snapshot、逐小时等待与原生 breakout/pullback 的局部价格筛选；决定不再制造指标，改为在冻结 LMML 经济事件上只测试 Binance Vision OI、top-trader/global positioning、taker flow 与 leave-target-out 市场结构。HYPE 继续锁定；详见 [P0/P1 合同](specs/binance-1d-ma7-dsml-p0-p1-contract-2026-08-10.md) 与 [VIPR 失败诊断](../1h-volatility-impulse-pullback-reclaim/diagnostics/binance-1h-vipr-p1-development-2026-08-10.md)。

## 2026-08-10 — 官方历史不足，P0 下载前停止

四个 altcoin metrics 从 `2021-12-01` 才存在，30 日上下文后冻结 LMML 事件最多剩 967 个，四项 P0 容量门全部不可达；决定不降门、不下载约六千个无助于缺失历史的日包、不拟合 P1。下一轮若继续使用 derivatives structure，必须改为覆盖期内每日全锚点的新采样机制。证据见 [P0 容量诊断](diagnostics/binance-1d-ma7-dsml-p0-capacity-2026-08-10.md)。
