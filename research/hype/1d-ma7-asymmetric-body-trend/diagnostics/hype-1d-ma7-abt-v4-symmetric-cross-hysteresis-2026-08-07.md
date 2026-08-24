# HYPE V4 对称 MA7 Cross × 持仓迟滞诊断

> 日期：2026-08-07。结论：用户澄清的行为已被正确实现——flat 入场只看 fresh MA7 cross，持仓后才使用双侧 `0.75×ATR7` 容错；但候选全期仅 `+44.12%`、MDD `-53.32%`，`12h` 为 `-69.64%`，23 个有效相位仅 6 个盈利。该机制不替代 V4，不登记 V5。

## 冻结口径

- 合同：[对称 MA7 Cross × 持仓迟滞合同](../specs/hype-1d-ma7-abt-v4-symmetric-cross-hysteresis-contract-2026-08-07.md)；
- Binance USD-M `HYPEUSDT` perpetual，accepted `1h` 聚合完整 UTC 日 K；
- flat：前收与当收新鲜穿越 `SMA7`，次日 open 入场；无 slope、entry buffer 或 ATR 入场门槛；
- long：仅当完整日收盘跌破 `SMA7-0.75×ATR7` 时次开平多反手空；
- short：仅当完整日收盘突破 `SMA7+0.75×ATR7` 时次开平空反手多；
- 保留 V4 hard/trailing、max hold、long `2d` / short `5d` cooldown 数值；保护与 max hold 只转 flat；
- 约 `1x`、单仓、非加仓；手续费 `0.001/fill`、不利滑点 `4 bps/fill`、真实 funding。

本轮只运行一个候选 `SYMMETRIC_CROSS_D075`，没有搜索容错距离、slope、pending 或 cooldown。

## 主结果

| 检查 | V4 | 对称候选 |
|---|---:|---:|
| 全期净收益 | `+411.23%` | `+44.12%` |
| MDD | `-26.81%` | `-53.32%` |
| Sharpe | `2.669` | `0.790` |
| PF | `13.516` | `1.415` |
| 交易数 | 17 | 29 |
| long / short | `8 / 9` | `20 / 9` |
| 胜率 | `70.59%` | `44.83%` |
| 暴露率 | `42.02%` | `63.85%` |
| `8 bps` | `+404.59%` | `+40.85%` |
| 额外延迟 1 日 | `+109.85%` | `+61.36%` |
| `12h` 日界 | `+35.33%` | `-69.64%` |
| 最新延伸 | `+398.84%` | `+37.83%` |

候选 prefit 为 `-9.14%`、MDD `-53.32%`；最后 90 日 flat-start 为 `+58.61%`、MDD `-28.49%`。收益主要来自后段，不能覆盖早期方向错误。

## 稳健性

- 90 日滚动：V4 为 `12/12` 盈利、中位 `+37.02%`、最差 `+15.02%`；候选为 `8/12` 盈利、中位 `+2.96%`、最差 `-36.60%`。
- 24 相位：相位 8 因缺 terminal open 不可用；其余 23 相位中，V4 `21/23` 盈利、中位 `+38.35%`，候选仅 `6/23` 盈利、中位 `-20.84%`、最差 `-68.89%`。
- 候选近期 `1d/7d/1m/3m/6m/1y`：`+1.81% / +8.70% / -0.68% / +58.61% / +37.87% / +41.44%`。
- 没有简化 intraday bankruptcy，但相位最差 MDD 达 `-83.40%`。

相位仍是检查项而非独立硬门禁；这里它与 prefit、滚动、MDD、PF 和 `1m/1y` 共同指向同一弱化结论。

## 行为是否符合用户本意

符合。2025-06-17 完整日收盘形成 fresh short cross 后，不再等待 short `2d` slope：

1. 2025-06-18 open 直接建立 short；
2. short 持有至 2025-06-30，越过上方 `0.75×ATR7` 边界后反手 long；
3. short 成本后 `+0.58%`；
4. 由于 6 月 28 日仍持有 short，V4 原 `2025-06-28` long 无法成交；
5. 6 月 30 日反手 long 后仍在原 `2025-07-17 21:00` 保护时点退出，但因晚两日、入场价更高，只赚 `+12.27%`，低于 V4 原 long 的 `+21.88%`。

