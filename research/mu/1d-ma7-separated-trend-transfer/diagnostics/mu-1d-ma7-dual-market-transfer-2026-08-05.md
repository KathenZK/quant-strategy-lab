# MU 日线 MA7 V1 双市场零调参迁移诊断

## 结论

同一套 `HYPE-1D-MA7-Asymmetric-Body-Trend-V1` 参数在 MU 的两个交易合同上给出不同绝对收益，但都没有通过迁移门禁：

- Binance `MUUSDT`：`103d` combined 成本后 `-12.30%`、MDD `-40.16%`、PF `0.68`、4 笔；long-only `+25.29%`，short-only `-15.82%`；
- Nasdaq `MU`：`365d` 零成本 combined `+51.51%`、MDD `-14.49%`、PF `6.12`、6 笔，但 6 笔全部是多头，short-only 没有信号；
- 同期 buy-and-hold 分别为 `+99.35% / +833.45%`，两 route 的 combined 均无超额；
- 共同 `69d` 窗口内，Binance / Nasdaq combined 为 `+15.44% / +47.36%`，仍远低于各自 buy-and-hold 的 `+158.15% / +164.90%`；
- Nasdaq 数据仍是 `raw_unaccepted`，其正收益只能视为 `explore / untrusted`，不能用于版本登记或 promotion。

因此本次只建立 MU transfer diagnostic family，不登记版本、不晋升，也不在已揭示 MU 历史上继续调参。

## 数据与合同

### Binance `MUUSDT`

- 市场：Binance USD-M `TRADIFI_PERPETUAL`，underlying type `EQUITY`；
- normalized `15m` 范围：`2026-04-07 13:30` 至 `2026-07-20 07:00 UTC`，`9,959` 行；
- raw/normalized mismatch、缺 K、重复、critical null、非法 OHLC、未闭合 K 均为 `0`；
- 聚合为 `2,489` 根完整 `1h`，再组成 `103` 个可回测 UTC 日；
- funding：`316` 个真实事件，event-time 结算；
- 成本：手续费 `0.001/fill`、不利滑点 `4 bps/fill`，另审计 `8 bps/fill`；
- stop 使用 `1h` path；主相位 `00:00 UTC`，审计相位 `12:00 UTC`。

### Nasdaq `MU`

- 市场身份：Nasdaq equity `MU`；数据提供方是 Yahoo Finance，不把 Yahoo 当交易所；
- raw 日线范围：`2025-06-16` 至 `2026-06-16`，`252` 个 regular sessions；
- 核心 OHLCV 无 null、重复或非法行；美国交易日历缺失/意外 session 均为 `0`；
- `adj_close` 与 `close` 有 `197` 行细小差异，最大 `23.88 bps`；为保持 OHLC 一致，使用 raw OHLC；
- 仍缺显式 `is_closed/quote_volume/trade_count/vwap`，调整口径未接受，状态为 `raw_unaccepted`；
- 主结果不猜测费用、滑点、借券或融资，按零成本；另做 `10 bps/fill` 示意；
- 只有日 OHLC，stop 可处理 session open gap 和日内触碰，但无法恢复 high/low 先后，也无法做 intraday phase audit。

完整参数与时序见[双市场零调参合同](../specs/mu-1d-ma7-v1-dual-market-transfer-contract-2026-08-05.md)。

## 全可用窗口

| Market / variant | 净收益 | MDD | Sharpe | PF | 交易数 | 成本 / funding |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Binance combined | `-12.30%` | `-40.16%` | `-0.34` | `0.68` | `4` | `1.25% / 4.53%` |
| Binance `8 bps` | `-12.59%` | `-40.33%` | `-0.36` | `0.68` | `4` | `1.61% / 4.53%` |
| Binance + 1 day lag | `-16.96%` | `-43.28%` | `-0.59` | `0.61` | `4` | `1.23% / 4.34%` |
| Binance long-only | `+25.29%` | `-20.21%` | `1.49` | `2.63` | `3` | `1.07% / 4.73%` |
| Binance short-only | `-15.82%` | `-20.63%` | `-1.95` | `0.00` | `2` | `0.56% / -0.18%` |
| Binance buy-and-hold | `+99.35%` | — | — | — | — | `0.44% / 14.15%` |
| Nasdaq combined / long-only | `+51.51%` | `-14.49%` | `1.39` | `6.12` | `6` | 未指定，主结果为零 |
| Nasdaq `10 bps/fill` | `+49.70%` | `-14.66%` | `1.35` | `5.77` | `6` | `1.20%` |
| Nasdaq + 1 session lag | `+47.21%` | `-15.17%` | `1.30` | `10.58` | `7` | 零成本 |
| Nasdaq short-only | `0.00%` | `0.00%` | — | — | `0` | — |
| Nasdaq buy-and-hold | `+833.45%` | — | — | — | — | 零成本 |

Nasdaq 的 combined 与 long-only 完全相同，说明该一年上涨样本没有触发冻结的空头规则。`+51.51%` 是正绝对收益，但只有 `18.73%` 暴露且远落后于该异常强趋势中的 buy-and-hold，不能证明组合机制获得了可迁移超额。

