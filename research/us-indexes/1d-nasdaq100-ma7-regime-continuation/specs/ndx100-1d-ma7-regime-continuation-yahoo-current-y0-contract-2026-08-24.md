# NDX100-1D-MA7-RC-Y0 Yahoo 当前成分诊断合同

## 身份

- Observation：`NDX100-1D-MA7-RC-Y0`。
- 角色：为验证 Yahoo 日线可用性而建立的当前成分股诊断，不是 historical point-in-time P0 的替代品。
- 状态：`explore / diagnostic-only / survivorship-biased / not promoted / not live-ready`。

## 数据冻结

- Universe：取 `2026-08-21` 冻结 Nasdaq-100 terminal snapshot 的全部证券，并把这组当前证券回填至其各自 Yahoo 可得历史；指数可能因多重 share class 超过 100 条证券。
- Provider：Yahoo Finance `query2` chart endpoint，无 API key。
- Fetch：`2008-01-01` 至 `2026-08-21`，为 `2010-01-01` 起的研究保留 252-session regime warm-up。
- Price：由 Yahoo raw OHLC 和 split events 重建 split-only OHLC；不使用含分红的 `Adj Close` 作为主价格。
- Calendar：XNAS regular sessions；无效 OHLC、重复和非交易日必须记录，价格与 forward return 禁止填 `0`。
- Cache：只写本家族 `artifacts/yahoo-current-cache/`，不进入 accepted canonical 数据湖。

## 解释边界

本观察存在明确 survivorship bias、listing-age bias、ticker-history/corporate-action 不完整风险。MA7 trigger、Slope/ER/RV、quintile、forward horizon、gap 和 robustness 如继续运行，全部继承 P0 冻结公式且禁止调参。任何结果只能与 historical P0 分开报告，不能用于 promotion，也不能声称代表历史 Nasdaq-100。

机器配置：[`../configs/ndx100-1d-ma7-regime-continuation-yahoo-current-y0.json`](../configs/ndx100-1d-ma7-regime-continuation-yahoo-current-y0.json)。
