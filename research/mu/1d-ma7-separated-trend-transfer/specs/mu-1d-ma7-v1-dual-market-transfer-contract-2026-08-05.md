# MU 日线 MA7 V1 双市场零调参迁移合同

## 身份

- 来源版本：[`HYPE-1D-MA7-Asymmetric-Body-Trend-V1`](../../../hype/1d-ma7-asymmetric-body-trend/specs/hype-1d-ma7-abt-v1-spec.md)
- 目标家族：`MU-1D-MA7-Separated-Trend-Transfer`
- 性质：direct transfer diagnostic；不登记 MU 版本
- 仓位：每次入场目标约 `1x`，成交后数量固定，单仓、非加仓

## 两个独立市场合同

### Binance route

- Exchange / market / symbol：Binance USD-M / `TRADIFI_PERPETUAL` / `MUUSDT`
- 输入：accepted normalized `15m` OHLCV，先聚合完整 `1h`，再聚合正好 24 根小时 K 的 UTC 日 K
- 主日界线：`00:00 UTC`；phase audit：`12:00 UTC`
- 执行：收盘信号最早次日 open；空头 open 条件观察后在下一根 `1h` open 成交
- Stop：用真实 `1h` open/high/low；gap 穿越 stop 时按小时 open 成交，否则按 stop 价加滑点
- 成本：手续费 `0.001/fill`，不利滑点 `4 bps/fill`；压力测试 `8 bps/fill`
- Funding：只结算实际持仓覆盖的 Binance event-time funding

### Nasdaq route

- Exchange / market / symbol / source：Nasdaq / equity / `MU` / Yahoo Finance
- 输入：regular-session raw `1d` OHLC；当前 `quality_status=raw_unaccepted`
- 日界线：America/New_York regular session provider 日 K
- 执行：收盘信号次交易 session open；open gap 穿越 stop 时按 open 成交，日 high/low 触发时按 stop 价
- 主成本：零手续费、零滑点，因为用户未指定；另做 `10 bps/fill` 示意压力测试
- 未建模：股票借券可得性/费率、融资、分红现金流、税费与精确 session 内 stop 顺序
- Phase：只有日线，无法完成 intraday bar-alignment audit

## 固定指标

- `SMA7_t = mean(close[t-6:t])`
- `TR_t = max(high-low, |high-close[t-1]|, |low-close[t-1]|)`
- `ATR7_t = mean(TR[t-6:t])`
- 所有 close / MA / ATR 信号只使用当时已闭合的日 K。

## 固定多头

| 参数 | 值 |
| --- | ---: |
| `entry_mode` | `reclaim` |
| `slope_lookback` / `slope_min_atr` | `1` / `0.02` |
| `confirm_days` / `entry_buffer_atr` | `1` / `0.0` |
| `exit_confirm_days` / `exit_buffer_atr` | `1` / `0.75` |
| `hard_stop_atr` / `trail_atr` | `0.0` / `1.5` |
| `max_hold_days` / `cooldown_days` | `90` / `2` |

多头在价格由下向上 reclaim SMA7 且斜率确认后，于下一可执行 open 入场；持仓按 SMA7 下方 ATR 迟滞退出、`1.5 ATR` trailing stop 或最长 90 日退出。首持仓日没有独立 hard stop，此缺口原样保留。

## 固定空头

| 参数 | 值 |
| --- | ---: |
| `entry_mode` | `reclaim` |
| `slope_lookback` / `slope_min_atr` | `2` / `0.02` |
| `confirm_days` / `entry_buffer_atr` | `1` / `0.1` |
| `exit_confirm_days` / `exit_buffer_atr` | `1` / `0.25` |
| `slope_exit_lookback` | `1` |
| `hard_stop_atr` / `trail_atr` | `1.5` / `4.0` |
| `max_hold_days` / `cooldown_days` | `20` / `5` |

空头在价格向下 reclaim SMA7、均线斜率与 `0.1 ATR` buffer 满足后入场；持仓按 SMA7 上方迟滞、斜率反转、`1.5 ATR` hard stop、`4 ATR` trailing 或 20 日上限退出。

## 固定审计

- 两 route：full available、共同日历窗口、combined / long-only / short-only、额外一日/session 延迟、近期 `1d/7d/1m/3m/6m/1y`（数据长度不足则不报）、滚动 `90d`。
- Binance：`0h/12h` phase、`8 bps` slippage、真实 funding。
- Nasdaq：`10 bps/fill` 示意摩擦；记录数据接受 blocker，不把普通加载成功当成可信通过。
- 共同窗口结果按各自真实交易合同计算；不把 Binance funding 或 24/7 K 线套到 Nasdaq route。