这说明“cross 必须产生方向动作”已实现；结果下降来自真实仓位占用与后续路径变化，不是再次漏掉 6 月 short。

## 逐笔路径与连锁变化

`共享`表示与 V4 同一入场、同一退出；其余均为候选新增或由仓位占用形成的替代路径。

| # | 候选交易 | 结果 | 相对 V4 的解释 |
|---:|---|---:|---|
| 1 | 2025-06-10 long → 06-13 protection | `-3.67%` | 与 V4 共享，规则尚未产生差异。 |
| 2 | 2025-06-18 short → 06-30 boundary | `+0.58%` | 6 月 17 日 fresh cross 次开空；占用 6 月 28 日，删除 V4 `+21.88%` long。 |
| 3 | 2025-06-30 long → 07-17 protection | `+12.27%` | 由持仓上边界反手；恢复上涨但比 V4 long 晚 2 日，收益减少。 |
| 4 | 2025-07-23 long → 08-01 boundary | `-12.22%` | 新增 flat cross long；占用并删除 7 月 24 日 V4 short `+6.26%`。 |
| 5 | 2025-08-01 short → 08-08 boundary | `-0.53%` | 上笔 long 的下边界反手；比被删除的 V4 short 晚 8 日。 |
| 6 | 2025-08-08 long → 08-19 protection | `+2.84%` | short 上边界反手；形成候选独有链条。 |
| 7 | 2025-08-23 long → 09-01 protection | `-5.45%` | 新增 fresh cross；提前占仓，删除 V4 8 月 27 日 long `+10.28%`。 |
| 8 | 2025-09-15 short → 09-18 boundary | `-7.78%` | 新增 fresh cross；快速下边界方向失败。 |
| 9 | 2025-09-18 long → 09-20 protection | `-5.97%` | 上笔反手后再亏；候选未形成 V4 9 月 20 日 short `+17.59%`。 |
| 10 | 2025-09-28 long → 10-07 protection | `-0.19%` | 新增 fresh cross；延续错过 V4 9 月 short 的连锁差异。 |
| 11 | 2025-10-14 long → 10-22 protection | `-19.09%` | 最大单笔亏损；占用并删除 V4 10 月 15 日 short `+6.12%`。 |
| 12 | 2025-10-31 short → 11-20 max hold | `+14.68%` | 新增 fresh cross；20 日 max hold 获利退出。 |
| 13 | 2025-11-27 long → 12-01 boundary | `-12.15%` | short cooldown 后新 cross；替代 V4 11 月 21 日 short `+6.82%`。 |
| 14 | 2025-12-01 short → 12-21 max hold | `+25.02%` | 下边界反手；早于 V4 12 月 6 日 short，但 max hold 也早 4 日退出。 |
| 15 | 2025-12-27 long → 2026-01-01 protection | `-6.93%` | 新增 fresh cross，V4 无对应仓位。 |
| 16 | 2026-01-04 long → 01-08 protection | `+1.06%` | 新增 fresh cross，保护退出。 |
| 17 | 2026-01-14 long → 01-19 protection | `-7.88%` | 新增 fresh cross，保护退出。 |
| 18 | 2026-01-25 long → 01-30 protection | `+29.39%` | 比 V4 1 月 27 日 long 提前 2 日，退出相同；本段优于 V4 `+20.47%`。 |
| 19 | 2026-02-07 short → 02-27 max hold | `+13.10%` | 新增 fresh cross，V4 无对应仓位。 |
| 20 | 2026-03-06 short → 03-09 protection | `-15.46%` | fresh short 取代 V4 3 月 1 日 long `+21.11%`，方向选择显著失败。 |
| 21 | 2026-03-21 short → 04-08 boundary | `+2.32%` | 新增 fresh cross；持续占仓，覆盖 V4 3 月 22 日短空与 3 月 29 日 long。 |
| 22 | 2026-04-08 long → 04-20 protection | `+5.51%` | 上笔 short 的上边界反手；结束该候选独有链条。 |
| 23 | 2026-04-26 long → 04-28 protection | `-3.62%` | 新增 fresh cross。 |
| 24 | 2026-05-02 long → 05-11 protection | `-0.52%` | 新增 fresh cross。 |
| 25 | 2026-05-15 long → 06-04 protection | `+47.01%` | 与 V4 共享；候选保护退出只转 flat，因此删除 V4 6 月 4 日反手 short `+1.42%`。 |
| 26 | 2026-06-12 long → 06-23 protection | `+9.20%` | cooldown 后新 fresh cross，V4 无对应仓位。 |
| 27 | 2026-06-30 long → 07-11 protection | `-1.17%` | 比 V4 7 月 3 日 long 提前 3 日，退出相同，结果近似。 |
| 28 | 2026-07-16 long → 07-17 boundary | `-9.47%` | 候选未做 V4 7 月 11 日 trailing 反手 short，转而先开 long 并一日亏损。 |
| 29 | 2026-07-17 short → 07-30 terminal | `+11.00%` | 下边界反手；比 V4 7 月 11 日 short `+18.86%`晚 6 日，少吃一段跌势。 |

