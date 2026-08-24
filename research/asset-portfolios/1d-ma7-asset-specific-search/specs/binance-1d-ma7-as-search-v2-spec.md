# Binance-1D-MA7-Asset-Specific-Search V2 规格

## 身份与证据角色

- Family：`Binance-1D-MA7-Asset-Specific-Search`
- Version：`V2`
- Alias：`BIN-1D-MA7-AS-SEARCH-V2`
- 状态：`registered / HARD-GATE-FAILED / not promoted / not live-ready`
- 市场/周期：Binance USD-M `BTCUSDT`、`ETHUSDT` perpetual；日线信号、真实 `1h` 路径执行
- 登记日期：`2026-08-17`
- 身份：P2-C parent。相对 V1 只改 long `entry_mode: reclaim → pullback_reclaim`；其余 long 字段、完整 short、成本、funding、仓位与执行时序与 V1 相同
- 证据角色：development 是冻结选择窗；audit / 全样本路径图为 researcher-exposed，不是 clean OOS，不构成 promotion

V2 的登记只固定策略身份和参数。P2 的 `20x / MDD≤20%` 硬门禁失败不变；本规格不授权 live spec、runner handoff、dry-run 或 live。P2-E 搜索赢家及其它 P2 探针不是本版本。

## 冻结参数

| Field | Long | Short |
| --- | ---: | ---: |
| `side` | `1` | `-1` |
| `entry_mode` | `pullback_reclaim` | `pullback_reclaim` |
| `slope_lookback` | `5` | `5` |
| `slope_min_atr` | `0.0` | `0.0` |
| `confirm_days` | `1` | `1` |
| `entry_buffer_atr` | `0.25` | `0.1` |
| `pullback_lookback` | `10` | `5` |
| `pullback_touch_atr` | `0.1` | `-0.5` |
| `breakout_lookback` | `7` | `10` |
| `exit_confirm_days` | `2` | `2` |
| `exit_buffer_atr` | `1.0` | `0.75` |
| `slope_exit_lookback` | `5` | `0` |
| `hard_stop_atr` | `0.0` | `1.5` |
| `trail_atr` | `0.0` | `5.0` |
| `max_hold_days` | `0` | `10` |
| `cooldown_days` | `0` | `2` |

## 信号与执行

- Indicator：`SMA7` / `ATR7` 使用闭合 UTC 日 K。
- Entry：闭合日 `t` 识别信号，下一 UTC 日 open 执行。多空均为 `pullback_reclaim`：先回到均线另一侧/触及回撤带，再重新穿越入场带。
- Exit：日线 MA7 迟滞、斜率退出、short hard stop / trailing / max hold 按冻结 engine 执行；stop 使用真实 `1h` 路径。
- 仓位：约 `1x`、单仓、非加仓；long / short 共用账户权益，同开盘 dual fire 时 long 优先。
- 成本：fee `0.001/fill`，base / stress 滑点 `4 / 8 bps/fill`。
- Funding：Binance fundingRate event-time，按持仓方向计入真实现金流。
- Terminal：`2026-08-10T00:00:00Z` open 强制平仓。

## 数据边界

- 冻结 P0 快照：[`p0_data_quality_manifest.json`](../../1d-ma7-rsi6-direction-aligned-pooled-ml/artifacts/p0_data_2026-08-10/p0_data_quality_manifest.json)
- Development（选择窗）：`[2019-12-24, 2025-08-07)`
- Researcher-exposed audit：`[2025-08-07, 2026-08-10)`；本次登记为画全样本路径而读取，仍不是 clean OOS
- Prospective 未读取

## 冻结指标

### Development（V2 身份窗口）

| 场景 | BTC combined | ETH combined |
| --- | ---: | ---: |
| Base | `6.3164x` / `-52.80%` / 117 笔（76L/41S） | `6.0161x` / `-56.76%` / 116 笔（76L/40S） |
| Stress `8bps` | `5.7532x` / `-53.04%` | `5.4816x` / `-57.26%` |
| Delay `+1d` | `2.1373x` / `-74.91%` | `4.6152x` / `-60.60%` |

两资产均未达到 `20x` 或 `MDD≤20%`。

### 全样本路径图窗口（含 audit）

窗口：`2019-12-24` 至 terminal open `2026-08-10`。HTML 交易笔数与此表 `closed_trades` 一致。

| 资产 | Equity multiple | Net | MDD | Trades |
| --- | ---: | ---: | ---: | ---: |
| `BTCUSDT` | `6.9062x` | `+590.62%` | `-52.80%` | `139`（90L/49S） |
| `ETHUSDT` | `4.2982x` | `+329.82%` | `-56.76%` | `135`（89L/46S） |

Audit 单独重启：BTC `+9.34% / -21.59%`（22 笔），ETH `-28.56% / -51.05%`（19 笔）。

### 近期切片（全样本终点锚定、窗口内重启）

切片只作审计，不参与选参。

| 切片 | BTC | ETH |
| --- | ---: | ---: |
| `1d` | `-0.39% / -1.20%` | `-0.63% / -1.61%` |
| `7d` | `-0.34% / -1.20%` | `-0.63% / -1.61%` |
| `1m` | `-1.25% / -6.47%` | `+0.33% / -10.39%` |
| `3m` | `-1.02% / -11.07%` | `-1.19% / -12.09%` |
| `6m` | `-2.33% / -21.59%` | `+0.17% / -17.13%` |
| `1y` | `+9.34% / -21.59%` | `-32.73% / -51.04%` |

## 决策边界

- V2 只登记 BTC/ETH shared P2-C parent 身份；不能把 P2-E 或单资产候选并入本版本。
- 改动任一 entry/exit 字段、成本模型、资产集合或执行时序后都不再是 V2。
- 当前最大风险是 development 内约 `-53% / -57%` 的账户回撤，以及 ETH 近一年重启亏损。不得在 V2 上继续加 stop/filter 救参。
- Promotion 前仍缺 clean prospective OOS、CPCV/robustness review、runner parity、实盘执行时序审计和线上开平仓对账。

## 证据

- [主账](../binance-1d-ma7-as-search-core-ledger.md)
- [P2-C 归因](../diagnostics/binance-1d-ma7-p2c-long-pullback-episode-attribution-2026-08-12.md)
- [BTC V2交易路径](../artifacts/binance_1d_ma7_as_search_v2_btc_trade_path_2026-08-17.html)
- [ETH V2交易路径](../artifacts/binance_1d_ma7_as_search_v2_eth_trade_path_2026-08-17.html)
- [机器摘要](../artifacts/binance_1d_ma7_as_search_v2_2026-08-17.json)
- [路径渲染脚本](../scripts/render_binance_1d_ma7_as_search_v2_trade_paths.py)
