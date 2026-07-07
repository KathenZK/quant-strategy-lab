# TRX-1H-Adaptive-Regime

`TRX-1H-Adaptive-Regime`（短 id：`TRX-1H-AR`）是 Binance USD-M Futures `TRXUSDT` perpetual `1h` 多指标自适应策略研究家族，与 BTC、ETH、SOL、HYPE 或其他资产 family 无版本继承关系。

## 研究目标

- 数据：运行时最近两年的全部闭合 `1h` K，直接刷新自 Binance FAPI，并保存 raw/normalized 数据湖分区、资金费历史和合约过滤器快照。
- OOS：最后三个月固定为 locked out-of-sample；搜索、排序、参数微调和 ensemble 冻结不得读取该区间。
- 硬门槛：年化权益倍率 `>=10.0x`（年化收益 `>=900%`）、胜率 `>=50%`、最大回撤严格小于 `20%`。
- 执行：闭合 K 产生信号，下一根 `1h` open 市价成交；入场后立即具备 stop-market/TP 保护；同 K 双触发按 stop-first；跳空穿越 stop 按 open 成交。
- 成本：`0.001` fee/fill、`4 bps` adverse slippage/fill，并计入 Binance 历史资金费。

## 指标与搜索面

搜索覆盖 EMA/MACD、RSI、Stochastic、CCI、Williams %R、ADX/DI、ATR、Bollinger、Keltner、Donchian、rolling VWAP、成交量、动量、wick/body 结构、`4h/12h/1d` 闭合 regime、资金费过滤、固定/风险预算仓位、固定 bracket/trailing exit 及 long/short/both。

## 当前状态

`NO-GO / V1, V2 and V3 diagnostic versions registered / recent adaptation search no-hit / not promoted / not live-ready`。

两阶段搜索提出 `480,768` 个结构化/随机/邻域配置，另做 `12,936` 个持续 regime 乐观上界变体；prefit hard-shape、locked OOS hard gate 均为 `0` 命中。领先 prefit-selected ensemble 全样本年化权益倍率 `4.077x`、最大回撤 `-19.84%`、胜率 `86.54%`，但 locked OOS 年化权益倍率 `0.844x`、区间收益 `-4.12%`。

按后续研究指令，该领先观察值已正式登记为 `TRX-1H-Adaptive-Regime-V1`；删参干净参数版本已正式登记为 `TRX-1H-Adaptive-Regime-V2`；V2 消融引导微调版本已正式登记为 `TRX-1H-Adaptive-Regime-V3`。V2 与 V1 逐交易路径完全一致；V3 是新交易路径。三者均为 diagnostic only，不生成 canonical live spec。

2026-07-06 已对 V2 完成全参数消融：覆盖 V2 对外暴露 clean 字段槽 `36/36`，one-at-a-time 行数 `211`（含 baseline），prefit 严格改善 `8` 行；执行重放违规 `0`。V2 近期分片仍为 `1m -10.12%`、`3m -4.12%`、`6m +12.80%`、`1y +45.18%`，保持 `NO-GO`。

根据 V2 消融做了一轮 train/validation/prefit-only 微调，选中观察值 `TRX-1H-AR-V2-ABLATION-GUIDED-TUNE-2026-07-06` 并按用户指令登记为 `TRX-1H-Adaptive-Regime-V3`：current full 从 `4.077x annual / -19.84% DD / 86.54% win` 改善到 `5.686x annual / -17.17% DD / 92.47% win`，最近 `1y` 改善到 `2.914x annual / +191.14% / -15.71% DD / 91.84% win`。但 reused holdout 胜率仅 `77.78%`，且没有新增 forward trades / production runner，因此 V3 仍不 promotion。

2026-07-07 已对 V3 完成全参数消融：覆盖 `36/36` 个参数槽，one-at-a-time 行数 `215`（含 baseline），prefit 严格改善行 `0`，执行重放违规 `0`。识别出 `5` 个 dormant 字段并固定，生成 `31` 槽的 V3 clean 参数面（与 V3 逐交易等价）。随后在 clean 面上做微调搜索（两个独立 seed 共 `12,531` 个唯一候选），要求 prefit 年化、胜率、回撤三指标同时严格优于 V3，命中 `0`：收益与胜率/回撤形成明确 trade-off，V3 在此参数面上已是局部最优，参数保持不变。

