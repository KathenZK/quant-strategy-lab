# Scripts — BIN-4H-EMAX-LGBM

一次性研究脚本。`4h` K 线在缓存构建时由已审计 `1h` Vision 归档重采样（UTC 4h 边界，OHLCV 聚合，衍生口径见基线报告）；标注、funding、指标复用 15m 家族冻结引擎 [`emax_common.py`](../../15m-ema-cross-lightgbm-event-selector/scripts/emax_common.py) 的纯函数（该文件按 SHA256 锁定，不得修改）。产物落 [../artifacts/](../artifacts/README.md)。

- [`run_baseline.py`](run_baseline.py)：P1 基线（含 legacy 分区修复后的装载 glob）。
- [`backtest_portfolio_control_a.py`](backtest_portfolio_control_a.py)：P2 对照组 A 组合回测（A1 未门控 / A2 BTC 日线 EMA96 门控）。
- [`build_v2_dataset.py`](build_v2_dataset.py)：V2 特征数据集（复用 15m 特征模块 [`emax_features.py`](../../15m-ema-cross-lightgbm-event-selector/scripts/emax_features.py)）。
- [`train_v2_scoring.py`](train_v2_scoring.py)：V2 LightGBM 打分层（扩窗逐年 purged CV）。
- [`backtest_portfolio_v2.py`](backtest_portfolio_v2.py)：V2 叠加组合与同窗 A1 对照。
- [`research_local_trend_selector.py`](research_local_trend_selector.py)：15m 局部+趋势选择器移植（a2 特征集，"换特征域"重启诊断）。
- [`research_k_candle_supplement.py`](research_k_candle_supplement.py)：K 族蜡烛形态增补（结果：轻微稀释，不纳入）。
