# Binance-1D-MA7-Asset-Specific-Search Core Ledger

## Family Identity

- Full family name：`Binance-1D-MA7-Asset-Specific-Search`
- Alias：`BIN-1D-MA7-AS-SEARCH`
- Market / symbols / timeframe：Binance USD-M `BTCUSDT`、`ETHUSDT` perpetual，UTC `1d`；`HYPEUSDT` 与美股价格指数只作共享参数 control
- Mechanism：固定 `SMA7/ATR7`，分资产搜索多空 entry / hold / exit，并以最差侧稳健分数选择 BTC/ETH 共享参数。
- Boundary：这是 HYPE 参数直迁失败后的 materially new target-asset search；不回写 `BIN-1D-MA7-ST-XFER` 或 HYPE V1。

## Current State

- Current versions：`V1` 与 `V2` 均 `registered / not promoted / not live-ready`。
- `V2` 身份：P2-C parent，即 V1 shared 参数、仅 long `entry_mode` 改为 `pullback_reclaim`。P2 硬门禁 `20x / MDD≤20%` 仍失败；不 promotion，无 live spec。
- `V2` development：BTC `6.3164x / -52.80%`（117 笔），ETH `6.0161x / -56.76%`（116 笔）。
- `V2` 全样本路径图：BTC `6.9062x / -52.80%`（139 笔），ETH `4.2982x / -56.76%`（135 笔）；含 researcher-exposed audit，不是 clean OOS。
- Runner：无 live spec、无 quant-runner implementation、无 dry-run/live instance。
- Next gate：不进入 live spec。不得在 V2 上继续救参；若再尝试 promotion，须另开新机制并通过全部 hard gates。

## Version Rules

- `V1` 固定为 BTC/ETH shared 参数（long `reclaim`），不包含单资产候选或 HYPE control。
- `V2` 固定为 P2-C parent：V1 shared 参数，仅 long `entry_mode=pullback_reclaim`；short 与 V1 完全相同。P2-E 搜索赢家及其它 P2 探针不是 V2。
- 单资产候选与 shared 参数是不同选择口径；不能把单资产 full 收益并入 `V1`/`V2`。
- 修改 MA 长度、搜索空间、选择目标、资产集合、成本模型或 entry/exit 字段后，必须另开新版本或新合同；只追加同参新窗口 observation 不改版本号。
- “登记/冻结 Vx”与 promotion 必须由用户另行明确请求。

## Version Table

| Observation | Status | Role / Core Idea | Key Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| BTC asset-specific | `explore / not promoted / not live-ready` | BTC development 单独选参 | full `+125.24%`，holdout `+0.06%`，MDD `-19.67%` | [搜索诊断](diagnostics/binance-btc-eth-1d-ma7-asset-specific-search-2026-08-05.md) | holdout 优势消失，不登记 |
| ETH asset-specific | `explore / not promoted / not live-ready` | ETH development 单独选参 | full `+421.94%`，holdout `-8.82%`，`12h=+19.74%` | [搜索诊断](diagnostics/binance-btc-eth-1d-ma7-asset-specific-search-2026-08-05.md) | holdout 失败；相位降低置信度，不登记 |
| `Binance-1D-MA7-Asset-Specific-Search-V1` | `registered / not promoted / not live-ready` | BTC/ETH shared 参数；最大化两资产 development 最差侧 | BTC/ETH full `+112.34%/+161.46%`；HYPE aligned `+48.86%/+55.29%`；HYPE control `-65.15%` | [V1规格](specs/binance-1d-ma7-as-search-v1-spec.md) · [搜索诊断](diagnostics/binance-btc-eth-1d-ma7-asset-specific-search-2026-08-05.md) · [HYPE aligned复算](diagnostics/binance-ma7-shared-params-btc-eth-hype-aligned-2026-08-12.md) · [BTC路径](artifacts/binance_ma7_shared_params_v1_btc_trade_path_2026-08-12.html) · [ETH路径](artifacts/binance_ma7_shared_params_v1_eth_trade_path_2026-08-12.html) | 登记研究身份；不 promotion；HYPE 迁移失败 |
| `Binance-1D-MA7-Asset-Specific-Search-V2` | `registered / HARD-GATE-FAILED / not promoted / not live-ready` | P2-C parent：V1 + long `pullback_reclaim` | development BTC/ETH `6.3164x/-52.80%`、`6.0161x/-56.76%`；全样本路径 `6.9062x` / `4.2982x` | [V2规格](specs/binance-1d-ma7-as-search-v2-spec.md) · [P2-C归因](diagnostics/binance-1d-ma7-p2c-long-pullback-episode-attribution-2026-08-12.md) · [BTC路径](artifacts/binance_1d_ma7_as_search_v2_btc_trade_path_2026-08-17.html) · [ETH路径](artifacts/binance_1d_ma7_as_search_v2_eth_trade_path_2026-08-17.html) | 只固定身份；硬门禁失败；不 promotion |
| Shared → HYPE control | `explore / not promoted / not live-ready` | 共享参数不调参回测 HYPE | combined `-65.15%`，MDD `-73.47%`；fresh aligned `438d` 同为 `-65.15%` | [HYPE control 诊断](diagnostics/binance-ma7-shared-params-on-hype-2026-08-05.md) · [fresh aligned复算](diagnostics/binance-ma7-shared-params-on-hype-fresh-aligned-2026-08-12.md) | 多空均失败；证明共享参数不通用 |
| Shared → US indexes | `explore / not promoted / not live-ready` | 共享参数不调参回测 S&P 500 / Nasdaq Composite | combined `+18.77%/+91.43%`；成本后均负 | [美股指数诊断](../../us-indexes/1d-ma7-shared-parameter-transfer/diagnostics/us-indexes-1d-ma7-shared-parameter-transfer-2026-08-05.md) | long 有部分 edge，short 与成本失败 |
| Long-exit short reversal | `explore / not promoted / not live-ready` | 多头 MA7 迟滞退出时同 open 反手空 | HYPE/BTC/ETH 收益变化 `-0.56/0.00/-22.73pp` | [反手诊断](diagnostics/binance-ma7-long-exit-short-reversal-2026-08-06.md) | 新增反手无正贡献；不采纳 |