随后按近期行情适配目标重做一轮搜索：`80,800` 个 unique configs、`42,905` 个可评估、`1,225` 个 ensemble；recent hard hits 仍为 `0`。最佳观察值 `ENS_REC__TRX_1H_AR_REC_N011284__TRX_1H_AR_REC_N031489` 最近 `1y` 为 `2.227x annual / +122.58% / -10.67% DD / 79.49% win / 39 trades`，最近 `3m` 为 `+22.40% / -4.14% DD / 100% win / 9 trades`，但离 `>=10x` 年化门槛很远；曝光缩放至 `5x` 也只有最近 `1y 4.724x` 且 DD 已超过 `20%`，因此不登记为版本。

## 入口

- `trx-1h-ar-core-ledger.md`：家族主账。
- `decision-log.md`：研究决策。
- `scripts/fetch_trx_binance_1h.py`：两年 K 线、资金费、合约快照抓取与质量审计。
- `scripts/research_trx_1h_adaptive_regime_search.py`：locked OOS 多指标宽搜索。
- `scripts/research_trx_1h_adaptive_regime_refine.py`：仅基于 prefit 结果的参数邻域搜索。
- `scripts/audit_trx_1h_persistent_regime_boundary.py`：持续趋势/均值回归持仓机制的偏乐观上界审计。
- `scripts/audit_trx_1h_live_feasibility.py`：领先观察值的精确复现、延迟/成本压力和生产控制审计。
- `scripts/trx_1h_ar_v2.py`：`V2` clean 参数实现与 V1 逐交易等价性校验。
- `scripts/trx_1h_ar_v3.py`：`V3` 微调参数实现与配置导出。
- `scripts/trx_1h_ar_v3_clean.py`：`V3` clean 参数面实现与逐交易等价性校验。
- `scripts/research_trx_1h_ar_v2_full_ablation.py`：`V2` 对外 clean 参数全量消融、最近 `1d/7d/1m/3m/6m/1y` 分片和逐笔执行重放审计。
- `scripts/research_trx_1h_ar_v2_ablation_guided_tune.py`：基于 V2 消融与 clean-surface pair pool 的微调观察；只用 train/validation/prefit 选参。
- `scripts/research_trx_1h_ar_v3_full_ablation.py`：`V3` 全参数消融、dormant 字段识别、标准分片和逐笔执行重放审计。
- `scripts/research_trx_1h_ar_v3_clean_tune.py`：V3 clean 参数面随机邻域微调（no-hit）；只用 train/validation/prefit 选参。
- `scripts/research_trx_1h_ar_recent_adaptation_search.py`：解锁近期行情后的近期适配复搜、标准分片、曝光缩放和逐笔执行复核。
- `research-notes/trx-1h-ar-search-conclusion-2026-07-03.md`：本轮总报告。
- `research-notes/trx-1h-ar-v2-ablation-guided-tune-2026-07-06.md`：V2 消融引导微调观察。
- `research-notes/trx-1h-ar-v3-clean-tune-2026-07-07.md`：V3 clean 参数面微调 no-hit 结论与三目标 trade-off 证据。
- `canonical-specs/trx-1h-ar-v3-parameter-spec-2026-07-06.md`：V3 全参数说明与 V2/V3 差异。
- `ablations/trx-1h-ar-v1-full-parameter-ablation-2026-07-05.md`：V1 原始 `StrategyConfig` 全字段消融与 V2 clean 参数面来源。
- `ablations/trx-1h-ar-v2-full-parameter-ablation-2026-07-06.md`：V2 全参数消融、严格分片和实盘可执行性复核。
- `ablations/trx-1h-ar-v3-full-parameter-ablation-2026-07-07.md`：V3 全参数消融、dormant 字段识别、clean 参数面和执行复核。
- `diagnostics/trx-1h-ar-recent-adaptation-search-2026-07-03.md`：近期适配复搜 `NO-GO` 证据。
- `live-specs/trx-1h-ar-live-feasibility-2026-07-03.md`：实盘可行性 `NO-GO` 证据。
- `artifacts/`：可复现证据；非 Markdown 产物默认由 `.gitignore` 忽略。
