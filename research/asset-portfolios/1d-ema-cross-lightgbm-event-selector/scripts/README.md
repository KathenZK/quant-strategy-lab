# Scripts — BIN-1D-EMAX-LGBM

一次性研究脚本。`1d` K 线在缓存构建时由已审计 `1h` Vision 归档重采样（UTC 日边界，OHLCV 聚合，衍生口径见基线报告）；标注、funding、指标复用 15m 家族冻结引擎 [`emax_common.py`](../../15m-ema-cross-lightgbm-event-selector/scripts/emax_common.py) 的纯函数（该文件按 SHA256 锁定，不得修改）。产物落 [../artifacts/](../artifacts/README.md)。

- [`run_baseline.py`](run_baseline.py)：P1 基线（缓存构建、币池、事件抽取、bracket 统计）。
- [`backtest_portfolio_control_a.py`](backtest_portfolio_control_a.py)：P2 组合级回测（A1 未门控 / A2 宽度门控），执行 [组合级契约](../specs/bin-1d-emax-portfolio-contract-2026-07-27.md)。
