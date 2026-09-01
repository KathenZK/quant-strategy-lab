# Decision Log

## 2026-08-31：四币日K MA7 穿越趋势发生率 SCOUT

决策：用户要求在 BTC/ETH/BNB/SOL 永续日K上统计穿越 MA7 后发生趋势的条件概率，以及斜率、放量、7/30/60/90 日上涨回撤比的分层。另立 diagnostic topic，不继承 TPSA/MA7-RC 的交易规则，不登记版本。

证据：[冻结口径](specs/binance-1d-ma7-cross-trend-probability-contract-2026-08-31.md) · [诊断](diagnostics/binance-1d-ma7-cross-trend-probability-2026-08-31.md)

## 2026-08-31：裸穿越约三成走出趋势段，斜率/放量/30日R过滤几乎不抬升

决策：全历史四币合计 `trend_20` 为 30.8%（多头 34.4%，空头 27.2%）。斜率 0.02、放量 1.5× 及其组合只把合计抬到 31–33%；预指定的 30 日多头 R<1 / 空头 R>1 反而降到 27.7%。保持 `explore / diagnostic-only / not promoted / not live-ready`，不把格子观察升级成过滤器。

证据：[诊断](diagnostics/binance-1d-ma7-cross-trend-probability-2026-08-31.md) · [汇总 JSON](artifacts/binance_1d_ma7_ctp_summary_2026-08-31.json)

## 2026-08-31：全市场缓存日K 仍约三成，方向结构接近 TPSA 而不是四币

决策：同一冻结口径扩到 `data/cache/binance_perp_1d_from_15m`（2020-01-01 至 2026-06-30 完整日）。653 个入选合约、111,918 个可标签穿越，合计 `trend_20` 30.4%（多头 29.3%，空头 31.6%）。斜率 0.02 只到 32.5%；放量 1.5× 降到 28.6%。保持 `explore / diagnostic-only / not promoted / not live-ready`，不另立家族、不搜索新阈值。

证据：[全市场诊断](diagnostics/binance-1d-ma7-cross-trend-probability-all-market-2026-08-31.md) · [汇总 JSON](artifacts/binance_1d_ma7_ctp_all_market_summary_2026-08-31.json)

## 2026-08-31：HYPE 点估计偏高，但不能判定比其它币更容易走出趋势

决策：同一冻结标签下 HYPE `trend_20` 为 36.0%（31/86），全市场 30.4%、同窗口其它币 30.1%。区间重叠，同窗口单侧二项 p=0.14。多头点估计更高但是事后拆分。保持 `explore / diagnostic-only / not promoted / not live-ready`。

证据：[HYPE 对照](diagnostics/binance-1d-ma7-cross-trend-probability-hype-vs-universe-2026-08-31.md) · [对照 JSON](artifacts/binance_1d_ma7_ctp_hype_vs_universe_2026-08-31.json)
