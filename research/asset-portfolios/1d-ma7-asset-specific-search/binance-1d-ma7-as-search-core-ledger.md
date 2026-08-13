# Binance-1D-MA7-Asset-Specific-Search Core Ledger

## Family Identity

- Full family name：`Binance-1D-MA7-Asset-Specific-Search`
- Alias：`BIN-1D-MA7-AS-SEARCH`
- Market / symbols / timeframe：Binance USD-M `BTCUSDT`、`ETHUSDT` perpetual，UTC `1d`；`HYPEUSDT` 与美股价格指数只作共享参数 control
- Mechanism：固定 `SMA7/ATR7`，分资产搜索多空 entry / hold / exit，并以最差侧稳健分数选择 BTC/ETH 共享参数。
- Boundary：这是 HYPE 参数直迁失败后的 materially new target-asset search；不回写 `BIN-1D-MA7-ST-XFER` 或 HYPE V1。

## Current State

- Current version：`Binance-1D-MA7-Asset-Specific-Search-V1`（`BIN-1D-MA7-AS-SEARCH-V1`）。
- Current status：`V1 registered / not promoted / not live-ready`。
- BTC asset-specific：development `+125.11%`，researcher-exposed holdout `+0.06%`，full `+125.24%`、MDD `-19.67%`、33 笔。
- ETH asset-specific：development `+364.32%`，holdout `-8.82%`，full `+421.94%`、MDD `-28.71%`、26 笔。
- Shared parameters：BTC development / holdout / full 为 `+111.30% / +0.49% / +112.34%`；ETH 为 `+140.80% / +27.14% / +161.46%`；HYPE 对齐窗口内 BTC/ETH 仍为 `+48.86% / +55.29%`。
- HYPE control：共享参数零调参应用于 HYPE 为 `-65.15%`、MDD `-73.47%`；long-only / short-only `-24.12% / -59.45%`，两个日界均大幅亏损；2026-08-12 fresh aligned `438d` 复算未改变结论。
- US-index controls：S&P 500 / Nasdaq Composite full combined 为 `+18.77%/+91.43%`，但 `10 bps/fill` 后为 `-48.26%/-12.38%`，且均远逊 buy-and-hold。
- Stress：三条目标 route 的 full `8 bps` 与额外延迟均为正；共享参数 holdout 在 BTC 基本持平、ETH 为正。
- Phase check：BTC asset-specific `0h/12h=+125.24%/+50.23%`；ETH asset-specific `+421.94%/+19.74%`；共享参数在 ETH 为 `+161.46%/-10.58%`；按现行治理仅降低证据置信度，不单独构成 blocker。
- Long-exit short reversal：多头 `ma7_hysteresis_exit` 同 open 反手空的 R1 在 HYPE / BTC / ETH 相对基准收益变化为 `-0.56 / 0.00 / -22.73pp`；真正新增反手仅 HYPE/ETH 各 1 笔且均亏损，BTC 原规则已自然同开盘开空；不采纳。
- Runner：无 live spec、无 quant-runner implementation、无 dry-run/live instance；本次只登记研究版本，不授权运行。
- Blockers：BTC/ETH 历史此前已查看；每方向搜索 20,000 组并做组合选择；单资产 holdout flat/negative；无 clean prospective OOS、CPCV、runner parity 或线上对账。ETH 相位翻负只作为非强制检查项与置信度提示。
- Next gate：若尝试 promotion，先完成 clean prospective OOS / CPCV / robustness / live-executable 审计；当前不进入 live spec。

## Version Rules

- `V1` 固定为 BTC/ETH shared 参数，不包含 BTC asset-specific、ETH asset-specific 或 HYPE control 参数。
- 单资产候选与 shared 参数是不同选择口径；不能把单资产 full 收益并入 `V1`。
- 修改 MA 长度、搜索空间、选择目标、资产集合、成本模型或 entry/exit 字段后，必须另开 `V2` 或新合同；只追加同参新窗口 observation 不改版本号。
- “登记/冻结 Vx”与 promotion 必须由用户另行明确请求。

## Version Table

