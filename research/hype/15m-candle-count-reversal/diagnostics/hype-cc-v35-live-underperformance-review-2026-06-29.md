# HYPE-CC-V35 实盘表现复审 2026-06-29

## 结论

`HYPE-Candle-Count-Reversal-V35` 当前不应继续按 live / paper-live candidate 解释。更准确的状态是：

```text
live-underperformance + execution-risk diagnostic
```

本次复审不是证明 V35 的 candle-count 反转机制完全无效，而是确认原 `+8357.56%` 回测不能作为实盘收益预期。补充读取本地数据湖后，6 月 Binance OHLCV 代理回放本身已经是亏损段；进一步读取阿里云 HypePulse live DB、systemd 日志和交易所快照后，当前更像是策略 / 行情样本外不利为主，实盘成交摩擦、mark 触发路径和小账户精度继续放大亏损。现有证据不支持把 Binance 亏损主要归因为实盘代码 bug。

## 复审输入

本次复审基于：

- `canonical-specs/hype-v35-reproducible-params.md`
- `diagnostics/hype-v35-overfit-diagnosis.md`
- `hype-cc-15m-milestone-comparison.md`
- `legacy-canvas/hype-v35-cross-exchange-execution.md`
- `../15m-live-execution-feasibility-audit-2026-06-25.md`
- 2026-06-29 运维口径记录的 Binance / Hyperliquid 实盘摘要
- `scripts/replay_hype_cc_v35_oos_proxy_2026_06_29.py`
- `artifacts/hype_cc_v35_oos_proxy_review_2026-06-29.json`
- `artifacts/hype_pulse_aliyun_live_audit_2026-06-29.json`

限制：

- 本地 Binance HYPEUSDT `15m` OHLCV 已覆盖至 `2026-06-26 04:00 UTC`，且 6/1 之后无 15m 缺口。
- 但本地 Binance `mark_price_klines` 只覆盖至 `2026-06-01 03:00 UTC`，无法精确复现 V35 原 `mark_high/mark_low` 触发口径。
- 本次新增的 6 月 OOS replay 使用 `mark_high=trade high`、`mark_low=trade low` 的 OHLCV 代理触发。它可判断方向性，但不是原 V35 mark-trigger 精确口径。
- 本地 Binance funding 在 6/1 之后没有非零对齐记录；本次代理结果基本不含 funding 影响。
- Binance 仍有 1 笔未平空单，实盘统计不是最终闭合批次。
- 阿里云审计为只读状态快照，没有重启服务、修改 env 或下单；交易所侧实时价格和未平仓 PnL 会随行情继续变化。

## 回测基准与当前实盘对比

| 口径 | 开仓/已平 | 止盈 | 止损 | 提前平 | 胜率/止盈占比 | 已知净平仓 PnL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| V35 全样本回测 | 340 / 340 | 188 | 109 | 43 | 58.53% 净胜率 | +8357.56% |
| V35 回测最后 7 天 | 7 / 7 | 2 | 4 | 1 | 28.57% | -19.38% |
| 6/1 后 OHLCV 代理回放 | 24 / 24 | 11 | 11 | 2 | 45.83% 胜率 | -18.98% |
| 6/5 后 OHLCV 代理回放 | 19 / 19 | 9 | 10 | 0 | 47.37% 胜率 | -18.12% |
| Binance 实盘 | 19 / 18 | 5 | 12 | 1 | 27.78% 止盈占比 | 约 -30.99 USDT |
| Hyperliquid 实盘 | 17 / 17 | 7 | 7 | 3 | 41.18% 止盈占比 | 约 +6.14，早期 4 笔缺 PnL 明细 |

当前 Binance 的 18 笔已平样本虽然短，但形态与 V35 全样本回测差距很大：

```text
若真实胜率按 V35 回测 58.53% 估计：
- 18 笔里胜利 <= 5 笔的二项概率约 0.83%
- 18 笔里胜利 <= 6 笔的二项概率约 2.76%

若真实止损率按 V35 回测 109/340 = 32.06% 估计：
- 18 笔里止损 >= 12 笔的二项概率约 0.27%
```

这些数值不能当严格显著性检验，因为交易不是独立同分布，实盘成交也不同于回测；但作为风险告警已经足够。当前表现不是“正常波动里很轻微的偏差”。

## 6 月本地数据湖复核

`scripts/replay_hype_cc_v35_oos_proxy_2026_06_29.py` 读取本地数据湖后得到：

