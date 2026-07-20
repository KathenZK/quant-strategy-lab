# HYPE-30M-Keltner-Breakout-Retest 首轮搜索

日期：2026-07-17

状态：`explore / not promoted / not live-ready`

研究目标：从 `HYPE-30M-Keltner-Trend-Breakout-V3` 演变出独立的 Keltner 突破→回踩→恢复趋势状态机，在不放宽止损、不机械缩小止盈的前提下，把全样本与时间分离胜率提高到 V3 的 `67.95%` 以上。

## 结论

**未找到满足目标的候选，0/864 通过。**

直接突破后等待回踩并没有提高胜率，反而把优质趋势入口延迟成较差入口：

- 严格“重新收回当前上轨”最佳行：`29 笔 / 胜率 62.07%`，validation 胜率仅 `50%`。
- 扩展到上轨内侧 `0.5 ATR` 的恢复区域后仍无通过行。
- 全搜索最接近行：`38 笔 / 胜率 60.53% / Return +317.64% / MDD -22.15%`。
- 同样本 parent V3 双向：`78 笔 / 胜率 67.95% / Return +6328.98% / MDD -22.68%`。
- 同样本 parent V3 仅多：`47 笔 / 胜率 74.47% / Return +3565.97% / MDD -17.84%`。

本机制不登记 `V1`，不继续围绕同一历史样本调参。

## 数据与执行口径

- Binance USDM perpetual `HYPEUSDT`。
- 真实 `1m` closed bars 聚合完整 `30m` / `1h`。
- UTC 数据：`2025-05-30 10:30` 至 `2026-07-13 06:06`，共 `588,697` 行。
- 缺失分钟、重复时间戳、非法 OHLC、关键空值均为 `0`。
- 手续费 `0.001/fill`，不利滑点 `0.0004/fill`，计入 Binance 历史 funding。
- 信号收盘后下一根 `30m` open 入场；入场 bar 起启用固定 `TP=10% / SL=2.5%`；SL 同 bar 优先；`hold=30`。
- ATRVT：`target=2.7%`、最高 `3x`、无最低杠杆 floor。
- 搜索只使用多头，避免已知较弱的 parent 空头腿污染新机制判断。

独立实现首先逐笔复现 parent V3：`+6328.9845% / 78 笔 / 胜率 67.9487%`，通过 parity 前置。

## 状态机

1. `1h EMA16 > EMA44` 且 EMA44 五小时前斜率为正。
2. `30m close > Keltner upper(EMA10, RMA ATR10, 2.0x)` 建立 breakout setup，不立即追入。
3. 在后续有限窗口等待价格回踩当前上轨区域，且不得有效跌破中轨容忍区。
4. 回踩后要求方向性阳线、close-location 达标，并恢复至当前上轨或上轨内侧指定 ATR 区域。
5. reclaim bar 收盘确认，下一根 `30m` open 入场。
6. 入场时检查 `ATR84 / next_open <= 1.25%`。

所有 setup、touch、reclaim 判断只使用当前已收盘 bar 与历史数据。

## 搜索范围

共 `864` 个入场状态机组合：

| 参数 | 扫描值 |
| --- | --- |
| 最大等待 | `2 / 3 / 4 / 5` bars |
| 上轨 touch buffer | `0 / 0.15 / 0.30 ATR10` |
| 中轨容忍 | `0 / 0.25 ATR10` |
| reclaim 相对上轨 | `-0.50 / -0.25 / 0 / +0.10 ATR10` |
| reclaim close-location | `0.55 / 0.65 / 0.75` |
| 通道扩张回看 | `关闭 / 3 / 6 bars` |

TP、SL、timeout、ATRVT 和趋势 regime 全部冻结，避免用退出改造制造表面高胜率。

验收要求：

- 全样本至少 40 笔，胜率 `>72%`，MDD不差于 `-22.68%`，PF至少 2；
- train 至少 20 笔且胜率高于 V3；
- validation 至少 8 笔且胜率高于 V3；
- 不使用 holdout 选择参数。

通过数：`0`。

## 最接近行

参数：

```text
max_wait_bars          = 5
touch_buffer_atr       = 0
mid_tolerance_atr      = 0
reclaim_buffer_atr     = -0.25
reclaim_close_location = 0.65
expansion_lookback     = 0
require_bullish_candle = true
side                   = long-only
```

