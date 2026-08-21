# HYPE-1D-MA7-ABT-V7.1 OAPP 反弹重置诊断合同

> 冻结日期：2026-08-20。状态：`diagnostic-only / not promoted / not live-ready`。本合同不修改已登记 V7.1，也不授权调整 live runner。

## 1. 问题与证据角色

用户报告的已揭示实盘事件：`2026-08-09 00:00 UTC` 以 `55.113` 开多，`2026-08-16 00:00 UTC` 以 `56.894` 因 `long_mfe_fraction_trail_exit`（OAPP）全平。该事件只能用于问题定位与事件反事实，不能作为 clean OOS 选择集。

V7.1 的 long OAPP 在最高收盘浮盈达到 `0.5×ATR7` 后，只要收盘相对最高收盘的回吐达到 MFE 的 `10%`、毛利润仍高于 `0.28%`，连续两个持仓日成立，就在下一 UTC 日 open 全平。当前“连续确认”不要求第二天继续下跌；即使第二天已经反弹，只要仍处于 `>=10%` 回吐区间，计数仍会增加。

本轮唯一问题：能否把“两日确认”改成更符合趋势语义的确认，避免正常反弹中的全平，同时保留 OAPP 的历史风险收益作用。

## 2. 数据、控制与冻结边界

- Market：Binance USD-M `HYPEUSDT` perpetual。
- Signal：完整 UTC `1d`；风险/stop 使用真实 `1h`；funding 使用 Binance event-time `fundingRate`。
- Cost：`0.001/fill + 4bps/fill`；压力为 `8bps/fill`。
- 唯一控制：exact `HYPE-1D-MA7-Asymmetric-Body-Trend-V7.1`，固定 `1x`、单仓、非加仓。
- Canonical 冻结窗：`2025-05-31` 至 `2026-08-06 00:00 UTC`，必须复现 `+711.04% / -18.40% / 20笔`。
- 扩展诊断窗：从同一起点至运行时最后一个完整 UTC 日；新增数据与 8 月事件已揭示，只作 diagnostic。
- V7.1 的入场、native MA7 exit、`1.5ATR` long trail、short RSI、short cooldown `3d`、PEHC_294、成本、funding 和执行顺序全部不变。

## 3. 预冻结候选

除控制外只运行以下三个单机制候选，不扩网格、不按结果补参数：

1. `RR`（rebound reset，主候选）：
   - 第一个满足原 OAPP 条件的收盘记为确认 `1`；
   - 后续仍满足原条件且 `close[t] <= close[t-1]` 才把确认数加一；
   - 若仍满足原条件但 `close[t] > close[t-1]`，说明价格反弹，确认数重置为 `1`；
   - 原条件不满足时重置为 `0`。
2. `AF05`（ATR floor，机制对照）：在原 OAPP 条件外，要求从最高收盘的绝对回吐至少 `0.5×ATR7`；原两日确认保持不变。
3. `MAG05`（MA proximity gate，机制对照）：在原 OAPP 条件外，要求 `close <= SMA7 + 0.5×ATR7`；原两日确认保持不变。

既有 V7.1 全参数消融中的 `confirm=3d`、`giveback=25%` 和 long OAPP off 只作已知参数放宽对照，不作为本轮候选，也不重复扩大邻域。

## 4. 必做审计

- Runner exact path：扩展控制必须复现用户给出的入场、出场、价格与原因；冻结前20笔必须继续与 V7.1 canonical 一致。
- 事件反事实：先保持 V7.1 历史状态至 `2026-08-09`，只从该笔入场后切换候选，报告 `2026-08-16` 是否仍退出、之后首次真实退出/terminal 状态、MA7/ATR7/OAPP计数。
- 全路径：候选从历史起点启用，报告收益、真实 `1h` MDD、PF、胜率、交易数、OAPP/PEHC次数、与控制的逐笔差异。
- 压力：`8bps`、信号额外延迟 `1d`、funding-off。
- 最近切片：按数据末端报告 `1d/7d/1m/3m/6m/1y`，仅作审计。
- 机制归因：逐个列出被候选改变的 long OAPP episode；不得只报告总收益。

## 5. 判定

- 候选若不能阻止 8 月 16 日的反弹中退出，则不解决本次问题。
- 阻止该次退出只证明局部规则生效，不证明未来收益更高；截至数据末端若仍持仓，只能写“结果未成熟”。
- 历史全路径若收益和 MDD同时恶化，或破坏 PEHC/forced-reversal 形成新的明显风险，不建议替换。
- 本轮最多给出 `KEEP V7.1`、`SHADOW RR` 或 `NO-GO` 建议；不得登记 V7.2、promotion 或直接改 runner。
- 若 `RR` 兼具最小改动、事件修复和不明显破坏历史路径，只能冻结为后续 shadow observer 假设；最终判断依赖新增、未用于本轮设计的前瞻交易。