| Observation | Status | Role / Core Idea | Key Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| BTC asset-specific | `explore / not promoted / not live-ready` | BTC development 单独选参 | full `+125.24%`，holdout `+0.06%`，MDD `-19.67%` | [搜索诊断](diagnostics/binance-btc-eth-1d-ma7-asset-specific-search-2026-08-05.md) | holdout 优势消失，不登记 |
| ETH asset-specific | `explore / not promoted / not live-ready` | ETH development 单独选参 | full `+421.94%`，holdout `-8.82%`，`12h=+19.74%` | [搜索诊断](diagnostics/binance-btc-eth-1d-ma7-asset-specific-search-2026-08-05.md) | holdout 失败；相位降低置信度，不登记 |
| `Binance-1D-MA7-Asset-Specific-Search-V1` | `registered / not promoted / not live-ready` | BTC/ETH shared 参数；最大化两资产 development 最差侧 | BTC/ETH full `+112.34%/+161.46%`；HYPE aligned `+48.86%/+55.29%`；HYPE control `-65.15%` | [V1规格](specs/binance-1d-ma7-as-search-v1-spec.md) · [搜索诊断](diagnostics/binance-btc-eth-1d-ma7-asset-specific-search-2026-08-05.md) · [HYPE aligned复算](diagnostics/binance-ma7-shared-params-btc-eth-hype-aligned-2026-08-12.md) · [BTC路径](artifacts/binance_ma7_shared_params_v1_btc_trade_path_2026-08-12.html) · [ETH路径](artifacts/binance_ma7_shared_params_v1_eth_trade_path_2026-08-12.html) | 登记研究身份；不 promotion；HYPE 迁移失败 |
| Shared → HYPE control | `explore / not promoted / not live-ready` | 共享参数不调参回测 HYPE | combined `-65.15%`，MDD `-73.47%`；fresh aligned `438d` 同为 `-65.15%` | [HYPE control 诊断](diagnostics/binance-ma7-shared-params-on-hype-2026-08-05.md) · [fresh aligned复算](diagnostics/binance-ma7-shared-params-on-hype-fresh-aligned-2026-08-12.md) | 多空均失败；证明共享参数不通用 |
| Shared → US indexes | `explore / not promoted / not live-ready` | 共享参数不调参回测 S&P 500 / Nasdaq Composite | combined `+18.77%/+91.43%`；成本后均负 | [美股指数诊断](../../us-indexes/1d-ma7-shared-parameter-transfer/diagnostics/us-indexes-1d-ma7-shared-parameter-transfer-2026-08-05.md) | long 有部分 edge，short 与成本失败 |
| Long-exit short reversal | `explore / not promoted / not live-ready` | 多头 MA7 迟滞退出时同 open 反手空 | HYPE/BTC/ETH 收益变化 `-0.56/0.00/-22.73pp` | [反手诊断](diagnostics/binance-ma7-long-exit-short-reversal-2026-08-06.md) | 新增反手无正贡献；不采纳 |

## Shared Assumptions

- Data：accepted Binance `1h` raw/normalized 聚合完整 UTC 日 K；development `550d`，researcher-exposed holdout `179d`。
- Search：固定 `SMA7`；每资产每方向 `20,000` 个唯一配置，development-only shortlist / stress / delay / pair selection。
- Cost：手续费 `0.001/fill`、不利滑点 `4 bps/fill`、实际 event-time funding；压力滑点 `8 bps/fill`。
- Execution：收盘信号次日 open；stop 用真实 `1h` 路径；约 `1x`、单仓、非加仓。
- Evidence role：全部历史均已揭示；holdout 没有参与本次选择，但不是 clean OOS。

## Evidence Map

- [冻结搜索合同](specs/binance-btc-eth-1d-ma7-search-contract-2026-08-05.md)
- [V1规格](specs/binance-1d-ma7-as-search-v1-spec.md)
- [搜索与诊断报告](diagnostics/binance-btc-eth-1d-ma7-asset-specific-search-2026-08-05.md)
- [共享参数应用于 HYPE 诊断](diagnostics/binance-ma7-shared-params-on-hype-2026-08-05.md)
- [共享参数对齐 HYPE fresh 窗口复算](diagnostics/binance-ma7-shared-params-on-hype-fresh-aligned-2026-08-12.md)
- [共享参数在 BTC/ETH 的 HYPE 对齐窗口复算](diagnostics/binance-ma7-shared-params-btc-eth-hype-aligned-2026-08-12.md)
- [共享参数应用于美股指数诊断](../../us-indexes/1d-ma7-shared-parameter-transfer/diagnostics/us-indexes-1d-ma7-shared-parameter-transfer-2026-08-05.md)
- [平多即反手空合同](specs/binance-ma7-long-exit-short-reversal-contract-2026-08-06.md) · [诊断](diagnostics/binance-ma7-long-exit-short-reversal-2026-08-06.md)
- [机器摘要](artifacts/binance_btc_eth_1d_ma7_asset_specific_search_summary_2026-08-05.json)
- [BTC V1交易路径](artifacts/binance_ma7_shared_params_v1_btc_trade_path_2026-08-12.html) · [ETH V1交易路径](artifacts/binance_ma7_shared_params_v1_eth_trade_path_2026-08-12.html)
- [路径渲染脚本](scripts/render_shared_ma7_v1_trade_paths.py)
- [复现脚本](scripts/search_binance_btc_eth_1d_ma7_asset_specific.py)
- [决策记录](decision-log.md)