## Shared Assumptions

- Data：V1 原搜索为 accepted Binance `1h` 聚合完整 UTC 日 K（development `550d` / holdout `179d`）。V2 使用 DAPML P0 快照，common start `2019-12-24`，development 止于 `2025-08-07` exclusive，terminal `2026-08-10`。
- Search：固定 `SMA7`；V1 每资产每方向 `20,000` 个唯一配置。V2 不是新搜索，只冻结 P2-C 单字段改动。
- Cost：手续费 `0.001/fill`、不利滑点 `4 bps/fill`、实际 event-time funding；压力滑点 `8 bps/fill`。
- Execution：收盘信号次日 open；stop 用真实 `1h` 路径；约 `1x`、单仓、非加仓。
- Evidence role：V1 全部历史已揭示。V2 development 为选择窗；audit/全样本路径为 researcher-exposed，不是 clean OOS。

## Evidence Map

- [冻结搜索合同](specs/binance-btc-eth-1d-ma7-search-contract-2026-08-05.md)
- [V1规格](specs/binance-1d-ma7-as-search-v1-spec.md)
- [V2规格](specs/binance-1d-ma7-as-search-v2-spec.md)
- [P2-C归因](diagnostics/binance-1d-ma7-p2c-long-pullback-episode-attribution-2026-08-12.md)
- [搜索与诊断报告](diagnostics/binance-btc-eth-1d-ma7-asset-specific-search-2026-08-05.md)
- [共享参数应用于 HYPE 诊断](diagnostics/binance-ma7-shared-params-on-hype-2026-08-05.md)
- [共享参数对齐 HYPE fresh 窗口复算](diagnostics/binance-ma7-shared-params-on-hype-fresh-aligned-2026-08-12.md)
- [共享参数在 BTC/ETH 的 HYPE 对齐窗口复算](diagnostics/binance-ma7-shared-params-btc-eth-hype-aligned-2026-08-12.md)
- [共享参数应用于美股指数诊断](../../us-indexes/1d-ma7-shared-parameter-transfer/diagnostics/us-indexes-1d-ma7-shared-parameter-transfer-2026-08-05.md)
- [平多即反手空合同](specs/binance-ma7-long-exit-short-reversal-contract-2026-08-06.md) · [诊断](diagnostics/binance-ma7-long-exit-short-reversal-2026-08-06.md)
- [机器摘要](artifacts/binance_btc_eth_1d_ma7_asset_specific_search_summary_2026-08-05.json)
- [BTC V1交易路径](artifacts/binance_ma7_shared_params_v1_btc_trade_path_2026-08-12.html) · [ETH V1交易路径](artifacts/binance_ma7_shared_params_v1_eth_trade_path_2026-08-12.html)
- [BTC V2交易路径](artifacts/binance_1d_ma7_as_search_v2_btc_trade_path_2026-08-17.html) · [ETH V2交易路径](artifacts/binance_1d_ma7_as_search_v2_eth_trade_path_2026-08-17.html)
- [V1路径渲染脚本](scripts/render_shared_ma7_v1_trade_paths.py)
- [V2路径渲染脚本](scripts/render_binance_1d_ma7_as_search_v2_trade_paths.py)
- [V2机器摘要](artifacts/binance_1d_ma7_as_search_v2_2026-08-17.json)
- [复现脚本](scripts/search_binance_btc_eth_1d_ma7_asset_specific.py)
- [决策记录](decision-log.md)
