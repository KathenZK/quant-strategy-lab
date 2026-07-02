# HYPE-1H-Adaptive-Regime 边界组合严格审计 - 2026-07-01

## 最终结论

`NO-GO / not live-ready / not promoted`。

边界组合 full 年化倍率 `9.73x`，低于 `10.0x`；locked holdout 仅 `5.22x`。虽然 full 胜率 `78.26%`、回撤 `-19.64%` 仍在线内，但三项硬门槛没有同时通过。

更关键的是，这个结果处在回撤边界：基础 holdout DD 已到 `-19.64%`，没有给 stop-market 跳空、成本漂移或状态恢复失败留下安全垫。

## 冻结规则摘要

- `DI-cross` 腿：`+DI14/-DI14` cross，12h EMA regime、RVOL/ADX/ATR/24h momentum/body/funding 过滤；`TP=1.5 ATR14`、`SL=4 ATR14`、`18h` timeout、固定 `3x`。
- `Stoch-reversal` 腿：Stoch(21) K/D 在 `<=25` / `>=60` 区域反转，MACD(8,21,5) turn、ATR/RVOL/ADX/distance 过滤；`SL=4 ATR14`、activation `1 ATR14`、trail `1 ATR14`、`8h` timeout、`24h` cooldown、固定 `2x`。
- 同时触发/持仓重叠时按 prefit 排名确定优先级；单仓，不加仓。
- 费用 `10 bps/fill`、滑点 `4 bps/fill`，逐笔资金费；closed bar 信号，下一根 open 入场。

## 延迟与成本压力

| Scenario | Full ann | Full DD | Full win | Holdout ann | Holdout DD | Pass |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `base_k1` | `9.73x` | `-19.64%` | `78.26%` | `5.22x` | `-19.64%` | `False` |
| `delay_k2` | `2.25x` | `-36.77%` | `68.57%` | `0.18x` | `-36.77%` | `False` |
| `delay_k3` | `1.01x` | `-44.83%` | `55.07%` | `0.10x` | `-44.83%` | `False` |
| `slip_8bps` | `6.11x` | `-33.12%` | `75.36%` | `2.16x` | `-33.12%` | `False` |
| `slip_10bps` | `5.79x` | `-33.41%` | `73.91%` | `2.04x` | `-33.41%` | `False` |
| `fee12_slip8` | `5.71x` | `-33.47%` | `73.91%` | `2.01x` | `-33.47%` | `False` |
| `double_cost` | `4.36x` | `-34.84%` | `71.01%` | `1.53x` | `-34.84%` | `False` |
| `exposure_075x` | `5.63x` | `-14.98%` | `78.26%` | `3.50x` | `-14.98%` | `False` |
| `exposure_050x` | `3.21x` | `-10.15%` | `78.26%` | `2.33x` | `-10.15%` | `False` |
| `exposure_125x` | `16.63x` | `-24.15%` | `78.26%` | `7.70x` | `-24.15%` | `False` |

## 消融与邻域

- 单腿拆分及所有 active-field one-at-a-time variants 共 `164` 行；完整 target pass 为 `0`。
- 这些变体在 holdout 解锁后只作脆弱性诊断，不用于回头挑参数。

## 月度与 bootstrap

- 月度块 `13` 个，负收益月 `1` 个。
- 交易序列 bootstrap `10,000` 次：annual 5/50/95 分位 `5.90x / 11.89x / 24.32x`；DD 5% 分位 `-23.00%`；完整形状命中率 `58.48%`。
- bootstrap 只重排/重采样已发生交易，不能替代新的时间外市场，因此不用于 promotion。

## 实盘可执行审计

- 合约 tick `0.00100`、qty step `0.01`、min notional `5 USDT`；最大名义暴露 `3.0x`。
- 历史信号最大初始 stop 距离约 `1589.7 bps`；超过 `15%` 的次数 `1`。
- backtest 已处理 stop gap-open、同 K stop-first、trailing 仅闭合 K 更新；这些是必要条件，不等于生产系统已完成。
- 当前没有 production runner、重启恢复、交易所订单/仓位对账、missing-bar fail-closed、kill switch 和真实 stop-market 滑点证据。

因此即使把 full `9.73x` 四舍五入成 `10x`，也不能实盘：精确门槛未过，holdout 未过，风险缓冲不足，生产状态机也不存在。