| 区间 | Return | MDD | 胜率 | 交易数 |
| --- | ---: | ---: | ---: | ---: |
| Full | `+317.64%` | `-22.15%` | `60.53%` | 38 |
| Train | - | - | `62.50%` | 24 |
| Validation | - | - | `61.54%` | 13 |
| Holdout | - | - | 样本不足 | 1 |

该行只是失败搜索中的 near observation，不是候选版本。

## 为什么失败

- Parent 的直接突破多头本身已有 `74.47%` 胜率；等待回踩删除了一部分最强趋势延续交易。
- 回踩后重新加速不稳定，更多交易最终走 time exit；near 行 38 笔中只有 1 笔 TP、29 笔 time exit、8 笔 SL。
- 严格 reclaim 太晚、交易少；放宽到上轨内侧虽然增加交易，但胜率仍只有约 60%。
- expansion 和中轨保护在 near 行逐笔无影响，是死旋钮；继续围绕这些参数搜索只会增加过拟合风险。

## 补充稳健性

虽然 near 行不达标，仍保留失败诊断：

- 12 个非重叠30日窗口仅 6 个正收益；中位收益 `+3.47%`，中位 2.5 笔。
- 5,000 次 trade bootstrap：收益 p05 `+63.48%`，MDD p05 `-36.19%`，胜率 p05 `47.37%`。
- 参数邻域 13 行均为正收益，但不能修复低胜率和低交易数。
- 双倍手续费/滑点后 `+216.59% / MDD -24.50% / 胜率 57.89%`。
- 延迟两根 bar 入场后 MDD恶化至 `-33.28%`。

30m 相位：

| 相位 | 收益中位 | 最低收益 | MDD 中位 | 交易数中位 |
| --- | ---: | ---: | ---: | ---: |
| `0` | `+195.92%` | `+130.77%` | `-20.50%` | 24 |
| `10` | `+170.19%` | `+141.27%` | `-22.39%` | 26 |
| `20` | `+74.73%` | `+61.62%` | `-35.25%` | 27 |

相位收益比比 parent V3 好，但 near 行本身不满足胜率目标，不能据此 promotion。

近期切片：

| 1d | 7d | 1m | 3m | 6m | 1y |
| ---: | ---: | ---: | ---: | ---: | ---: |
| `0%` | `-7.26%` | `+15.00%` | `+12.05%` | `+142.26%` | `+223.78%` |

## 决策

- 不登记 `HYPE-30M-Keltner-Breakout-Retest-V1`。
- 停止继续搜索当前 breakout→upper-retest→reclaim 定义。
- 不把 parent V3 long-only 后验包装成新策略；它仍只是 parent 消融观察。
- 若继续寻找高胜率 Keltner 策略，应提出不同、预先冻结的机制假设，例如通道内趋势回撤或中轨趋势恢复，而不是扩大当前网格。

## 证据

- [研究脚本](../scripts/research_hype_30m_keltner_breakout_retest_initial_search.py)
- [汇总 JSON](../artifacts/hype_30m_keltner_breakout_retest_initial_search_2026-07-17.json)
- [搜索表](../artifacts/hype_30m_keltner_breakout_retest_search_2026-07-17.csv)
- [Near 行逐笔交易](../artifacts/hype_30m_keltner_breakout_retest_candidate_trades_2026-07-17.csv)
- [滚动窗口](../artifacts/hype_30m_keltner_breakout_retest_oos_2026-07-17.csv)
- [Monte Carlo](../artifacts/hype_30m_keltner_breakout_retest_mc_2026-07-17.csv)
- [相位](../artifacts/hype_30m_keltner_breakout_retest_phase_2026-07-17.csv)
- [组件消融](../artifacts/hype_30m_keltner_breakout_retest_ablation_2026-07-17.csv)
- [参数邻域](../artifacts/hype_30m_keltner_breakout_retest_neighborhood_2026-07-17.csv)
- [近期切片](../artifacts/hype_30m_keltner_breakout_retest_recent_slices_2026-07-17.csv)
- [执行压力](../artifacts/hype_30m_keltner_breakout_retest_stress_2026-07-17.csv)