完整逐笔差异见[逐笔差异 CSV](../artifacts/hype_1d_v4_symmetric_cross_hysteresis_2026-08-07_trade_deltas.csv)，候选原始交易见[候选交易 CSV](../artifacts/hype_1d_v4_symmetric_cross_hysteresis_2026-08-07_symmetric_cross_d075_trades.csv)。

## 归因

- 22 笔 flat fresh-cross 入场只有 8 笔盈利，动态净 PnL 合计约 `-0.0038` 个初始权益单位，整体没有显示历史优势。
- 7 笔持仓外边界反手有 5 笔盈利，动态净 PnL 合计约 `+0.4450`；但它们依赖前序仓位路径，不能作为独立入场优势。
- 7 笔以外边界反手结束的旧仓只有 2 笔盈利，合计动态净 PnL 约 `-0.4099`，说明持仓容错会让部分错误 fresh-cross 仓位继续承受较大损失。
- 29 笔中 18 笔由保护退出、3 笔由 max hold 退出；多头从 V4 的 8 笔增至 20 笔，是暴露率和 MDD扩大的主要来源。

问题不在手续费：`8 bps`仍为正。核心问题是“任何无 slope 的 fresh MA7 cross 都可入场”增加了大量方向质量较低的 long，并通过仓位占用删除原 V4 的高收益 short/long。

## 裁决

1. 用户本意已经正确复现，不能再说该行为“没有被测试”；
2. 本轮候选历史表现显著失败，不替代 V4，不登记 V5，不 promotion；
3. V4 继续保持 `registered / not promoted / not live-ready`；
4. 不根据上述单笔赢家继续搜索 `0.75`、重新加 slope 或增加 pending；
5. 该结果也不证明“对称原则错误”，只证明“flat 无质量门槛 fresh cross + 持仓 `0.75×ATR7` 迟滞 + V4风险层”在当前历史上不具备 V4 的选择性。

## 证据

- [冻结合同](../specs/hype-1d-ma7-abt-v4-symmetric-cross-hysteresis-contract-2026-08-07.md)
- [审计脚本](../scripts/audit_hype_1d_ma7_abt_v4_symmetric_cross_hysteresis.py)
- [交易路径渲染脚本](../scripts/render_hype_1d_ma7_abt_v4_symmetric_cross_hysteresis_trade_path.py)
- [完整交易路径 HTML](../artifacts/hype_1d_ma7_abt_v4_symmetric_cross_d075_trade_path_2026-08-07.html)
- [机器摘要](../artifacts/hype_1d_v4_symmetric_cross_hysteresis_2026-08-07_summary.json)
- [分期/压力/延迟](../artifacts/hype_1d_v4_symmetric_cross_hysteresis_2026-08-07_metrics.csv)
- [近期切片](../artifacts/hype_1d_v4_symmetric_cross_hysteresis_2026-08-07_recent.csv)
- [90 日滚动](../artifacts/hype_1d_v4_symmetric_cross_hysteresis_2026-08-07_rolling_90d.csv)
- [24 相位](../artifacts/hype_1d_v4_symmetric_cross_hysteresis_2026-08-07_phase24.csv)
- [最新延伸](../artifacts/hype_1d_v4_symmetric_cross_hysteresis_2026-08-07_latest.csv)
