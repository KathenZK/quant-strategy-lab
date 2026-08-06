# Decision Log

## 2026-08-04：建立独立的日线 MA7 延续与偏离验证线

冻结 SMA7、三资产分开判断和无订单的第一阶段边界；过去 MA7/MA30 交易规则失败不直接否定 MA7 偏离状态的预测价值。验证口径见[初始合同](specs/binance-1d-ma7dc-initial-validation-contract-2026-08-04.md)。

## 2026-08-04：只有 BTC long 获得部分支持

三资产验证后，BTC long 通过方向延续与斜率增量两项，ETH long 只通过 restart 增量，HYPE 与全部 short 未获支持；不登记版本。若继续，只让 BTC long 进入新的执行研究，证据见[初始验证报告](diagnostics/binance-1d-ma7dc-initial-validation-2026-08-04.md)。

## 2026-08-04：HYPE 截图的 MA7 视觉贴合只获得部分事实支持

改用独立 ATR ZigZag 评分完整趋势后，HYPE `2 ATR / 3–14d / cross1 / long` 的 MA7 admission 为 100%、及时进入为 66.7%，但只有 6 段，完整波段捕获中位数 18.7%、MFE 保留 31.7%，证据为 `insufficient`。截图中约 20.5→77 的主体上涨实际是约 134 日的 `3 ATR` swing；按 MA7 真实执行需 9–11 次往返才能跟到结束附近，成本后只捕获约三分之一。由此冻结结论：MA7 可作长期 campaign 状态参考，但不能单独作为完整开平仓状态机；不登记版本，证据见[Campaign 持仓轨道验证](diagnostics/binance-1d-ma7dc-campaign-tracking-2026-08-04.md)。

## 2026-08-04：单独 MA7 容忍带失败，半 MFE 仅保留为后续假设

冻结三臂验证后，`0.5ATR + 两日确认` 明显恶化；叠加 `2R 后最多回吐 50%` 虽改善 HYPE 波段捕获和 MFE 保留，但主样本只有 6 段、只过 2/5，近期切片仍弱，决定 `insufficient / not promoted`。同时确认 `1ATR` 单腿 stop 与长期 campaign 尺度冲突；后续必须分离 position stop 与 campaign invalidation，证据见[容忍带与半 MFE 验证](diagnostics/binance-1d-ma7dc-tolerance-exit-2026-08-04.md)。
