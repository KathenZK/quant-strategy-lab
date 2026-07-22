# MU Research

本页是 MU 单资产研究路由。市场为 Binance USD-M `MUUSDT` `TRADIFI_PERPETUAL`；不同机制必须分家族维护，不得因同为 `15m` 趋势研究而互相继承版本或指标。

| Full family name | Alias | Directory | 机制 | 状态 |
| --- | --- | --- | --- | --- |
| `MU-HYPE-Transfer` | `MU-HYPE-XFER` | [扁平历史家族](mu-hype-xfer-session-aware-ledger.md) | HYPE V35/V6 风格 EMA 趋势迁移、时段与仓位实验 | `explore / not promoted / not live-ready`；V14 前向未确认 |
| `MU-15M-Donchian-Trend-Breakout` | `MU-15M-DTB` | [家族目录](15m-donchian-trend-breakout/README.md) · [主账](15m-donchian-trend-breakout/mu-15m-dtb-core-ledger.md) | EMA regime + Donchian 收盘突破 + ATR/trailing exit | final audit 未通过、停止扩搜 / `explore / not promoted / not live-ready` |

历史迁移入口：

- [决策日志](decision-log.md)
- [V14 最新数据有效性诊断](diagnostics/mu-hype-xfer-v14-latest-validity-2026-07-20.md)
- [历史迁移报告](legacy-canvas/README.md)
- [历史研究脚本](scripts/README.md)