```text
精确 V35 trade+mark+funding replay 数据：
- rows: 35,203
- start: 2025-05-30 10:30 UTC
- end:   2026-06-01 03:00 UTC
- missing_15m_bars: 0

OHLCV proxy 数据：
- rows: 37,607
- start: 2025-05-30 10:30 UTC
- end:   2026-06-26 04:00 UTC
- 6/1 之后 rows: 2,405
- 6/1 之后 missing/null: 0
- proxy: mark_high=trade high, mark_low=trade low
```

关键窗口：

| 窗口 | 收益 | 最大回撤 | 交易 | 胜 / 负 | Exit mix |
| --- | ---: | ---: | ---: | ---: | --- |
| `2026-06-01 03:00` → `2026-06-26 04:00` | `-18.98%` | `-28.98%` | 24 | 11 / 13 | take 11 / stop 11 / early 2 |
| `2026-06-05 00:00` → `2026-06-26 04:00` | `-18.12%` | `-28.98%` | 19 | 9 / 10 | take 9 / stop 10 |
| `2026-06-10 00:00` → `2026-06-26 04:00` | `-27.37%` | `-28.17%` | 15 | 6 / 9 | take 6 / stop 9 |
| `2026-06-13 00:00` → `2026-06-26 04:00` | `-10.56%` | `-22.35%` | 14 | 7 / 7 | take 7 / stop 7 |
| `2026-06-01 03:00` → `2026-06-15 13:00` | `+2.28%` | `-11.64%` | 12 | 6 / 6 | take 6 / stop 4 / early 2 |

这组结果改变了“诊断到底偏哪边”的判断：

- 不是“回测同期应该赚钱、实盘却亏”，因为 6 月 OHLCV 代理回放本身就是 `-18%` 到 `-27%` 的亏损区间。
- 从 `2026-06-05` 起算，代理回放正好 19 笔，交易数与 Binance 实盘 `19` 笔接近，说明实盘没有明显少跑一大段理论盈利序列。
- Binance 实盘仍比代理差：代理 19 笔是 stop 10 / take 9，实盘已平 18 笔是 stop 12 / take 5 / early 1，且净 PnL 为负。这更像实盘 mark 触发、市场单滑点、精度/手续费和小账户摩擦把坏段进一步放大，而不是唯一由代码漏信号造成。
- Hyperliquid 到 `2026-06-15 21:00 UTC+8` 停服前，代理口径到 `2026-06-15 13:00 UTC` 为 `+2.28%`、12 笔 6 胜 6 负；这与 Hyperliquid 实盘 `+6.14` 的方向一致。后续 Binance 继续运行进入了更差的 6/17 之后窗口。

## 阿里云实盘审计

`artifacts/hype_pulse_aliyun_live_audit_2026-06-29.json` 保留了 2026-06-29 对阿里云 HypePulse 的只读审计摘要。关键事实：

- 远端代码在 `main`，commit `b802e6236c29bd5114c231aa2605e0cb9a3d7eac`；未见代码脏改动，只有未跟踪 `logs/`。
- `hype-pulse-binance-live` 自 `2026-06-17 15:07:59 CST` 起持续运行，最近 72 小时 journal warning/error 为 0；最新处理 K 线为 `2026-06-29 07:00 UTC`，与审计时点相符，不是卡死。
- `hype-pulse-hyperliquid-live` 已在 `2026-06-15 21:18:23 CST` 正常停止，DB 停在 `2026-06-15 13:00 UTC`，空仓。
- Binance live 当前状态 `paused_reason=null`、`risk_multiplier=0.125`，仍持有一笔 `0.27 HYPE` 空单，均价 `62.23`，交易所侧同时存在 reduce-only `TAKE_PROFIT_MARKET 60.052` 和 `STOP_MARKET 64.408` 两张保护单。
- Binance env 的 `MAX_NOTIONAL_QUOTE=0`，即不使用 300U 上限，而是完全按账户权益与 allocation 算名义金额；在当前小账户下不会超过 300U，但这是与原 V35 固定 cap 口径不同的实盘配置点。

交易序列需要剔除 3 笔 `test_order_cycle` 小额强制测试单。剔除后，Binance 正式策略闭合样本为 18 笔：

```text
take: 5
stop: 12
early_main: 1
sum closedPnl: -30.39772999 USDT
sum fees:      -0.59637260 USDT
net:           -30.99410259 USDT
```

逐笔配对计划价与实盘成交价后，执行摩擦的量级是：

