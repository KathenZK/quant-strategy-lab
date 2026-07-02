# HYPE-1H-Adaptive-Regime 核心研究台账

Family：`HYPE-1H-Adaptive-Regime`

Alias：`HYPE-1H-AR`

Created：2026-07-02

## 边界

`HYPE-1H-Adaptive-Regime` 是 Binance USD-M Futures `HYPEUSDT` perpetual `1h` 自适应市场状态研究线。它独立于 `HYPE-15M-Multi-Indicator-Intraday`、`HYPE-EMA-Crossover`、`HYPE-EMA-Trend-Breakout`、`HYPE-5M-Pullback-Trail` 和其他 HYPE 家族。

本台账中的 `V1`、`V2` 只在 `HYPE-1H-Adaptive-Regime` 家族内有效。裸版本号不具有策略身份。

## 当前状态

- 当前登记版本：`HYPE-1H-Adaptive-Regime-V2`。
- 当前状态：`clean equivalent diagnostic baseline / NO-GO / not live-ready / not promoted`。
- 家族实盘判断：`NO-GO`。
- 原因：current full 年化权益倍率低于 `10.0x` 硬门槛，reused holdout 明显降级，K+2/更高滑点压力下回撤穿越 `20%`，且没有生产 runner、重启恢复、交易所订单/仓位对账、missing-bar fail-closed、kill switch 和真实 stop-market 滑点证据。

## 数据与成本口径

- Exchange：Binance。
- Market：USD-M perpetual。
- Symbol：`HYPEUSDT`。
- Timeframe：`1h`。
- 数据：标准 raw/normalized 数据湖，闭合 K `2025-05-30 10:00 UTC` 至 `2026-07-02 02:00 UTC`，共 `9,545` 根。
- 数据质量：missing `0`、duplicate `0`、critical null `0`、OHLCV violation `0`、raw/normalized mismatch `0`、normalized unclosed `0`。
- 资金费：历史资金费 `2,385` 条，按逐笔持仓区间计入。
- 成本：手续费 `0.001/fill`，滑点 `4 bps/fill`。
- 执行：闭合 K 信号，下一根 `1h` open 市价入场；单仓不重叠；同刻冲突 DI-cross 优先；stop-first；gap-open stop 按 open 成交。
- 计分起点：指标 warmup 后 `2025-07-14 10:00 UTC`。

## 版本规则

| 版本 | 说明 |
| --- | --- |
| `HYPE-1H-Adaptive-Regime-V1` | 第一版正式登记基线，来自 `DI-cross + Stoch-reversal` 最强冻结边界；不是 live/paper-live/dry-run/candidate/handoff。 |
| `HYPE-1H-Adaptive-Regime-V2` | V1 全字段消融后的干净等价版本，删除 dormant 或固定状态机字段；DI、Stoch 和 merged 逐笔交易签名与 V1 完全一致；不是 promotion。 |
| 后续版本 | 只有在冻结参数、保留数据质量证据、完成 live-executable 审计并写入本主账后，才可登记为新的 `Vx`；高年化但压力失败的 tune 只能记录为 rejected diagnostic。 |

## 版本台账

| Version | Status | Core idea | Evidence | Decision |
| --- | --- | --- | --- | --- |
| `HYPE-1H-Adaptive-Regime-V1` | diagnostic baseline / NO-GO / not live-ready | `DI-cross` 趋势腿 + `Stoch-reversal` 反转腿，闭合 K 信号、K+1 open 入场；DI fixed ATR bracket，Stoch ATR trailing；固定权益名义仓位，DI 优先合并单仓。 | `canonical-specs/hype-1h-ar-v1-baseline-spec.md`；`ablations/hype-1h-ar-v1-full-parameter-ablation-2026-07-02.md`；`diagnostics/hype-1h-adaptive-regime-boundary-audit-2026-07-01.md` | Current full `9.6838x`、`-19.64%` 最大回撤、`78.26%` 胜率、`69` 笔；reused holdout `5.1305x`。未达 `10.0x` 硬门槛，压力测试缺缓冲，维持 `NO-GO`。 |
| `HYPE-1H-Adaptive-Regime-V2` | clean equivalent diagnostic baseline / NO-GO / not live-ready | 保留 V1 两条腿真实生效参数，删除 `40` 个 dormant 或固定状态机字段槽；策略行为与 V1 完全相同。 | `canonical-specs/hype-1h-ar-v2-clean-baseline-spec.md`；`ablations/hype-1h-ar-v2-full-parameter-ablation-2026-07-02.md`；`research-notes/hype-1h-ar-v2-active-parameter-tune-2026-07-02.md`；`diagnostics/hype-1h-ar-v2-tune-frontier-live-audit-2026-07-02.md`；`research-notes/hype-1h-ar-v2-live-robust-prefit-tune-2026-07-02.md`；`research-notes/hype-1h-ar-v2-window-backtest-2026-07-02.md` | 与 V1 逐笔等价，current full 仍为 `9.6838x / -19.64% / 78.26% / 69 trades`。V2 clean `34` 字段槽全参数消融中，完整 current full + reused holdout target-like 通过 `0` 行；普通微调 `19,600` 组与扩大稳健预拟合 `640,000` 组均未形成更优实盘版本，维持 `NO-GO`。 |

