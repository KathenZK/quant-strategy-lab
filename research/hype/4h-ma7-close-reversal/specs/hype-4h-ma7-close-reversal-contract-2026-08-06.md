# HYPE 4H MA7 收盘反手合同（2026-08-06）

## 身份

- Family：`HYPE-4H-MA7-Close-Reversal`。
- Alias：`HYPE-4H-MA7-CR`。
- 市场：Binance USD-M `HYPEUSDT` perpetual。
- 周期：UTC `4h`。
- 状态：`explore / not promoted / not live-ready`。
- 机制边界：单根 `SMA7` 的收盘上下方状态决定下一根开盘目标方向；始终持有多仓或空仓并在信号翻转时直接反手。
- 防串线：不是 `HYPE-4H-MA7-Asymmetric-Body-Trend` 的 reclaim / slope / ATR 参数分支，也不继承日线 V1。

## 冻结规则

1. `SMA7[t] = mean(close[t-6:t])`，只使用已经闭合的七根 `4h`。
2. 若 `close[t] > SMA7[t]`，则下一根 `4h` open 的目标仓位为 `+1x`。
3. 若 `close[t] < SMA7[t]`，则下一根 `4h` open 的目标仓位为 `-1x`。
4. 若相等或指标未 warmup，保持当前仓位；warmup 期间为空仓。
5. 第一个有效信号后进入多仓或空仓，此后除 terminal flatten 外不主动空仓。
6. 方向翻转时在同一根下一期开盘先平旧仓、再开反向仓；按两次 fill 计费和滑点。
7. 成交后按权益建立约 `1x` 目标仓位；持仓期间数量固定，到下一次反手才重新计算。
8. 无 buffer、无连续 K 确认、无 ATR stop、无 trailing stop、无 cooldown、无 max hold。

## 数据与执行

- 从标准数据湖已接受的连续闭合 `1h` K 聚合；每根 `4h` 必须恰由四根连续 `1h` 组成。
- 仅使用收盘已知的信号，最早下一根 `4h` open 成交；不使用图中事后可见的盘中穿越。
- 手续费 `0.001/fill`，基准不利滑点 `4 bps/fill`，压力 `8 bps/fill`。
- funding 使用 Binance 实际事件时间和费率，以事件小时 open 近似名义，只在持仓期间结算。
- terminal open 强制平仓并计一次 fill。
- 策略没有交易所驻留保护单；即使收益为正，这也是 `not live-ready` blocker。

## 审计

- 全期基准、`8 bps/fill`、额外延迟一根 `4h`；
- `fee=0/slippage=0` 且保留实际 funding 的 gross 解释项，只用于区分信号与交易成本，不参与可交易性判定；
- 前段与从数据终点精确回推 `120d` 的 flat-start 时间切片；它们只作审计，不参与选择，也不是 clean OOS；
- 最近 `1d/7d/1m/3m/6m/1y`；
- `90d` 窗口、`30d` 步长；
- 从真实 `1h` 重聚合 `0h/1h/2h/3h` 四个可用相位；
- long-only（MA7 上方持多、下方空仓）与 short-only（MA7 下方持空、上方空仓）诊断；
- 同成本和 funding 的 `1x` buy-and-hold。

## 判定纪律

- 本轮没有可搜索参数，不能根据结果增加 buffer、确认、stop 或选择单腿。
- 全历史已经被研究者查看，任何正收益只构成历史观察。
- 高频反手导致的 turnover、成本、相位或延迟失败必须原样记录。
- 不登记版本、不创建 live spec、不推进 runner；后续变体必须另行预冻结。
- 小时内 high/low 先后顺序未知，路径 MDD 使用同小时 favorable-to-adverse 的保守 envelope，不宣称为逐笔真实路径。
