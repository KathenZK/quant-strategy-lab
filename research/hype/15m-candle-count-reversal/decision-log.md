# HYPE-CC 决策日志

这是 HYPE candle-count reversal 研究的家族级阅读路径。

## 当前边界

- 本家族属于策略规格与归档材料。
- 它不是 active package code 的事实来源。
- 需要复现逻辑时，应使用 specs 在一次性脚本或生产 runner 中重建。

## 版本记录

- `HYPE-CC-V10`：ATR dynamic stop 基线。
- `HYPE-CC-V13`：全 ATR288 双向限价规格。
- `HYPE-CC-V18`：ATR672 稳健基线。
- `HYPE-CC-V19`：仅多头 three-opposite-candle early exit。
- `HYPE-CC-V20`：inclusive opposite-three exit 变体。
- `HYPE-CC-V21`：双向 opposite-three exit 变体。
- `HYPE-CC-V35`：可复现性与过拟合诊断检查点。

## 决策记录

- `2026-06-29`：`diagnostics/hype-cc-v35-live-underperformance-review-2026-06-29.md` 在 Binance live 表现不佳、6 月 OHLCV-proxy OOS replay 和阿里云 HypePulse live DB / 日志 / 交易所快照审计后，将 `HYPE-CC-V35` 下调为 live-underperformance / execution-risk diagnostic。当前归因优先级是策略 / 行情样本外亏损，其次是实盘成交摩擦放大；远端审计未发现服务卡死、当前保护单缺失、warning storm 或大幅入场滑点等足以把亏损主因改判为代码 bug 的证据。在补齐 2026-06-01 之后 mark-price replay 和 live-realistic replay 前，不要把 `+8357.56%` 或 `58.53%` 胜率作为 live expectation 引用。
- `2026-06-29`：`diagnostics/hype-cc-v35-parameter-overfit-rediagnosis-2026-06-29.md` 将 V35 参数级风险重新分层：`10/8` 核心信号和 `trend_window_bars=96` 是高风险样本内尖点，双向 `12/9` counter 和 `target_atr_pct=0.006` 是后期收益增强 / 放大层；ATR672、TP 5.5、cooldown 8、gap 8 等机制可保留研究，但具体数值需重新做 live-realistic OOS。不要从 V35 继续微调，应回退到更少后期增强层的基线重新评估。
- `2026-07-08`：确认 `HYPE-CC-V35` 确实在 quant-runner 以 `hype_candle_count` dry-run 配置运行（`configs/dryrun.toml`），状态更新为 `dry-run / forward-test required`，并建立 [runner-tracking/README.md](runner-tracking/README.md)。历史 live underperformance 继续作为 execution-risk 证据保留；当前 dry-run 是重新观察/对账状态，不等于 live 批准。首份 runner 观察报告缺失前不得升级 `live`，也不得据此给出新的 `NO-GO`。
- `2026-07-08`（live-specs 缺口记录）：治理审计发现 V35 进入 runner 早于 `lab-runner-handoff` 契约成文，lab 侧没有 `live-specs/` 交接规格，runner 侧以 `HYPE-CANDLE-COUNT-V35-SPEC.md` + [specs/hype-v35-reproducible-params.md](specs/hype-v35-reproducible-params.md) 为实现事实源，属 grandfathered 例外。升级 `live` 前必须按 handoff 契约补写 `live-specs/` 交接规格并与 runner SPEC 互链；在此之前该缺口保持为 live-readiness blocker。
- `2026-07-14`：[`diagnostics/hype-cc-v35-dual-ema-trend-filter-2026-07-14.md`](diagnostics/hype-cc-v35-dual-ema-trend-filter-2026-07-14.md) 对 V35 叠加 13 组双 EMA 顺趋势禁入进行滚动 OOS 与后段 holdout；相对最优 `EMA24/672` 虽改善 2026-06-01 后亏损，但训练段 OOS 收益、Sharpe 与最差回撤均弱于 V35，长期收益衰减明显。结论为候选失败，不登记 `HYPE-CC-V36`，不修改 V35 runner / dry-run。
- `2026-07-14`：[`diagnostics/hype-cc-v35-adx-di-trend-block-2026-07-14.md`](diagnostics/hype-cc-v35-adx-di-trend-block-2026-07-14.md) 改用“仅在 ADX 强趋势中按 `+DI/-DI` 禁止逆向开仓”的较弱过滤；训练段相对最优 `ADX28 >= 25` 略有改善，但未形成参数高原，最终 holdout 从 V35 的 `-17.49%` 恶化至 `-19.93%`。结论仍为候选失败，不登记 `HYPE-CC-V36`，不修改 V35 runner / dry-run。

## 证据政策

优先使用家族文档，而不是 archived code。如果代码与文档不一致，先引用文档，再通过重新生成一次性回测进行验证。
