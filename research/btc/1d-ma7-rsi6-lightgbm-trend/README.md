# BTC-1D-MA7-RSI6-LightGBM-Trend

- Alias：`BTC-1D-MA7-RSI6-LGBM`
- 市场/周期：Binance USD-M `BTCUSDT` perpetual，UTC `1d`
- 机制：以 `SMA7` 穿越、价格相对 `SMA7` 的路径和 `RSI6` 阶段状态为核心特征，用 LightGBM 研究趋势延续、顶部反转与底部反转的条件概率。
- 当前状态：`explore / diagnostic-only / not promoted / not live-ready`；尚未训练模型或登记版本。

## 边界

- 本家族是 BTC 日线机器学习研究，不继承 HYPE 日线 MA7 家族或既有 BTC/ETH MA7 参数搜索的版本、参数与结论。
- 所有特征只能读取当前已闭合日 K 及历史；收盘产生的信号最早在下一 UTC 日开盘成交。
- 当前 P0 只冻结数据、验证集和首批特征定义；模型输出、标签、阈值及最终退出机制尚未冻结。

## 入口

- [主账](btc-1d-ma7-rsi6-lgbm-core-ledger.md)
- [决策记录](decision-log.md)
- [P0 数据与特征合同](specs/btc-1d-ma7-rsi6-lgbm-p0-data-feature-contract-2026-08-07.md)
- [P1 development 合同](specs/btc-1d-ma7-rsi6-lgbm-p1-development-contract-2026-08-07.md)
- [P1 development 诊断](diagnostics/btc-1d-ma7-rsi6-lgbm-p1-development-2026-08-07.md)
- [P2 expected-return 合同](specs/btc-1d-ma7-rsi6-lgbm-p2-expected-return-contract-2026-08-10.md)
- [P2 expected-return 诊断](diagnostics/btc-1d-ma7-rsi6-lgbm-p2-expected-return-2026-08-10.md)
- [P3 Logistic-EV 稳健性合同](specs/btc-1d-ma7-rsi6-logistic-ev-p3-robustness-contract-2026-08-10.md)
- [P3 Logistic-EV 稳健性诊断](diagnostics/btc-1d-ma7-rsi6-logistic-ev-p3-robustness-2026-08-10.md)
- [数据质量证据](artifacts/btcusdt_perp_1d_data_quality_2026-08-07.json)
- [数据同步脚本](scripts/sync_btcusdt_perp_1d.py)
- [产物索引](artifacts/README.md)
