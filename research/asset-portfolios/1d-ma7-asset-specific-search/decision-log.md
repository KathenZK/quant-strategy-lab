# Decision Log

## 2026-08-05 — BTC/ETH 固定 MA7 分资产与共享参数搜索

决定：按用户要求固定 `SMA7/ATR7`，在 development 内分别搜索 BTC、ETH 多空参数并选择 BTC/ETH 共享参数。单资产 full 可达到 BTC `+125.24%`、ETH `+421.94%`，但 researcher-exposed holdout 分别只有 `+0.06% / -8.82%`；共享参数 full 为 `+112.34% / +161.46%`、holdout 为 `+0.49% / +27.14%`，但 ETH `12h` 相位转为 `-10.58%`。三条路线保持 `explore / not promoted / not live-ready`，不登记、不按 holdout 二次选参；共享参数仅保留为优先 prospective observation。证据：[搜索诊断](diagnostics/binance-btc-eth-1d-ma7-asset-specific-search-2026-08-05.md) · [机器摘要](artifacts/binance_btc_eth_1d_ma7_asset_specific_search_summary_2026-08-05.json)。

## 2026-08-05 — 共享参数应用于 HYPE

决定：BTC/ETH 共享参数原样应用到 HYPE 后 combined `-65.15%`、MDD `-73.47%`，long-only / short-only 为 `-24.12% / -59.45%`，`0h/12h` 均大幅亏损；共享参数不是通用 MA7 参数，不根据 HYPE 结果二次调整，保持 `explore / not promoted / not live-ready`。证据：[HYPE control 诊断](diagnostics/binance-ma7-shared-params-on-hype-2026-08-05.md) · [机器摘要](artifacts/binance_ma7_shared_params_on_hype_summary_2026-08-05.json)。

## 2026-08-05 — 共享参数应用于美股指数

决定：BTC/ETH 共享参数零调参应用到 S&P 500 / Nasdaq Composite 后，full combined 为 `+18.77%/+91.43%`，但 `10 bps/fill` 后为 `-48.26%/-12.38%`，且 short-only 均长期亏损、远逊 buy-and-hold；不根据指数结果调参，不改变共享参数的 `explore / not promoted / not live-ready` 判定。证据：[美股指数诊断](../../us-indexes/1d-ma7-shared-parameter-transfer/diagnostics/us-indexes-1d-ma7-shared-parameter-transfer-2026-08-05.md)。

## 2026-08-06 — 平多即反手空诊断

决定：预先冻结并检验“多头 `ma7_hysteresis_exit` 时同 open 平多反手 `1x` 空单”；HYPE/BTC/ETH 相对原策略收益变化为 `-0.56/0.00/-22.73pp`。HYPE/ETH 各新增 1 笔反手且均亏损，BTC 两次相关事件本来就会自然同开盘开空；该机制不采纳，不改写 HYPE V1 或 BTC/ETH 共享参数。证据：[冻结合同](specs/binance-ma7-long-exit-short-reversal-contract-2026-08-06.md) · [诊断](diagnostics/binance-ma7-long-exit-short-reversal-2026-08-06.md)。

## 2026-08-12 — 共享参数对齐HYPE fresh窗口复算

决定：按用户要求用当前 HYPE fresh API 窗口复算 BTC/ETH shared MA7 参数；剔除首个不完整小时路径日后，`2025-05-31` 至 `2026-08-12` terminal open 的完整日 `438d` combined 仍为 `-65.15%`、MDD `-73.47%`，long-only / short-only `-24.12% / -59.45%`，同期 buy-and-hold `+52.01%`。该复算不改变旧裁决：共享参数不是 HYPE 通用替代版本，不登记、不 promotion、不推进 runner。证据：[fresh aligned诊断](diagnostics/binance-ma7-shared-params-on-hype-fresh-aligned-2026-08-12.md) · [机器证据](artifacts/binance_ma7_shared_params_on_hype_fresh_aligned_2026-08-12.json)。

## 2026-08-12 — 共享参数在BTC/ETH的HYPE对齐窗口复算

决定：为澄清“全周期赚钱是否只是窗口效应”，同一 BTC/ETH shared MA7 参数截取 `2025-05-31` 至 `2026-08-12` terminal open 后，`BTCUSDT` combined `+48.86%`、MDD `-14.78%`，`ETHUSDT` combined `+55.29%`、MDD `-27.02%`；同期两者 buy-and-hold 分别为 `-43.28% / -30.73%`。因此问题不是 HYPE 对齐窗口失效，而是 shared 参数迁移到 HYPE 资产失败。证据：[BTC/ETH aligned诊断](diagnostics/binance-ma7-shared-params-btc-eth-hype-aligned-2026-08-12.md)。

## 2026-08-12 — 登记 V1 并生成 BTC/ETH 交易路径

决定：按用户要求，将 BTC/ETH shared MA7 参数登记为 `Binance-1D-MA7-Asset-Specific-Search-V1`，状态为 `registered / not promoted / not live-ready`；同时基于 HYPE 对齐窗口机器证据生成 BTC 与 ETH 的自包含交易路径 HTML。登记只固定版本身份和证据链接，不代表 HYPE 可迁移、live spec、dry-run 或 runner 授权。证据：[V1规格](specs/binance-1d-ma7-as-search-v1-spec.md) · [BTC路径](artifacts/binance_ma7_shared_params_v1_btc_trade_path_2026-08-12.html) · [ETH路径](artifacts/binance_ma7_shared_params_v1_eth_trade_path_2026-08-12.html)。

## 2026-08-13 — BTC/ETH候选最近1至4年横向排名

决定：固定既有 growth 路径并统一按 `2025-08-07` 终点切分；近期综合前三为 `COST / CPPR-25% / DASE`。三者只保留为核心收益、风险模块与组合架构的后继研究材料；`CILL/CBCT` 仅保留模块或对照，其余当前机制停止。该诊断不重选参数、不揭示 audit/prospective、不改变任何家族状态。证据：[横向排名](diagnostics/binance-btceth-recent-horizon-ranking-2026-08-13.md) · [机器摘要](artifacts/binance_btceth_recent_horizon_ranking_2026-08-13.json)。

## 2026-08-17 — 登记 V2 并生成 BTC/ETH 交易路径

决定：按用户要求，将 P2-C parent（V1 shared 参数、仅 long `entry_mode` 改为 `pullback_reclaim`）登记为 `Binance-1D-MA7-Asset-Specific-Search-V2`，状态为 `registered / HARD-GATE-FAILED / not promoted / not live-ready`。P2-I 的研究线关闭与不 promotion 结论不变；本次只固定版本身份并绘制全样本路径，不授权 live spec 或 runner。证据：[V2规格](specs/binance-1d-ma7-as-search-v2-spec.md) · [BTC路径](artifacts/binance_1d_ma7_as_search_v2_btc_trade_path_2026-08-17.html) · [ETH路径](artifacts/binance_1d_ma7_as_search_v2_eth_trade_path_2026-08-17.html)。
