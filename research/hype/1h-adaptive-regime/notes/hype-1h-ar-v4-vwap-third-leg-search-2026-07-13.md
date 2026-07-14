# HYPE-1H-Adaptive-Regime-V4 VWAP 第三腿严格搜索 - 2026-07-13

## 结论

本轮没有找到同时满足“第三腿高胜率、三腿组合正向增益、K+2/8bps 不恶化”的 VWAP 第三腿。`2,400` 个冻结搜索候选中，`13` 个通过第三腿 standalone 严格门槛，但精确三腿联合门槛通过数为 `0`；因此不登记 V5，不改变 `HYPE-1H-Adaptive-Regime-V4` 的 `NO-GO / not promoted / not live-ready` 状态。

搜索结果不是“VWAP 腿完全没有预测力”。最接近的预拟合观察 `HYPE_1H_AR_V4_VWAP3_1442` 在 base/K+2/8bps 的 prefit 中都提高收益和胜率，但三个场景的 validation 回撤均比 V4 多恶化超过预先冻结的 `1pp` 容差。冻结后揭示又显示，它在 reused holdout 的三场景边际收益全部为负，因此不能事后放宽门槛接纳。

## 数据与执行口径

- 市场：Binance USD-M Futures `HYPEUSDT` perpetual `1h`。
- 冻结闭合 K：`2025-05-30 10:00 UTC` 至 `2026-07-02 02:00 UTC`，共 `9,545` 根；本轮禁止 refresh。
- 数据质量：missing `0`、duplicate `0`、critical null `0`、OHLCV violation `0`、raw/normalized mismatch `0`。
- 资金费：历史资金费 `2,385` 条，按持仓区间计入。
- 成本：fee `0.001/fill`；base/K+2 滑点 `4 bps/fill`；成本压力 `8 bps/fill`。
- 执行：闭合 K 确认信号，K+1 或压力口径 K+2 open 市价入场；stop-first；gap-open stop 按 open 成交。
- 三腿仲裁：全局单仓，优先级 `DI > Stoch > VWAP`；VWAP 只填空仓；只有真实成交才更新对应腿 cooldown。
- 选参数据：仅 train、validation、prefit；reused holdout/current full 只在身份冻结后一次性揭示。

## 第三腿机制

第三腿是 `1x`、short-only、range-gated 的 VWAP 偏离回归：

1. `vwap_dev_atrW = (close - rolling_vwap_W) / ATR14` 从上方下穿正偏离带时 arm。
2. arm 和 confirm 时都重新执行 ADX、RVOL、ATR 等过滤。
3. arm 后第一根完整闭合 K 才能确认；确认窗口为 `3/6/12` 根，过期不补单。
4. 确认模式为 `roc6_macd`、`roc6_di` 或 `fast_consensus`。
5. 确认后按场景在下一根或下两根 open 入场。

搜索覆盖 VWAP `24/48/96/168h`、偏离带 `0.75-2.0 ATR`、`max_adx=20/30/40`、RVOL/ATR 下限、fixed/trailing exit、TP/SL、最长持仓和 cooldown。使用固定 seed `2026071304` 生成 `2,399` 个 arm-confirm 候选，并保留 `1` 个即时 VWAP 对照；即时对照不具备赢家资格。

## 预先冻结门槛

### 第三腿 standalone

- train、validation、prefit 总收益分别严格大于 `0`；
- 三个窗口胜率分别 `>=80%`；
- validation 至少 `10` 笔，prefit 至少 `25` 笔；
- 三个窗口最大回撤严格小于 `20%`；
- 与 V4 入场的 `±3h` overlap 小于 `40%`。

### 精确三腿组合

对 base K+1、K+2、8bps 三个场景的 train、validation、prefit 同时要求：

- 相对 V4 的 log equity 增量非负，prefit 严格为正；
- 组合胜率不低于 V4；
- 最大回撤相对 V4 的恶化不超过 `1pp`；
- base prefit 至少新增 `8` 笔真实 VWAP 成交；
- VWAP 被 V4 挡掉比例小于 `70%`；
- 单笔最大正贡献不超过 VWAP 正 log 收益的 `40%`。

## 搜索结果

| 阶段 | 结果 |
| --- | ---: |
| 生成候选 | `2,400` |
| arm-confirm 候选 | `2,399` |
| 即时对照 | `1` |
| standalone 严格门槛通过 | `13` |
| 三场景精确联合评估 | `13` |
| 精确三腿联合门槛通过 | `0` |
| 冻结主观察 | `0` |
| 冻结失败对照 | `2` |

13 个 standalone 高胜率候选进入精确联合后，最常见失败不是交易数或集中度，而是：

- `10/13` 至少在一个场景的 train 组合胜率低于 V4；
- `9/13` 至少出现 validation 回撤、train 收益或 prefit 收益阻塞；
- 三腿诊断附加门槛（新增成交、blocked ratio、正收益集中度）在这 13 个候选中全部通过。

这说明“单腿胜率高”不足以保证加入共享单仓后仍提高组合质量；仓位占用、交易排序和低赔率小盈利会稀释原两腿的收益/胜率形状。

## 最接近观察：`HYPE_1H_AR_V4_VWAP3_1442`

