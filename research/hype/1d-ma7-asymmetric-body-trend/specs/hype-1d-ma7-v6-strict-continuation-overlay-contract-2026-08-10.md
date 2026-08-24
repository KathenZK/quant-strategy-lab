# HYPE-1D-MA7-ABT-V6 严格连续趋势 Overlay 执行合同

> 冻结时间：2026-08-10（首次运行前）。状态：`diagnostic-only / not promoted / not live-ready`。

## 研究问题

把上一轮“非 ML 三门放行器”落成一套可执行规则：只在 exact V6 漏掉 raw MA7 cross
后，用已知数据确认趋势延续、MAE 预算和机会成本，再决定是否补一笔 overlay 交易。

本轮只运行这一套规则，不搜索阈值，不登记 V7，不研究杠杆，不生成交易路径 HTML。

## 固定规则

Control：exact V6 `PEHC_294`，固定 `1x`、单仓、非加仓。

候选只来自 V6 原生入场未触发时的 raw MA7 cross：

- long raw cross：前一完整日 close `<= MA7`，当前完整日 close `> MA7`；
- short raw cross：前一完整日 close `>= MA7`，当前完整日 close `< MA7`；
- V6 原生入场永远优先；相反 cross、穿回 MA7、非有限数据或超过 `5d` 未确认即取消。

候选必须同时过三门：

1. 趋势延续门：
   - raw cross 后至少 `3` 个完整日持续位于 MA7 同侧；
   - `2d` MA7 slope / ATR 同向 `>= 0.04`；
   - close 距 MA7 在 `[0.25, 1.00] ATR` 内；
   - `ER5 >= 0.35`，避免 MA7 附近来回摆动。
2. MAE / 失效风险门：
   - 从 raw cross close 到确认日 close 的最差反向 close 变动不得低于 `-0.75 ATR`；
   - 确认日不得是距 MA7 超过 `1.00 ATR` 的追价。
3. 机会成本门：
   - overlay 只在 V6 baseline flat 时评估；
   - 不允许覆盖真实持仓；
   - 结果必须审计是否减少 V6 的 `long_mfe`、`short_rsi`、`shadow_start` 或
     `handoff_accept` 事件；若减少，判定机会成本门失败。

## 必须输出

- exact V6 与严格 overlay 的全窗收益、真实 `1h` MDD、日内极值 MDD、PF、胜率、交易数；
- 候选 raw cross、确认、取消、过期次数，以及趋势/MAE/机会成本门失败原因；
- 相对 V6 的新增/删除交易和核心链条事件变化；
- `8 bps`、funding-off、额外一日 signal lag；
- `8 × 54d` cold-flat block 与最近 `1d/7d/1m/3m/6m/1y`；
- 裁决：只有全窗收益更高、真实 `1h` MDD 更小、压力和分块不双劣、且机会成本门不失败时，才允许成为 diagnostic passer。

## 裁决纪律

方向确认、视觉趋势补到或局部收益为正都不是通过条件。若完整经济路径劣于 V6，或任何核心链条事件被削弱，本轮失败并停止，不在同一 432 日继续调阈值。
