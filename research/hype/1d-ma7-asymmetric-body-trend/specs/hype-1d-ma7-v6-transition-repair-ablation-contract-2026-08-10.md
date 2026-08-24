# HYPE-1D-MA7-ABT V6 转换链修复消融合同（2026-08-10）

## 1. 研究问题与边界

本轮只回答：在不修改 `HYPE-1D-MA7-Asymmetric-Body-Trend-V6` 身份的前提下，修复其自然入场转换链中的七个已知问题，是否能在同一份全历史上同时提高收益、降低回撤，并改善慢涨/阴跌趋势的持续识别。

七个问题固定为：

1. 删除统一的全局 cooldown；
2. 改为同方向 `1d/2d` cooldown，合格反向信号不受阻；
3. raw MA7 cross 建立有限 `3d/5d` episode，不因 fresh cross 次日失效；
4. entry buffer 与 slope 可以在 cross 后 episode 内成熟；
5. episode 发生反向 recross 时立即取消；
6. short RSI6 止盈后不机械锁死 `5d`，改为同趋势重新观察；
7. 延迟确认必须有 anti-chase 上限。

V6、V5、PEHC、OAPP 与 exact V4 的冻结文件均不修改。本轮是 V6 上的独立 diagnostic overlay，不登记 V7，不触发 promotion、runner handoff 或杠杆研究。

## 2. 数据、窗口与执行

- 市场：Binance USD-M `HYPEUSDT` perpetual。
- bar：完整 UTC `1d`，决策只使用已闭合日线；成交使用下一可执行真实 `1h` open。
- 全历史：连续 `[0,432)`，432 个完整 UTC 日；本轮全窗已经 researcher-exposed。
- 冷启动稳定性：`8 × 54d` cold-flat block；每块仅预热指标，仓位、pending、cooldown、episode 与 RSI reobserve 状态全部重置。
- 成本：沿用 frozen V6，fee `10bps/fill`、基础 adverse slippage `4bps/fill`、funding 启用；压力只把 slippage 提至 `8bps/fill`。
- 回撤主口径：真实 `1h` chronological MDD；同时保留日极值 MDD 供审计。
- 近期审计：以数据尾部锚定 `1d/7d/1m/3m/6m/1y`，不用于选择。
- 无任何未揭示 OOS；所有结果只能作为 post-reveal 机制证据。

## 3. 精确状态机

### 3.1 cooldown

退出发生在日索引 `i` 时：

- `GLOBAL_BASE`：保持 V6 原始全局 cooldown，long 退出后阻断后续 `2` 个日开盘，short 退出后阻断后续 `5` 个日开盘；
- `NONE`：自然 long/short 均无 cooldown；forced reversal 与 PEHC 原时序不变；
- `DIRECTIONAL_1/2`：只阻断相同方向后续 `1/2` 个日开盘，合格反方向自然信号绕过；
- 无论是否被 cooldown 阻断，flat 状态下都每日更新 cross episode 与 RSI reobserve 观察；cooldown 只阻止成交，不删除信号状态。

同一日若 long 与 short 同时合格，保持 V6 的 long-first 优先级。PEHC handoff 与 frozen forced reversal 仍优先于自然入场。

### 3.2 raw-cross episode

- long raw cross：`close[t-1] <= MA7[t-1]` 且 `close[t] > MA7[t]`；
- short raw cross：`close[t-1] >= MA7[t-1]` 且 `close[t] < MA7[t]`；
- episode 只在 exact V6 native entry 当日没有已经触发时建立；
- episode age 为当前 signal index 减 raw-cross index，最早 `age=1` 才能确认；
- 有限寿命取 `3d/5d`，超过寿命取消；
- recross cancel ON 时，long 的 `close <= MA7`、short 的 `close >= MA7` 立即取消；OFF 只作为反事实消融，不作为建议实现。

### 3.3 延迟成熟

沿用 V6 两侧原生阈值：

