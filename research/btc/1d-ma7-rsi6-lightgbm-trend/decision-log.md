# Decision Log

## 2026-08-07

决定以 Binance USD-M `BTCUSDT` perpetual 完整 UTC 日 K 启动独立的 MA7/RSI6 LightGBM 诊断线：严格 MA7 收盘上穿/下穿作为离散特征，Wilder `RSI6` 作为连续阶段特征，并把最近完整一年永久冻结为一次性 validation。证据：[P0 合同](specs/btc-1d-ma7-rsi6-lgbm-p0-data-feature-contract-2026-08-07.md)与[数据质量审计](artifacts/btcusdt_perp_1d_data_quality_2026-08-07.json)。

## 2026-08-07 P1

在不读取冻结 validation 的前提下冻结 P1 development-only 事件筛选合同：MA7 严格穿越定方向，LightGBM 预测成本后净正概率，RSI6 `80/20` 极值后反向确认、固定 `3×ATR7` 止损和反向 MA7 穿越共同定义退出，并以 nested walk-forward、预注册阈值和门禁决定是否取得 validation 揭示资格。证据：[P1 development 合同](specs/btc-1d-ma7-rsi6-lgbm-p1-development-contract-2026-08-07.md)。

## 2026-08-07 P1 结果

P1 development 门禁失败：核心 LightGBM 的 OOS 排序接近随机，预注册阈值没有形成可交易样本；因此不揭示最近一年、不登记版本、不生成候选交易路径，后续若继续须先建立新的 expected-net-return P2 合同。证据：[P1 development 诊断](diagnostics/btc-1d-ma7-rsi6-lgbm-p1-development-2026-08-07.md)。

## 2026-08-10 P2

在 validation 继续封存的前提下冻结 P2 expected-return 合同：保持 P1 事件、特征和执行状态机不变，以未缩尾成本后净收益的 L2 回归为主，预注册 edge、inner `5/15` 交易覆盖和 OOS Spearman/top-quintile 排序门禁。证据：[P2 expected-return 合同](specs/btc-1d-ma7-rsi6-lgbm-p2-expected-return-contract-2026-08-10.md)。

## 2026-08-10 P2 结果

P2 主模型经济与排序门禁失败，validation 继续封存；Logistic-EV 对照虽通过本轮数值门槛，但因不是预注册主模型只能作为独立 P3 线索，不能事后替换并直接揭示 validation。证据：[P2 expected-return 诊断](diagnostics/btc-1d-ma7-rsi6-lgbm-p2-expected-return-2026-08-10.md)。

## 2026-08-10 P3

在 validation 继续封存且必须另行人工批准揭示的前提下，冻结 P3 Logistic-EV 稳健性合同：固定 `1.00%` edge、不再搜索，新增 `3/4` 绝对正折、`0.50%/1.50%` 压力线和 `10,000` 次分层交易 bootstrap。证据：[P3 稳健性合同](specs/btc-1d-ma7-rsi6-logistic-ev-p3-robustness-contract-2026-08-10.md)。

## 2026-08-10 P3 结果

P3 稳健性失败：combined 只在 `2/4` 折绝对为正，`1.50%` 压力和 bootstrap 均失败；short-only 虽四折全正但只有 `14` 笔且 bootstrap 未达 `95%`。决定继续封存 validation，不登记候选，并停止在同一 BTC 特征/edge 上微调。证据：[P3 稳健性诊断](diagnostics/btc-1d-ma7-rsi6-logistic-ev-p3-robustness-2026-08-10.md)。
