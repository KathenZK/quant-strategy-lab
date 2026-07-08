# HYPE-EMA-TB 最近三个月波动率与 TP/SL 审计

日期：2026-07-08

## 结论

数据湖已把 Binance HYPEUSDT 永续 `15m` 已闭合 K 线更新到 `2026-07-08 05:30 UTC`。本次检查的直接结论是：**最近三个月波动率确实略有下降，但不足以解释为“止盈止损因为波动率变小而失效”。**

更准确的判断：

- 最近 90 天 median `ATR%` 为 `0.68%`，前 90 天为 `0.71%`，下降约 `4.23%`；15m 高低波幅中位数从 `0.67%` 降到 `0.63%`，确实变窄。
- 但 V35 最近 90 天仍有 `26` 次 take-profit、`7` 次 stop-loss、`2` 次 indicator-exit，TP 仍在正常触发；不是“波动小到 5ATR TP 打不到”。
- 最近 90 天 V35 收益 `+215.41%`、maxDD `-21.90%`，低于前 90 天 `+491.82% / -21.87%`；主要劣化更像是交易质量/信号强度下降和止损占比上升，而不是 TP/SL 机制本身失效。
- 最近 90 天 V35 入场 median `ATR%` 从前 90 天 `0.66%` 降到 `0.61%`，对应 `5ATR` TP 的价格距离从 `3.29%` 降到 `3.05%`，`7ATR` SL 从 `4.61%` 降到 `4.26%`。ATR 变小会让价格层面的 TP/SL 更近，不会让 TP 更难触发。
- 真正需要注意的是仓位：V35 用 `target_atr_pct / ATR%` 估算仓位。最近 90 天 35 笔里有 `18` 笔打到 `3.0x` cap，median allocation 为 `3.0x`；低 ATR 会更容易推高仓位，导致单次 SL 的账户回撤体感更重。

## 数据湖更新与质量

- 市场：Binance USD-M Futures。
- 标的：`HYPE/USDT:USDT`。
- 周期：`15m`。
- 数据范围：`2025-05-30 10:30 UTC` 至 `2026-07-08 05:30 UTC`。
- 已闭合 K 线：`38765` 根。
- 缺失 15m bar：`0`。
- 重复 timestamp：`0`。
- open/high/low/close/volume/quote_volume/trade_count/vwap 关键空值：`0`。
- OHLC 违规：`0`。
- raw vs normalized：`38765` 行完全对齐，open/high/low/close/volume/quote_volume/trade_count/vwap 最大差异均为 `0`。
- Funding：对齐后非零 funding 行 `2422`，aligned sum rate `0.09728559`。

## 波动率对照

| 窗口 | 价格变化 | median ATR% | mean ATR% | median 15m high-low% | median abs 15m return | p90 abs 15m return | median 1d realized vol |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 最近 30 天 | +11.91% | 0.83% | 0.87% | 0.69% | 0.29% | 0.85% | 91.90% |
| 最近 90 天 | +76.84% | 0.68% | 0.72% | 0.63% | 0.26% | 0.80% | 81.36% |
| 前 90 天 | +48.50% | 0.71% | 0.81% | 0.67% | 0.28% | 0.88% | 85.23% |
| 全样本 | +103.39% | 0.78% | 0.81% | 0.69% | 0.29% | 0.86% | 90.83% |

最近 90 天比前 90 天确实更窄，但幅度是温和下降，不是 regime 级别塌缩。最近 30 天 median ATR% 反而回升到 `0.83%`。

## 策略最近 90 天

| 版本 | 90天收益 | maxDD | 交易数 | 胜率 | 退出结构 | median entry ATR% | median TP距离 | median SL距离 | median allocation |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| V35 | +215.41% | -21.90% | 35 | 74.29% | TP 26 / SL 7 / indicator 2 | 0.61% | 3.05% | 4.26% | 3.0x |
| V38 | +170.62% | -21.90% | 35 | 74.29% | TP 20 / SL 8 / floor 6 / indicator 1 | 0.61% | 3.05% | 4.26% | 3.0x |
| V37 | +257.27% | -24.76% | 49 | 71.43% | TP 35 / SL 8 / weak 4 / indicator 2 | 0.69% | 3.44% | 4.81% | 2.829x |
| V37+V38 | +206.53% | -24.76% | 49 | 71.43% | TP 29 / SL 9 / floor 6 / weak 4 / indicator 1 | 0.69% | 3.44% | 4.81% | 2.829x |

V38 在最近 90 天把 6 笔原本可能继续跑向 TP 的单改成 profit floor，收益从 V35 的 `+215.41%` 降到 `+170.62%`，maxDD 不变。它仍然是“高 MFE 回吐保险”，不是近期收益修复工具。

V37 最近 90 天收益最高，但 maxDD 到 `-24.76%`，说明 early-long 卫星增加了收益，也带来了额外回撤；叠加 V38 后收益降到 `+206.53%`，回撤没有改善。

## 判断：是不是波动率变小导致 TP/SL 出问题？

不是主因。

原因有三点：

1. V35 的 TP/SL 是 entry ATR 固定距离。ATR% 变小会让 `5ATR` TP 和 `7ATR` SL 在价格百分比上变近。最近 90 天 median TP 距离只有 `3.05%`，比前 90 天 `3.29%` 更近，不是更难打到。
2. 最近 90 天 V35 仍然有 `26/35` 笔 TP，TP 触发占比仍高；如果波动率小到 TP/SL 机制失效，应该看到 TP 明显枯竭，但这里没有。
3. 更明显的变化是信号强度和亏损占比：V35 入场处 median ADX28 从前 90 天 `38.73` 降到最近 90 天 `33.24`，胜率从 `84.85%` 降到 `74.29%`，SL 从 `4` 笔增到 `7` 笔。

所以近期问题更像：

- 趋势质量下降，ADX 入场强度变弱；
- 低 ATR 让仓位更容易打到 `3.0x` cap，SL 对账户权益更疼；
- V38 profit floor 能处理“差一点 TP 后回吐”的心理/尾部问题，但样本内会牺牲收益，不能解决最近 90 天收益下降的核心原因。

## 后续建议

暂不建议因为“波动率变小”去放宽 TP/SL。更值得测的是低 ATR regime 下的仓位 cap 或入场质量过滤：

- 当 entry `ATR% < 0.60%` 时，降低 `max_allocation` 或提高 ADX/volume 门槛；
- 检查最近 90 天 7 笔 V35 stop-loss 的共同特征：是否集中在低 `ATR%`、低 ADX28、低 volume_surge 或卫星/主仓重叠；
- V38 继续只作为 near-TP 回吐保险观察，不作为收益修复版。

## 复现与证据

- 数据湖补数脚本：`../scripts/fetch_hype_binance_15m.py`
- 波动率审计脚本：`../scripts/research_hype_ema_tb_recent_volatility_audit.py`
- 数据质量产物：`../artifacts/hype_binance_15m_data_quality.json`
- 审计 JSON：`../artifacts/hype_ema_tb_recent_3m_volatility_audit_2026-07-08.json`
- 审计逐笔：`../artifacts/hype_ema_tb_recent_3m_volatility_audit_trades_2026-07-08.csv`
