# HYPE-1H-Multi-Mechanism-Trend-Following-V1 原始基线规格

## 身份与状态

- Family：`HYPE-1H-Multi-Mechanism-Trend-Following`
- Version：`HYPE-1H-Multi-Mechanism-Trend-Following-V1`
- Status：`registered diagnostic baseline / not promoted / not live-ready`
- Role：广搜后冻结的原始可执行边界；locked OOS 未揭示。

## 数据与执行合同

- Selection data：`[2025-05-30 10:00 UTC, 2026-04-22 10:00 UTC)`；最近三个月 locked OOS 不参与选择。
- 闭合 `1h` K 生成信号，下一根 open 成交；单净仓，无同向加仓。
- fee `0.001/fill`、slippage `4 bps/fill`、逐 bar 对齐真实 funding。
- stop-first；stop gap 按 bar open，其他 stop/TP 按冻结价并施加不利滑点。
- 固定 leverage `2.0x`，不超过目标上限 `3x`。

## 冻结规则与参数

- 机制：双向 time-series momentum。`close[t] - close[t-120]` 以 `ATR48` 归一化；上穿 `+2.0 ATR` 做多、下穿 `-2.0 ATR` 做空。
- regime：方向与 `EMA96/EMA120` 排列一致。
- 过滤：`ADX14 >= 10`；`volume / prior rolling-median(volume,48) >= 0.75`。
- 入场：信号闭合后的下一根 open，adverse slippage 后成交。
- 初始止损：`4.0 ATR48`；止盈：`1.5 ATR48`。
- trailing：浮盈达到 `0.75 ATR` 后，以有利极值回撤 `2.5 ATR` 更新下一根生效的 stop。
- breakeven：浮盈达到 `1.5 ATR` 后将 stop 收至 raw entry。
- 最大持仓 `168h`；出场后 cooldown `24h`；trend-exit disabled。
- 配置 SHA256：`68da56723b2161488dcb093ad34928e98503415cd05b3a40f0e434d17ee12c8e`。

## 冻结选择指标

| Window | Annual factor | Total return | MDD | Win rate | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Prefit | `4.8034x` | `+307.55%` | `20.04%` | `82.26%` | `62` | `3.036` |
| Internal validation 90d | `10.3214x` | `+77.74%` | `9.72%` | `87.50%` | `16` | `7.515` |

V1 未达到 `>=20x`，且 prefit MDD 未严格小于 `20%`；登记只固定身份，不授权 promotion。