## V1 / V2 冻结指标

| Window | Annual multiple | Annual return | Max DD | Win rate | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Prefit | `11.6665x` | `+1066.65%` | `-16.93%` | `79.25%` | `53` | `7.267` |
| Reused holdout | `5.1305x` | `+413.05%` | `-19.64%` | `75.00%` | `16` | `4.342` |
| Current full | `9.6838x` | `+868.38%` | `-19.64%` | `78.26%` | `69` | `6.486` |

V1 与 V2 的 DI component trade signature、Stoch component trade signature、merged trade signature 均为 exact equal。

## V2 最近窗口复核

| Window | Trades | Win rate | Total return | Max DD | Annual multiple |
| --- | ---: | ---: | ---: | ---: | ---: |
| 最近 7 天 | `1` | `100.00%` | `+3.91%` | `-0.56%` | `7.3908x` |
| 最近 30 天 | `8` | `87.50%` | `+36.09%` | `-16.37%` | `42.5963x` |
| 最近 90 天 | `17` | `70.59%` | `+42.11%` | `-19.64%` | `4.1624x` |
| 最近 180 天 | `35` | `71.43%` | `+165.21%` | `-19.64%` | `7.2364x` |
| 最近 365 天 | `69` | `78.26%` | `+795.75%` | `-19.64%` | `9.6838x` |

滚动 `7d` 切片共 `50` 个，其中 `11` 个零交易窗口；`30d` 切片交易数中位数 `5`，最少 `2`、最多 `10`。短窗口年化只作形状诊断，不作 promotion 依据。

## V2 全参数消融摘要

`ablations/hype-1h-ar-v2-full-parameter-ablation-2026-07-02.md` 覆盖 V2 clean 配置接口的 `34` 个字段槽：DI-cross `15` 个，Stoch-reversal `19` 个；共输出 `98` 行（含 baseline 与两条 leg_removed 诊断行），coverage missing fields 为 `0`。

单字段消融结果：

- Prefit 同时提高年化、降低回撤且胜率 `>=50%`：`1` 行。
- Current full 同时提高年化、降低回撤且胜率 `>=50%`：`13` 行。
- 完整 current full + reused holdout target-like 通过：`0` 行。

因此本轮消融只提供参数敏感性证据，不创建 `V2.1` 或 `V3`，也不改变 `NO-GO / not live-ready` 状态。

## V1 机制摘要

### 腿 A：DI-cross

- 信号：`+DI14 - -DI14` 零轴交叉。
- 过滤：`12 <= ADX14 <= 36`、`RVOL48 >= 2`、`ATR14/close <= 250 bps`、方向化 `ROC24 >= -200 bps`、距 `EMA89 <= 750 bps`、方向与闭合 `12h` EMA regime、K 线实体和最后已知 funding 一致。
- 退出：入场后立即放 `TP=1.5 ATR14`、`SL=4.0 ATR14`，最长 `18` 根 `1h` K。
- 权益暴露：固定 `3.0x`。

### 腿 B：Stoch-reversal

- 信号：`Stoch(21)` K/D 在超卖或超买区反向交叉。
- 过滤：`ADX14 >= 12`、`RVOL48 >= 1`、`200 <= ATR14/close <= 400 bps`、距 `EMA55 <= 2500 bps`、`MACD(8,21,5)` 转向确认。
- 退出：入场后立即放 `SL=4.0 ATR14`，闭合 K 后按 `trail_activation=1.0 ATR`、`trail=1.0 ATR` 更新 trailing stop，最长 `8` 根 `1h` K。
- 权益暴露：固定 `2.0x`；出场后冷却 `24` 根。

## 复现

```bash
uv run python research/hype/1h-adaptive-regime/scripts/fetch_hype_binance_1h.py --refresh
uv run python research/hype/1h-adaptive-regime/scripts/research_hype_1h_ar_v1_full_ablation.py
uv run python research/hype/1h-adaptive-regime/scripts/research_hype_1h_ar_v2_clean_tune.py
uv run python research/hype/1h-adaptive-regime/scripts/research_hype_1h_ar_v2_window_backtest.py
```

## 约束提醒

后续任何 agent 如果按用户要求“登记为 Vx / 记录为 Vx / 写成 Vx”，必须更新本文件的版本规则、版本台账和当前状态；只写 canonical spec、research note 或 decision log 不算完成版本登记。
