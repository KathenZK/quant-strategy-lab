# HYPE-1D-MA7-SNC02 MA05 试仓与确认扩仓 Stage B 冻结合同

> 冻结日期：2026-08-20。状态：`diagnostic-only / explore / not promoted / not live-ready`。本合同在首次运行 Stage B 结果前写入；结果揭示后不得修改臂、确认条件或门槛并重称预注册结果。

## 1. 研究问题与边界

Stage A 已揭示：固定 `MA05` 结构退出把 SNC02 扩展窗净收益从 `+32.56%` 提高到 `+148.79%`，真实 1h 最大回撤从 `-50.79%` 降到 `-33.61%`，但仍未满足 `20%` 回撤门槛。剩余最大回撤由 2026-02 至 2026-05 多次新 cross 后的反复亏损共同造成，因此 Stage B 只研究入场风险暴露，不再修改：

- SNC02：镜像 `fresh SMA7 cross + directional SMA7 slope >= 0.02ATR7`；
- `MA05`：long 在 `close < SMA7 - 0.5ATR7` 且 SMA7 单日 slope `<=0` 时下一 UTC open 全平，short 镜像；
- `SMA7/ATR7`、成本、funding、数据窗口及 V7.1 身份。

所有历史均已揭示，本轮只能作机制诊断；不登记版本、不 promotion、不修改 runner。Stage B 不叠加 Stage A 的 BE、部分止盈、固定小时止损或其他退出层。

## 2. 固定实验臂

| Arm | 初始目标风险 | 确认后目标风险 | 连续确认日 |
|---|---:|---:|---:|
| `MA05_1X` | 1.00x | 不扩仓 | 0 |
| `MA05_FIXED75` | 0.75x | 不扩仓 | 0 |
| `MA05_FIXED50` | 0.50x | 不扩仓 | 0 |
| `MA05_P50_C1` | 0.50x | 1.00x | 1 |
| `MA05_P50_C2` | 0.50x | 1.00x | 2 |
| `MA05_P25_C2` | 0.25x | 1.00x | 2 |

固定降仓臂只是风险缩放参照，不视为创造新 alpha。动态臂只能在开仓后由下面的统一确认状态扩到 `1x`，每笔最多一次；不得分级多次加仓。

## 3. 冻结确认条件

对持仓方向记 `s=+1`（long）或 `s=-1`（short）。每个完整 UTC 日收盘后，以下三项必须同时成立，才记作一个确认日：

1. `s * (close - entry_price) > 0`：相对本 campaign 初始开仓价已有方向性浮盈；
2. `s * (close - SMA7) >= 0`：收盘仍在趋势侧；
3. `s * (SMA7[t] - SMA7[t-1]) / ATR7[t] >= 0.02`：均线方向和 SNC02 入场斜率门槛一致。

若任一项失败，连续确认计数立即归零。达到 arm 的 `C1/C2` 后，下一 UTC open 将当前仓位按当时权益和执行成本调到 `1x`；扩仓不是用旧权益或旧数量机械翻倍。

## 4. 事件优先级与成交

1. 日线收盘后若出现与当前仓位相反的 SNC02 合格信号，下一 UTC open 先平旧仓，再按新 arm 的**初始目标风险**开反向仓；该事件优先于 `MA05` 和扩仓。
2. 无反向合格信号时，`MA05` 全平优先于扩仓；结构已经失效时不得先加仓。
3. flat 时只有新的 SNC02 fresh qualified signal 才能入场；`MA05` 平仓后不自动重入，不保留 stale pending。
4. 日线动作额外 `1d lag` 压力下，信号入场、反手、`MA05` 平仓和确认扩仓统一再延迟一个完整日；已有 pending 时忽略后续日线动作，直至该动作成交。
5. 所有成交发生在 Binance HYPEUSDT perpetual 下一 UTC 日 open，手续费、滑点和实际 turnover 逐笔计入；funding 按原始事件时点计入。

## 5. 数据、成本与窗口

- 市场：Binance USDⓈ-M perpetual `HYPEUSDT`；信号与确认 `1d`，风险路径 `1h`，UTC。
- 主窗：扩展数据 `2025-05-31 -> 2026-08-20 terminal`；同时报告 canonical `2025-05-31 -> 2026-08-06`。
- 成本：手续费 `0.001/fill`，基础滑点 `4bps/fill`，实际 funding；压力为 `8bps`、funding-off、额外 `1d lag`。
- 最近 flat-start：`1d/7d/1m/3m/6m/1y`；年度 flat-start：2025 partial、2026 YTD。
- 风险：按小时 open、funding pre/post、entry/exit/promotion 成交顺序计算 chronological `1h` MDD；不得用逐笔或日收盘 MDD 替代。

## 6. 首次运行前冻结的判定

以 exact `MA05_1X` 的扩展窗和 2026-08-09 最新 long 为参照。每个 arm 报告净收益、真实 1h MDD、胜率、PF、成本、funding、暴露、最大实际杠杆、扩仓次数、多空贡献、最近趋势捕获和压力结果。

- `MDD20_PASS`：扩展窗 chronological `1h MDD >= -20%`。
- `ROBUSTNESS_PASS`：扩展窗净收益 `>0`、PF `>=1`、`8bps`净收益 `>0`、额外 `1d lag`净收益 `>0`。
- `RETURN_RETENTION_PASS`：扩展窗净收益至少为 `MA05_1X` 的 `50%`。
- `LATEST_TREND_CAPTURE_PASS`：存在 2026-08-09 long、截至 terminal 仍持有（统一以 `terminal_flatten` 截面估值），且其 campaign 净收益至少为 `MA05_1X` 同笔的 `60%`。terminal flatten 不视为成熟止盈。
- `CONTINUATION_CANDIDATE`：同时满足上述四项。

任一候选即使通过也仍是 `post-reveal diagnostic`，不能据此登记或上线。若仅固定降仓臂通过，只能说明风险缩放足以压低回撤；不得表述为新增 alpha 或最终止盈止损方案。

## 7. 产物

- 研究脚本：`scripts/research_hype_1d_ma7_snc02_ma05_probe_sizing_stage_b.py`
- 机器证据：`artifacts/hype_1d_ma7_snc02_ma05_probe_sizing_stage_b_2026-08-20.json`
- 诊断报告：`diagnostics/hype-1d-ma7-snc02-ma05-probe-sizing-stage-b-2026-08-20.md`