```text
official closed trades: 18
entry slippage adverse sum:       -0.00242 USDT
stop/take exit adverse slippage:  +0.4536887 USDT
fees:                             +0.5963726 USDT
net loss:                         -30.99410259 USDT
```

这说明 Binance 亏损主体不是入场滑点，也不是 stop/take 市价单滑点单独造成；实盘摩擦大约解释 `~1.05 USDT` 的额外拖累，核心仍是该段信号/exit mix 本身偏向止损。代码层面暂未看到当前 Binance 服务卡死、保护单缺失、warning storm、重复开仓或大幅入场滑点等可以解释 `-30.99 USDT` 的主因。

## 是否过拟合

判断：V35 有明显样本内特化 / 过拟合风险；6 月 OOS 代理回放进一步显示，当前差表现首先是策略在新行情段失效 / 回撤，而不是单纯实盘代码错误。

已有 `hype-v35-overfit-diagnosis.md` 给出的关键风险仍成立：

- `10/8` 是最大依赖点，`9/7`、`10/7`、`11/8`、`12/9` 都明显弱于基准。
- `trend_window_bars=96` 是强敏感点，`72/120/144/192/288` 都显著弱于 `96`。
- 双向 `12/9` counter 不是孤点，但仍是 V35 后期新调出来的收益增强层。
- `target_atr_pct=0.006` 不是 alpha，只是收益和回撤放大器。

因此，V35 的风险画像不是“单一参数尖峰”，而是多个敏感参数叠加后选出最高收益 / Sharpe 组合。它在滚动 90 天窗口上曾经全部正收益，说明不是只靠单一历史片段；但上线后的短样本恶化和执行审计问题表明，这个稳健性不足以支持 live promotion。

## 实盘偏差来源

`15m-live-execution-feasibility-audit-2026-06-25.md` 已经把 `HYPE-Candle-Count-Reversal` 降级为 execution-risk / diagnostic。对 V35 最关键的偏差是：

1. 回测在信号 bar 的 close 入场，实盘只能在信号确认后市价或下一可成交时点入场。
2. `early_main`、`early_counter_opposite`、`early_counter_favorable` 回测按当前 close 平仓，实盘确认条件时已经知道 close，无法保证按该 close 成交。
3. ATR 止盈止损用 mark high / low 触发后按理论 stop/take 价成交，实盘的 `STOP_MARKET` / `TAKE_PROFIT_MARKET` 会按订单簿成交。
4. 同一根 15m K 内触发路径只有 high/low，无法还原 tick 级先后顺序。
5. Binance 小资金账户里，手续费、滑点、数量精度和保护单触发误差占比更高。
6. 6 月实盘期间曾有执行中断和保证金问题，回测没有这类连续性风险。

这些偏差方向对 Binance 近期表现尤其不利：止损会更差、止盈可能少赚，且小账户摩擦占比更高。但本次远端审计量化后，已闭合 Binance 正式策略单的 stop/take 出口滑点约 `0.45 USDT`、手续费约 `0.60 USDT`，它们放大亏损但不是主要亏损来源。

## 决策

当前不建议继续把 Binance V35 作为收益型实盘候选运行。可选口径只有两个：

1. 暂停 Binance V35，等待 live-realistic replay、实盘交易逐笔对齐和参数重审完成。
2. 若继续运行，只应视为极小仓位数据采集，不应以盈利预期解释；当前 `risk_multiplier=0.125` 是风控降仓结果，不是策略恢复健康的证据。

后续若要重新评估，必须先完成：

- 补齐 Binance 2026-06-01 之后 `15m` mark-price kline，重跑精确 mark-trigger OOS；
- 把 close 入场 / close early exit 改成 live-realistic next-tick 或 next-open；
- 对 stop-market / take-profit-market 增加 slippage stress；
- 用实盘审计库逐笔对齐理论 entry/exit、实盘 entry/exit、触发价、成交价、滑点、手续费和 missed signal；
- 再比较 V31/V35/V36 或更低 `target_atr_pct` 的 live-realistic 版本。

在上述审计前，`HYPE-CC-V35` 保持降级，不再使用 `+8357.56%` 或 58.53% 胜率作为实盘预期。当前归因优先级是：策略 / 行情样本外亏损 > 实盘成交摩擦放大 > 低优先级继续排查的代码或状态机问题。阿里云只读审计没有发现足以推翻这个归因顺序的实盘代码证据。