- long：`distance=(close-MA7)/ATR7 > 0`；`1d MA7 slope/ATR7 > 0.02`；
- short：`distance=(MA7-close)/ATR7 > 0.10`；`2d down-slope/ATR7 > 0.02`；
- `BUFFER_MATURE`：cross 日允许 buffer 未通过，episode 内以后通过；slope 必须在 cross 日已通过；
- `SLOPE_MATURE`：cross 日允许 slope 未通过，episode 内以后通过；buffer 必须在 cross 日已通过；
- `BOTH_MATURE`：两者均可在 episode 内以后通过；确认日两者必须同时严格通过；
- 所有延迟确认还需 `distance < anti_chase_cap_atr`，上限比较严格 `<`。

### 3.4 short RSI6 同趋势 reobserve

仅在实际退出原因是 `short_rsi_take_profit` 时启动：

1. 只要 `close < MA7`，观察保持有效，最多 `5d`；若 `close >= MA7` 或到期则取消；
2. RSI6 必须先恢复到 `>= reset_threshold`，测试 `20/30`；
3. 恢复后的下一根或以后，若 `close < prior_close`、short 原生 `2d down-slope/ATR7 > 0.02`、`distance > 0.10ATR` 且低于 anti-chase cap，则下一日开盘重新做空；
4. 不允许 RSI6 尚未恢复时原地平空再开空，避免把止盈退化为无效换手；
5. native fresh entry、episode entry 或 PEHC handoff先成交时，reobserve 状态清除。

## 4. 冻结实验矩阵

### 4.1 七项逐项消融

- `A0 EXACT_V6`
- `A1 NO_GLOBAL_COOLDOWN`
- `A2 DIRECTIONAL_CD_1D`
- `A2B DIRECTIONAL_CD_2D`
- `A3 RAW_EPISODE_5D`（episode 建立，但 buffer/slope 不允许延迟成熟，用于识别 dormant wiring）
- `A4 BUFFER_MATURE_5D`
- `A4B SLOPE_MATURE_5D`
- `A4C BOTH_MATURE_5D`
- `A5 BOTH_MATURE_NO_RECROSS_CANCEL`
- `A6 RSI_REOBSERVE_R20`
- `A6B RSI_REOBSERVE_R30`
- `A7 BOTH_MATURE_CAP_INF/1.50/1.00/0.75`

### 4.2 低复杂度组合

仅组合以下冻结网格，不做自适应救援：

- directional cooldown：`1d/2d`；
- episode age：`3d/5d`；
- maturity：`BUFFER/SLOPE/BOTH`；
- anti-chase cap：`0.75/1.00/1.50ATR`；
- RSI reobserve：`OFF/R20/R30`；
- recross cancel 固定 ON。

共 `2 × 2 × 3 × 3 × 3 = 108` 个组合。逐项结果揭示后不得扩参数网格；若所有组合失败，直接复盘而非继续阈值救援。

## 5. 比较与裁决

每个 arm 对 exact V6 同窗报告：全历史累计收益、折算年化、chronological `1h` MDD、交易数、多空笔数、胜率、profit factor、成本、8bps压力、8块 cold-flat 复合收益/最差块 MDD、近期分片、激活次数及逐笔新增/删除。

“变好”必须同时满足：

1. 全历史累计收益严格高于 V6；
2. 全历史 chronological `1h` MDD 严格小于 V6（数值更接近 0）；
3. 8bps 不双劣；
4. `8 × 54d` cold-flat 复合收益与最差块 MDD不双劣；
5. 至少两个新增/改变的经济交易事件，且不破产；
6. V6 的 OAPP long exit、RSI6 short TP 与 PEHC handoff 仍有可审计接线。

即使满足以上条件，也只记为 `POST-REVEAL DIAGNOSTIC PASS`，不登记版本、不宣称 OOS、不具备上线资格。若没有 arm 同时提高收益和降低回撤，结论为 `HARD-GATE-FAILED`。
