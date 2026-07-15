# HYPE-CC-V35 ADX/DI 强趋势逆向禁入诊断（2026-07-14）

## 结论

本轮针对“不要在明确趋势中逆势开单”重新定义过滤器，没有沿用双 EMA 的全时段严格顺趋势门：

```text
ADX < threshold:
    趋势不明确，保留 V35 原双向反转机会

ADX >= threshold and +DI > -DI:
    只允许做多，禁止做空

ADX >= threshold and -DI > +DI:
    只允许做空，禁止做多
```

ADX 本身只表示趋势强度，方向必须由 `+DI/-DI` 给出。原 V35 的 `96` 根 / `5%` 趋势过滤继续保留，ADX/DI 仅作为额外的新开仓禁入层。

预先声明的 20 组粗网格中，训练段相对最优是 `ADX28 >= 25`。它在训练段滚动选择窗略优于 V35，但改善不是稳定高原；在 `2026-06-01 03:15 UTC` 之后的 holdout 中只拦截 1 次候选入场，收益反而从 `-17.49%` 恶化到 `-19.93%`。

**结论：ADX/DI 强趋势逆向禁入未通过，不登记 `HYPE-CC-V36`，不修改 V35 runner 或 dry-run 配置。**

## 数据与质量

| 项目 | 口径 |
| --- | --- |
| 交易所 / 市场 | Binance USD-M Futures |
| 标的 | `HYPEUSDT` 永续 |
| 周期 | `15m` |
| UTC 数据范围 | `2025-05-30 10:30` 至 `2026-07-14 11:15` |
| OHLCV / mark price | 各 39,364 根 |
| funding | 2,457 条，最大间隔 8 小时 |
| 缺失 / 重复 | OHLCV、mark、funding 均为 0 |
| 关键空值 / 非法 OHLC | 0 |
| raw / normalized 不一致 | OHLCV 与 mark 均为 0 |

mark-price 数据通过 Binance `/fapi/v1/markPriceKlines` 补齐并重审，证据见
[mark-price 数据质量产物](../artifacts/hype_cc_binance_mark_15m_refresh_2026-07-14.json)。

## 指标与信号口径

### Wilder 风格 ADX / DI

```text
up_move   = high[t] - high[t-1]
down_move = low[t-1] - low[t]

+DM = up_move   if up_move > down_move and up_move > 0 else 0
-DM = down_move if down_move > up_move and down_move > 0 else 0

TR = max(
    high[t] - low[t],
    abs(high[t] - close[t-1]),
    abs(low[t] - close[t-1]),
)

RMA(x, n) = EWM(x, alpha=1/n, adjust=False, min_periods=n)

+DI = 100 * RMA(+DM, n) / RMA(TR, n)
-DI = 100 * RMA(-DM, n) / RMA(TR, n)
DX  = 100 * abs(+DI - -DI) / (+DI + -DI)
ADX = RMA(DX, n)
```

全部指标只使用当前及以前已闭合的 `15m high/low/close`。ADX 或 DI 未完成 warmup、非有限值或 `+DI == -DI` 时禁止开仓。

### 预声明网格

```text
ADX window = [14, 28, 56, 96]
threshold  = [20, 25, 30, 35, 40]
共 20 组
```

没有在已知 holdout 上继续细调窗口或阈值。

## 执行与成本

- 信号在已闭合 K 线上确认，下一根 K open 入场。
- 入场 K 当根 mark high/low 可以触发保护价。
- 同 K 同时触发止损和止盈时，止损优先。
- 主成本：每次成交手续费 `0.00045`，不利滑点 `0.0004`。
- Binance 压力成本：每次成交手续费 `0.001`，不利滑点 `0.0004`。
- funding 按 Binance funding history 计入。
- 最近 `1d/7d/1m/3m/6m/1y` 只作审计，不参与选参。

## V35 基线对账

原冻结窗口 `2025-05-30 10:30` 至 `2026-06-01 03:00 UTC` 精确复现当前家族本地基线：

| 指标 | 当前可复现值 |
| --- | ---: |
| 收益 | +7713.71% |
| 最大回撤 | -33.28% |
| Sharpe | 4.56 |
| 开仓 | 339 |
| 止损 / 止盈 / 提前平 | 109 / 187 / 43 |

## 训练段滚动选择窗

选择数据截止 `2026-06-01 03:00 UTC`。使用 10 个 30 天窗口，首窗前保留 70 天历史用于指标与策略 warmup；这些窗口用于候选选择，不冒充最终未观察 OOS。

| 方案 | 正收益窗 | 收益中位数 | Sharpe 中位数 | 回撤中位数 | 最差回撤 | 交易中位数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| V35 baseline | 70% | +42.43% | 4.22 | -22.65% | -29.91% | 28.0 |
| ADX28 >= 25 | 70% | +42.81% | 4.77 | -22.65% | -27.59% | 27.5 |
| ADX14 >= 35 | 80% | +41.04% | 4.56 | -21.93% | -27.39% | 26.0 |

