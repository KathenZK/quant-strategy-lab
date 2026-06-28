# HYPE-6H-RS4-Regime-Switch

本目录记录同事提供的 RS4 策略说明的独立复现与诊断。

RS4 是 HYPE USDT 永续 `6h` regime-switch 趋势策略：`v10` 压缩动量腿负责低波动后的 MACD 双向趋势，`melt-leg` 扩张突破腿负责高波动且方向干净时的仅多头突破。

## 当前状态

- 当前主版本：`HYPE-6H-RS4-Regime-Switch-V1`。
- 状态：diagnostic only / not promoted。
- 数据：本仓库标准数据湖 Binance HYPEUSDT perpetual `5m` normalized OHLCV，聚合为 `6h`。
- 主要限制：本地没有 HTML 声称的 Bybit 2024-12 全史口径；当前结果只能验证 Binance/canonical 近期段。

## 复现入口

- 主账：`hype-6h-rs4-regime-switch-core-ledger.md`
- 决策记录：`decision-log.md`
- 脚本：`scripts/research_hype_6h_rs4_backtest.py`
- V1 简化版脚本：`scripts/research_hype_6h_rs4_simplified_backtest.py`
- 诊断报告：`diagnostics/hype-6h-rs4-regime-switch-backtest-2026-06-26.md`
- V1 简化版报告：`diagnostics/hype-6h-rs4-simplified-backtest-2026-06-28.md`
- 结果与证据：`artifacts/`