## 共同日历窗口

窗口为 `2026-04-08` 至 `2026-06-16` terminal open：

| Market / variant | 净收益 | MDD | PF | 交易数 | Buy-and-hold |
| --- | ---: | ---: | ---: | ---: | ---: |
| Binance combined | `+15.44%` | `-21.23%` | `2.40` | `2` | `+158.15%` |
| Binance long-only | `+36.52%` | `-17.43%` | — | `2` | — |
| Binance short-only | `-8.75%` | `-13.52%` | `0.00` | `1` | — |
| Nasdaq combined / long-only | `+47.36%` | `-13.69%` | — | `1` | `+164.90%` |
| Nasdaq short-only | `0.00%` | `0.00%` | — | `0` | — |

共同窗口只有 `1–2` 笔闭合交易，不能支持稳定性判断。两条价格路径按同一日历日期对齐后的日收益相关系数为 `0.9467`，期间价格收益约 `+169.44% / +167.50%`；差异主要来自 UTC 24/7 与 regular-session 日界线、funding、成本和信号触发，不应把两个 route 当成重复回测。

## 相位、延迟与稳定性

- Binance combined 在 `0h/12h` 共同窗口分别为 `-12.30% / -11.91%`，方向一致但均亏损；
- Binance long-only 为 `+25.29% / +11.59%`，对相位仍有明显幅度敏感；
- Binance short-only 为 `-15.82% / -14.12%`，两相位都失败；
- Binance 只有 1 个完整滚动 `90d` 窗口：combined `-1.46%`，long-only `+40.79%`，short-only `-8.75%`；
- Nasdaq 10 个滚动 `90d` 窗口中 7 个为正，combined 中位 `+1.14%`、最差 `-6.88%`；short-only 全部无交易；
- Nasdaq 无 intraday 数据，phase/bar-alignment gate 未完成。

延迟与摩擦没有改变 Nasdaq 的正负方向，但样本低、没有空头行为且无超额；Binance combined 本身已经亏损。

## 近期切片

| Market / variant | `1d` | `7d` | `1m` | `3m` | `6m` | `1y` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Binance combined | `0.00%` | `-7.68%` | `-24.03%` | `-12.30%` | 不足 | 不足 |
| Binance long-only | `0.00%` | `-7.68%` | `-12.26%` | `+25.29%` | 不足 | 不足 |
| Binance short-only | `0.00%` | `-7.75%` | `-7.75%` | `-15.82%` | 不足 | 不足 |
| Nasdaq combined / long-only | `0.00%` | `0.00%` | `-5.30%` | `+47.36%` | `+61.75%` | `+51.51%` |
| Nasdaq short-only | `0.00%` | `0.00%` | `0.00%` | `0.00%` | `0.00%` | `0.00%` |

切片分别锚定数据集 terminal open，仅用于 audit，不参与选择。

## 未完成门禁

- Nasdaq equity 数据尚未进入 accepted normalized 层，不能支持登记指标；
- 两 route 都没有 buy-and-hold 超额，交易样本极低；
- Nasdaq 的费用、借券、融资、分红现金流与日内成交顺序未冻结；
- Binance 历史只有约 `3.4` 个月，无法完成 `6m/1y` 近期与长期 regime 审计；
- 来源 V1 的多头首持仓日仍无 hard stop；
- 无 clean prospective OOS、CPCV、完整 stress、runner parity 或线上开平仓对账。

## 决策

1. 记录 Binance combined 失败、long-only 正收益以及 Nasdaq long-only 正绝对收益，均只作为 transfer diagnostic。
2. 不登记 `MU-...-V1`，不晋升，不从同一段 MU 历史中删除空头或搜索新参数。
3. 若继续研究，先把 Nasdaq MU 日线完成 accepted session-aware 数据审计并扩充历史；随后可另立预先冻结的 MU long-only 机制，不能继承本次 post-view 指标为 OOS。

## 证据

- [机器摘要](../artifacts/mu_1d_ma7_dual_market_transfer_summary_2026-08-05.json)
- [窗口指标](../artifacts/mu_1d_ma7_dual_market_transfer_metrics_2026-08-05.csv)
- [近期切片](../artifacts/mu_1d_ma7_dual_market_transfer_recent_2026-08-05.csv)
- [Binance 相位审计](../artifacts/mu_1d_ma7_dual_market_transfer_phase_2026-08-05.csv)
- [滚动 90 日](../artifacts/mu_1d_ma7_dual_market_transfer_rolling_90d_2026-08-05.csv)
- [完整交易](../artifacts/mu_1d_ma7_dual_market_transfer_trades_2026-08-05.csv)
- [双市场日线对齐](../artifacts/mu_1d_ma7_dual_market_transfer_daily_alignment_2026-08-05.csv)
- [Binance 组合路径](../artifacts/mu_1d_ma7_dual_market_transfer_binance_path_2026-08-05.csv)
- [Nasdaq 组合路径](../artifacts/mu_1d_ma7_dual_market_transfer_nasdaq_path_2026-08-05.csv)
- [复现脚本](../scripts/research_mu_1d_ma7_dual_market_transfer.py)
