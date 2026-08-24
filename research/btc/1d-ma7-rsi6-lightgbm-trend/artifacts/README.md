# Artifacts

- [BTCUSDT 永续完整日 K 数据质量与冻结切分证据（2026-08-07）](btcusdt_perp_1d_data_quality_2026-08-07.json)：记录 Binance 合约身份、数据范围、缺口/重复/OHLC/闭合状态、raw/normalized 对齐、消费者视图 hash 与最近一年 validation 边界。
- [BTCUSDT 永续完整 1h stop-path 数据质量（2026-08-07）](btcusdt_perp_1h_stop_path_quality_2026-08-07.json)：记录小时路径的完整性、闭合状态、raw/normalized 对齐和 hash。
- [BTCUSDT funding/mark 数据质量（2026-08-07）](btcusdt_funding_mark_quality_2026-08-07.json)：记录实际 funding rate、官方 mark fallback、timestamp 对齐和 endpoint/fallback 差异。
- [P1 development 机器证据目录](p1_development_2026-08-07/)：包含事件标签、外层 OOS 概率、SHAP、模型、门禁摘要和空的 selected-trade 证据。
- [P2 expected-return 机器证据目录](p2_expected_return_2026-08-10/)：包含 P1/P2 事件 hash、收益回归/Logistic-EV 消融、嵌套 edge、OOS 预测、SHAP、模型和门禁摘要。
- [P3 Logistic-EV 稳健性机器证据目录](p3_logistic_ev_robustness_2026-08-10/)：包含固定 edge OOS 预测、双 edge 压力、分层 bootstrap、系数稳定性和 validation 封存 manifest。

P1/P2/P3 均未通过完整 development 门禁，因此本目录不包含候选交易路径 HTML，冻结 validation 也未产生输出。