预拟合身份：VWAP `168h`、偏离带 `1.75 ATR`、`max_adx=20`、confirm `12h + roc6_macd`、fixed `TP=0.75 ATR / SL=2.5 ATR`、最长持仓 `18h`、cooldown `0`、固定 `1x`。

Standalone train/validation/prefit 分别为：

| Window | Trades | Win rate | Total return | Max DD |
| --- | ---: | ---: | ---: | ---: |
| Train | `34` | `91.18%` | `+28.98%` | `-5.11%` |
| Validation | `10` | `90.00%` | `+11.51%` | `-7.62%` |
| Prefit | `44` | `90.91%` | `+43.83%` | `-7.62%` |

精确三腿 prefit 对 V4 的比较：

| Scenario | V4 annual / DD / win | V4+VWAP annual / DD / win | Δlog equity |
| --- | --- | --- | ---: |
| Base K+1 | `26.8626x / -16.93% / 82.14%` | `34.2675x / -16.93% / 84.15%` | `+0.1818` |
| K+2 | `16.3191x / -19.86% / 80.00%` | `23.1606x / -19.86% / 85.06%` | `+0.2614` |
| 8bps | `20.8854x / -22.20% / 80.00%` | `26.7142x / -22.20% / 83.13%` | `+0.1838` |

它仍被拒绝，因为 validation 回撤相对 V4 的恶化分别为：

- Base K+1：`-1.0725pp`，超过 `1pp` 容差 `0.0725pp`；
- K+2：`-1.4825pp`，超过 `0.4825pp`；
- 8bps：`-1.3563pp`，超过 `0.3563pp`。

## 冻结后揭示

`1442` 只作为 prefit 排名最高的失败对照揭示，不具备赢家资格：

| Scenario | V4 holdout return / DD | V4+VWAP holdout return / DD | 边际收益 |
| --- | --- | --- | ---: |
| Base K+1 | `+61.87% / -19.11%` | `+60.82% / -17.59%` | `-1.05pp` |
| K+2 | `-9.06% / -25.04%` | `-9.45% / -28.64%` | `-0.39pp` |
| 8bps | `+33.14% / -22.46%` | `+31.65% / -24.86%` | `-1.49pp` |

虽然 `1442` 的 current-full base 年化为 `25.1503x`、高于 V4 的 `20.9748x`，但该改善来自已经参与选参的 prefit；reused holdout 没有正边际。不能用 current-full 聚合结果覆盖冻结门槛和后段失败。

第二个冻结失败对照 `HYPE_1H_AR_V4_VWAP3_0008` 也在 reused holdout 三场景全部产生负边际，因此不形成参数邻域继续搜索的依据。

## 最近时间片

由于没有冻结主观察，最近 `1d/7d/1m/3m/6m/1y` 只审计原 V4，不把失败对照包装为第三腿结果：

| Window | Trades | Win rate | Total return | Max DD |
| --- | ---: | ---: | ---: | ---: |
| `1d` | `0` | `0.00%` | `0.00%` | `0.00%` |
| `7d` | `1` | `100.00%` | `+3.91%` | `-0.56%` |
| `1m` | `9` | `77.78%` | `+32.50%` | `-16.37%` |
| `3m` | `20` | `70.00%` | `+60.80%` | `-19.11%` |
| `6m` | `39` | `71.79%` | `+240.34%` | `-19.11%` |
| `1y` | `75` | `80.00%` | `+1789.36%` | `-19.11%` |

时间片锚定数据集末端，只作审计，不参与本轮选参。

## 决策

- 不接纳 VWAP 第三腿，不登记 V5，不改变 V4 或家族状态。
- 不因 `1442` 接近回撤容差而事后把 `1pp` 放宽；后段负边际进一步支持拒绝。
- 当前 OHLCV/VWAP short-range 加法线的主要问题不是找不到高胜率单腿，而是高胜率不能稳定转化为精确单账户组合的跨场景边际。
- 若继续寻找第三腿，应转向与 VWAP/Stoch 不同的信息源或事件机制；仍须先做精确联合增量门槛，不再围绕本轮 `1442/0008` 邻域追参。

## 证据

- 复现脚本：[`../scripts/research_hype_1h_ar_v4_vwap_third_leg.py`](../scripts/research_hype_1h_ar_v4_vwap_third_leg.py)
- 汇总 JSON：[`../artifacts/hype_1h_ar_v4_vwap_third_leg_2026-07-13.json`](../artifacts/hype_1h_ar_v4_vwap_third_leg_2026-07-13.json)
- 全候选：[`../artifacts/hype_1h_ar_v4_vwap_third_leg_all_candidates_2026-07-13.csv`](../artifacts/hype_1h_ar_v4_vwap_third_leg_all_candidates_2026-07-13.csv)
- 冻结失败对照交易路径：[`../artifacts/hype_1h_ar_v4_vwap_third_leg_frozen_trades_2026-07-13.csv`](../artifacts/hype_1h_ar_v4_vwap_third_leg_frozen_trades_2026-07-13.csv)
- V4 压力基线：[`../diagnostics/hype-1h-ar-v4-execution-pressure-optimization-2026-07-10.md`](../diagnostics/hype-1h-ar-v4-execution-pressure-optimization-2026-07-10.md)
