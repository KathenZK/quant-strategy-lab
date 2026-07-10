# HYPE-30M-Keltner-Trend-Breakout-V2.1 ATR 动态 TP/SL 研究

日期：2026-07-10

版本：`HYPE-30M-Keltner-Trend-Breakout-V2.1`

状态：`registered / not promoted / not live-ready`

结论：保留 V2.1 固定 `TP=10% / SL=2.5%`；本轮 ATR 动态 bracket 不采用。

## 研究问题

V2.1 当前 TP/SL 都是入场时固定百分比。动态变体使用信号 bar 已收盘 ATR，在下一根 open 入场时计算并冻结：

```text
dynamic_tp_pct = clip(tp_atr_mult * entry_atr_pct, tp_floor, tp_cap)
dynamic_sl_pct = clip(sl_atr_mult * entry_atr_pct, sl_floor, sl_cap)
```

测试两种 ATR：

- `ATR10`：与 Keltner 通道一致，响应更快；
- `ATR84`：与 V2.1 杠杆 ATR 一致，更稳定。

无持仓中动态更新，不在持仓期间移动 bracket；不存在未来函数。

## ATR 分布

V2.1 的 113 笔入场：

| entry ATR84 / price | 数值 |
| --- | ---: |
| Min | `0.47%` |
| P25 | `0.85%` |
| Median | `1.07%` |
| P75 | `1.25%` |
| P95 | `1.72%` |
| Max | `2.23%` |

在中位 ATR 下，固定 TP/SL 约等于：

- TP：`9.34 ATR84`；
- SL：`2.33 ATR84`。

## 搜索协议

- 共测试 `433` 个配置。
- TP：固定或 ATR 倍数 `6 / 7.5 / 9 / 10.5 / 12`，配 `6%/8%` floor 与 `10%/12%/15%` cap。
- SL：固定或 ATR 倍数 `1.5–3.0`，配 `1.5%/2.0%` floor 与 `2.5%/3.0%/3.5%` cap。
- 成本：手续费 `0.001/fill`、不利滑点 `0.0004/fill`、实际 funding。
- 选择目标：
  - 全样本胜率高于 V2.1；
  - 全样本 MDD 小于 V2.1；
  - 全样本收益至少保留 `80%`；
  - validation 胜率/MDD不退化且收益至少保留 `70%`。

结果：满足全部约束的配置为 `0`。

## 关键反例

### 动态 SL：胜率提高但回撤恶化

表现最强的胜率型动态 SL：

```text
ATR source = ATR10
TP = 固定 10%
SL = clip(3.0 * ATR10%, 2.0%, 3.5%)
```

| 指标 | V2.1 固定 bracket | 动态 SL |
| --- | ---: | ---: |
| Return | `+4638.01%` | `+3678.50%` |
| 收益保留 | `100%` | `79.31%` |
| MDD | `-25.84%` | `-30.72%` |
| Win rate | `56.64%` | `58.93%` |

它提高胜率，但违反“更小回撤”，收益也跌破 `80%` 保留线，因此否决。动态放宽高波动 stop 会减少普通止损，却扩大单次风险和组合回撤。

### 动态 TP near-miss

唯一同时满足全样本三目标的近似候选：

```text
ATR source = ATR10
TP = clip(6.0 * ATR10%, 6%, 10%)
SL = 固定 2.5%
```

| 指标 | V2.1 | 动态 TP near-miss |
| --- | ---: | ---: |
| Return | `+4638.01%` | `+3917.22%` |
| 收益保留 | `100%` | `84.46%` |
| MDD | `-25.84%` | `-25.84%` |
| Win rate | `56.64%` | `56.78%` |
| Trades | `113` | `118` |
| TP / SL / time | `10 / 38 / 65` | `20 / 40 / 58` |

它主要把低波动交易的 TP 压到 `6%–8%`，因此 TP 数增加，但 MDD 只是在浮点精度上等于基线，并没有实质下降。

Validation：

| 指标 | V2.1 | 动态 TP near-miss |
| --- | ---: | ---: |
| Return | `+577.08%` | `+407.31%` |
| 收益保留 | `100%` | `70.58%` |
| MDD | `-19.65%` | `-19.65%` |
| Win rate | `65.79%` | `65.00%` |

Validation 胜率下降、收益明显下降，因此不满足选择协议。

## Near-miss 稳健性

| 检查 | 结果 |
| --- | --- |
| Rolling OOS | 44 组，正收益 `97.73%`，收益中位数 `+32.14%` |
| Monte Carlo | 失败；交易重排 MDD p05 `-41.93%`，差于门槛 `-38.77%` |
| DSR(N=1000) | `0.9576`，通过 |
| Start time | 23 个起跑点均盈利，但 CAGR CV `0.511 > 0.5` |
| 30m phase | 失败；非原生/原生中位 CAGR 比 `10.35%`，CV `1.476` |
| 1h phase | 通过 |
| Holdout | 1 笔，`-2.86%`，证据不足 |

最近分片也发生明显收益损失：

| Window | V2.1 Return | Dynamic TP Return |
| --- | ---: | ---: |
| `1m` | `+28.95%` | `+11.72%` |
| `3m` | `+301.33%` | `+206.46%` |
| `6m` | `+1068.00%` | `+803.25%` |
| `1y` | `+4018.81%` | `+3510.80%` |

## 决策

ATR 动态 TP/SL 在机制上可执行，且入场前一根已收盘 ATR 足以避免未来函数。但在 V2.1 上：

- 动态 SL 用更宽 stop 换取胜率，导致 MDD 恶化；
- 动态 TP 用更近目标换取更多 TP，收益下降且 validation 胜率未提高；
- 没有配置同时实现更高胜率、更低 MDD和可接受收益保留。

因此 V2.1 继续冻结固定 `TP=10% / SL=2.5%`。动态 bracket 只保留为研究诊断，不创建 V2.2。

## 证据

- [研究脚本](../scripts/research_hype_30m_k2_v2_1_dynamic_atr_bracket.py)
- [汇总 JSON](../artifacts/hype_30m_k2_v2_1_dynamic_atr_bracket_2026-07-10.json)
- [搜索表](../artifacts/hype_30m_k2_v2_1_dynamic_atr_bracket_search_2026-07-10.csv)
- [Near-miss trades](../artifacts/hype_30m_k2_v2_1_dynamic_atr_bracket_trades_2026-07-10.csv)
- [Rolling OOS](../artifacts/hype_30m_k2_v2_1_dynamic_atr_bracket_oos_2026-07-10.csv)
- [Monte Carlo](../artifacts/hype_30m_k2_v2_1_dynamic_atr_bracket_mc_2026-07-10.csv)
- [Start time](../artifacts/hype_30m_k2_v2_1_dynamic_atr_bracket_start_2026-07-10.csv)
- [Phase](../artifacts/hype_30m_k2_v2_1_dynamic_atr_bracket_phase_2026-07-10.csv)
- [Stress](../artifacts/hype_30m_k2_v2_1_dynamic_atr_bracket_stress_2026-07-10.csv)
