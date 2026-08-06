# MU Research

本页是 MU 单资产研究路由。覆盖 Binance USD-M `MUUSDT` `TRADIFI_PERPETUAL` 与 Nasdaq `MU` equity；不同机制或执行合同必须明确隔离，不得互相继承版本或指标。

| Full family name | Alias | Directory | 机制 | 状态 |
| --- | --- | --- | --- | --- |
| `MU-HYPE-Transfer` | `MU-HYPE-XFER` | [扁平历史家族](mu-hype-xfer-session-aware-ledger.md) | HYPE V35/V6 风格 EMA 趋势迁移、时段与仓位实验 | `explore / not promoted / not live-ready`；V14 前向未确认 |
| `MU-15M-Donchian-Trend-Breakout` | `MU-15M-DTB` | [家族目录](15m-donchian-trend-breakout/README.md) · [主账](15m-donchian-trend-breakout/mu-15m-dtb-core-ledger.md) | EMA regime + Donchian 收盘突破 + ATR/trailing exit | final audit 未通过、停止扩搜 / `explore / not promoted / not live-ready` |
| `MU-1D-MA7-Separated-Trend-Transfer` | `MU-1D-MA7-ST-XFER` | [家族目录](1d-ma7-separated-trend-transfer/README.md) · [主账](1d-ma7-separated-trend-transfer/mu-1d-ma7-st-xfer-core-ledger.md) | HYPE 日线 V1 固定 SMA7 多空状态机迁移至 Binance perpetual / Nasdaq equity | Binance combined 失败；Nasdaq 仅多头正收益且数据未接受 / `explore / not promoted / not live-ready` |

历史迁移入口：

- [决策日志](decision-log.md)
- [V14 最新数据有效性诊断](diagnostics/mu-hype-xfer-v14-latest-validity-2026-07-20.md)
- [历史迁移报告](legacy-canvas/README.md)
- [历史研究脚本](scripts/README.md)

股票现货交叉验证数据已从旧 `data/external/us_equities` 迁入统一 raw OHLCV，
按 `exchange=nasdaq / market_type=equity / source=polygon_api|yahoo_finance`
隔离。数据湖规范见 [`../../docs/data-lake-spec.md`](../../docs/data-lake-spec.md)，迁移与质量结论见
[`mu-equity-ohlcv-migration-2026-08-05.md`](diagnostics/mu-equity-ohlcv-migration-2026-08-05.md)。
这些数据当前为 `raw_unaccepted`，不能作为新版本登记或 promotion 证据。