`ADX28 >= 25` 在预先定义的训练门槛上通过，但只有一个相邻组合维持不弱于基线，未形成至少两个稳健邻居的参数高原。`ADX14 >= 35` 也通过训练门槛，但与最优行不构成连续局部高原。

完整结果见 [ADX/DI 网格](../artifacts/hype_cc_v35_adx_di_grid_2026-07-14.csv) 和
[逐窗结果](../artifacts/hype_cc_v35_adx_di_rolling_2026-07-14.csv)。

## 最终 holdout

窗口：`2026-06-01 03:15` 至 `2026-07-14 11:15 UTC`。

| 方案 | 收益 | 最大回撤 | Sharpe | 开仓 | 被 ADX/DI 禁入 |
| --- | ---: | ---: | ---: | ---: | ---: |
| V35 baseline | -17.49% | -36.24% | -1.49 | 39 | 0 |
| ADX28 >= 25 | -19.93% | -36.24% | -1.85 | 39 | 1 |

`ADX14 >= 35` 在 holdout 中与 `ADX28 >= 25` 产生相同交易结果，同样为 `-19.93% / -36.24%`。两个训练预通过候选都没有改善最终 holdout。

该过滤器只拦到一个满足原 V35 条件的候选信号，但路径状态使多空开仓结构从 `20/19` 变为 `19/20`，最终亏损增加约 `2.44` 个百分点。证据不支持把这条规则接入现有 runner。

## 最近切片

| 窗口 | V35 收益 / 回撤 | ADX28 >= 25 收益 / 回撤 | 判断 |
| --- | --- | --- | --- |
| 1d | -0.34% / -7.44% | -3.29% / -5.72% | 各 1 笔未平仓，证据不足 |
| 7d | +2.58% / -10.29% | -0.45% / -10.29% | ADX 较差 |
| 1m | -19.38% / -30.30% | -21.77% / -30.30% | ADX 较差 |
| 3m | -8.43% / -46.76% | +4.43% / -46.76% | ADX 收益改善，回撤不变 |
| 6m | +530.63% / -46.76% | +568.95% / -46.76% | ADX 略好 |
| 1y | +5980.07% / -46.76% | +4976.27% / -46.76% | 长期收益与 Sharpe 下降 |

完整切片见 [recent artifact](../artifacts/hype_cc_v35_adx_di_recent_2026-07-14.csv)。

## 全窗口与成本压力

| 口径 | V35 baseline | ADX28 >= 25 |
| --- | ---: | ---: |
| next-open 收益 | +6647.82% | +5533.78% |
| next-open 最大回撤 | -46.76% | -46.76% |
| next-open Sharpe | 4.07 | 3.98 |
| next-open 开仓 | 379 | 370 |
| Binance 成本压力收益 | +3282.24% | +2757.57% |
| Binance 成本压力最大回撤 | -49.31% | -49.31% |
| Binance 成本压力 Sharpe | 3.49 | 3.39 |

全窗口共发生 20 次 ADX/DI 禁入检查，最终少开 9 笔，但没有降低最大回撤，收益和 Sharpe 均下降。其风险收益交换不成立。

机器可读摘要见 [summary JSON](../artifacts/hype_cc_v35_adx_di_summary_2026-07-14.json)，
选中候选交易见 [selected trades](../artifacts/hype_cc_v35_adx_di_selected_trades_2026-07-14.csv)。

## 决策

1. 不登记 `HYPE-CC-V36`。
2. 不修改 V35 参数规格、quant-runner 实现或 dry-run 配置。
3. ADX 不能单独表达方向；若未来重测，必须继续明确绑定 `+DI/-DI`。
4. 当前失败不是阈值不够细的证据。继续按 holdout 亏损微调 ADX 窗口或阈值会形成二次过拟合。
5. 如果仍需降低逆趋势风险，更合理的下一步是先做 V35 亏损交易的 regime attribution，确认“强趋势逆向单”是否真是主要亏损来源，再决定过滤器，而不是继续替换技术指标。

## 复现入口

- 研究脚本：[research_hype_cc_v35_adx_di_trend_block.py](../scripts/research_hype_cc_v35_adx_di_trend_block.py)
- 共用 V35 回放与数据审计：[research_hype_cc_v35_dual_ema_filter.py](../scripts/research_hype_cc_v35_dual_ema_filter.py)
- mark 补齐脚本：[fetch_hype_cc_binance_mark_15m.py](../scripts/fetch_hype_cc_binance_mark_15m.py)
- 家族主账：[hype-cc-15m-milestone-comparison.md](../hype-cc-15m-milestone-comparison.md)
- 决策日志：[decision-log.md](../decision-log.md)
