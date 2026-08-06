# Decision Log

## 2026-08-05 — BTC/ETH 固定 MA7 分资产与共享参数搜索

决定：按用户要求固定 `SMA7/ATR7`，在 development 内分别搜索 BTC、ETH 多空参数并选择 BTC/ETH 共享参数。单资产 full 可达到 BTC `+125.24%`、ETH `+421.94%`，但 researcher-exposed holdout 分别只有 `+0.06% / -8.82%`；共享参数 full 为 `+112.34% / +161.46%`、holdout 为 `+0.49% / +27.14%`，但 ETH `12h` 相位转为 `-10.58%`。三条路线保持 `explore / not promoted / not live-ready`，不登记、不按 holdout 二次选参；共享参数仅保留为优先 prospective observation。证据：[搜索诊断](diagnostics/binance-btc-eth-1d-ma7-asset-specific-search-2026-08-05.md) · [机器摘要](artifacts/binance_btc_eth_1d_ma7_asset_specific_search_summary_2026-08-05.json)。

## 2026-08-05 — 共享参数应用于 HYPE

决定：BTC/ETH 共享参数原样应用到 HYPE 后 combined `-65.15%`、MDD `-73.47%`，long-only / short-only 为 `-24.12% / -59.45%`，`0h/12h` 均大幅亏损；共享参数不是通用 MA7 参数，不根据 HYPE 结果二次调整，保持 `explore / not promoted / not live-ready`。证据：[HYPE control 诊断](diagnostics/binance-ma7-shared-params-on-hype-2026-08-05.md) · [机器摘要](artifacts/binance_ma7_shared_params_on_hype_summary_2026-08-05.json)。

## 2026-08-05 — 共享参数应用于美股指数

决定：BTC/ETH 共享参数零调参应用到 S&P 500 / Nasdaq Composite 后，full combined 为 `+18.77%/+91.43%`，但 `10 bps/fill` 后为 `-48.26%/-12.38%`，且 short-only 均长期亏损、远逊 buy-and-hold；不根据指数结果调参，不改变共享参数的 `explore / not promoted / not live-ready` 判定。证据：[美股指数诊断](../../us-indexes/1d-ma7-shared-parameter-transfer/diagnostics/us-indexes-1d-ma7-shared-parameter-transfer-2026-08-05.md)。
