# Binance-1D-MA7-Asset-Specific-Search Core Ledger

## Family Identity

- Full family name：`Binance-1D-MA7-Asset-Specific-Search`
- Alias：`BIN-1D-MA7-AS-SEARCH`
- Market / symbols / timeframe：Binance USD-M `BTCUSDT`、`ETHUSDT` perpetual，UTC `1d`；`HYPEUSDT` 与美股价格指数只作共享参数 control
- Mechanism：固定 `SMA7/ATR7`，分资产搜索多空 entry / hold / exit，并以最差侧稳健分数选择 BTC/ETH 共享参数。
- Boundary：这是 HYPE 参数直迁失败后的 materially new target-asset search；不回写 `BIN-1D-MA7-ST-XFER` 或 HYPE V1。

## Current State

- Current version：无；本次未登记版本。
- Current status：`explore / not promoted / not live-ready`。
- BTC asset-specific：development `+125.11%`，researcher-exposed holdout `+0.06%`，full `+125.24%`、MDD `-19.67%`、33 笔。
- ETH asset-specific：development `+364.32%`，holdout `-8.82%`，full `+421.94%`、MDD `-28.71%`、26 笔。
- Shared parameters：BTC development / holdout / full 为 `+111.30% / +0.49% / +112.34%`；ETH 为 `+140.80% / +27.14% / +161.46%`。
- HYPE control：共享参数零调参应用于 HYPE 为 `-65.15%`、MDD `-73.47%`；long-only / short-only `-24.12% / -59.45%`，两个日界均大幅亏损。
- US-index controls：S&P 500 / Nasdaq Composite full combined 为 `+18.77%/+91.43%`，但 `10 bps/fill` 后为 `-48.26%/-12.38%`，且均远逊 buy-and-hold。
- Stress：三条目标 route 的 full `8 bps` 与额外延迟均为正；共享参数 holdout 在 BTC 基本持平、ETH 为正。
- Phase：BTC asset-specific `0h/12h=+125.24%/+50.23%`；ETH asset-specific `+421.94%/+19.74%`；共享参数在 ETH 为 `+161.46%/-10.58%`，相位门禁失败。
- Runner：无 live spec、无 quant-runner implementation、无 dry-run/live instance。
- Blockers：BTC/ETH 历史此前已查看；每方向搜索 20,000 组并做组合选择；单资产 holdout flat/negative；ETH 相位严重衰减或翻负；无 clean prospective OOS、CPCV、runner parity 或线上对账。
- Next gate：不根据 holdout 或 `12h` 结果二次选参；如继续，只能优先冻结共享参数，等待新增日 K prospective observation。

## Version Rules

- 本次候选只是历史开发 observation，不产生 `V1`。
- 单资产与共享参数是三条不同选择口径；不能只挑其 full 收益作为同一版本。
- 修改 MA 长度、搜索空间、时间切分、选择目标、资产集合、成本或相位后重新挑选，均是新搜索合同。
- “登记/冻结 Vx”与 promotion 必须由用户另行明确请求。

## Version Table

| Observation | Status | Role / Core Idea | Key Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| BTC asset-specific | `explore / not promoted / not live-ready` | BTC development 单独选参 | full `+125.24%`，holdout `+0.06%`，MDD `-19.67%` | [搜索诊断](diagnostics/binance-btc-eth-1d-ma7-asset-specific-search-2026-08-05.md) | holdout 优势消失，不登记 |
| ETH asset-specific | `explore / not promoted / not live-ready` | ETH development 单独选参 | full `+421.94%`，holdout `-8.82%`，`12h=+19.74%` | [搜索诊断](diagnostics/binance-btc-eth-1d-ma7-asset-specific-search-2026-08-05.md) | 时间与相位失败，不登记 |
| BTC/ETH shared | `explore / not promoted / not live-ready` | 最大化两资产 development 最差侧 | BTC/ETH full `+112.34%/+161.46%`；holdout `+0.49%/+27.14%` | [搜索诊断](diagnostics/binance-btc-eth-1d-ma7-asset-specific-search-2026-08-05.md) | 最值得 prospective，但 ETH 相位翻负 |
| Shared → HYPE control | `explore / not promoted / not live-ready` | 共享参数不调参回测 HYPE | combined `-65.15%`，MDD `-73.47%`；`12h=-70.24%` | [HYPE control 诊断](diagnostics/binance-ma7-shared-params-on-hype-2026-08-05.md) | 多空均失败；证明共享参数不通用 |
| Shared → US indexes | `explore / not promoted / not live-ready` | 共享参数不调参回测 S&P 500 / Nasdaq Composite | combined `+18.77%/+91.43%`；成本后均负 | [美股指数诊断](../../us-indexes/1d-ma7-shared-parameter-transfer/diagnostics/us-indexes-1d-ma7-shared-parameter-transfer-2026-08-05.md) | long 有部分 edge，short 与成本失败 |

## Shared Assumptions

- Data：accepted Binance `1h` raw/normalized 聚合完整 UTC 日 K；development `550d`，researcher-exposed holdout `179d`。
- Search：固定 `SMA7`；每资产每方向 `20,000` 个唯一配置，development-only shortlist / stress / delay / pair selection。
- Cost：手续费 `0.001/fill`、不利滑点 `4 bps/fill`、实际 event-time funding；压力滑点 `8 bps/fill`。
- Execution：收盘信号次日 open；stop 用真实 `1h` 路径；约 `1x`、单仓、非加仓。
- Evidence role：全部历史均已揭示；holdout 没有参与本次选择，但不是 clean OOS。

## Evidence Map

- [冻结搜索合同](specs/binance-btc-eth-1d-ma7-search-contract-2026-08-05.md)
- [搜索与诊断报告](diagnostics/binance-btc-eth-1d-ma7-asset-specific-search-2026-08-05.md)
- [共享参数应用于 HYPE 诊断](diagnostics/binance-ma7-shared-params-on-hype-2026-08-05.md)
- [共享参数应用于美股指数诊断](../../us-indexes/1d-ma7-shared-parameter-transfer/diagnostics/us-indexes-1d-ma7-shared-parameter-transfer-2026-08-05.md)
- [机器摘要](artifacts/binance_btc_eth_1d_ma7_asset_specific_search_summary_2026-08-05.json)
- [复现脚本](scripts/search_binance_btc_eth_1d_ma7_asset_specific.py)
- [决策记录](decision-log.md)
