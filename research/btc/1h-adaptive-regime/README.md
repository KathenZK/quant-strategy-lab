# BTC-1H-Adaptive-Regime

`BTC-1H-Adaptive-Regime`（短 id：`BTC-1H-AR`）是 Binance USD-M Futures `BTCUSDT` perpetual `1h` 多指标自适应策略研究家族，与任何 HYPE family 无版本继承关系。

## 研究目标

- 数据：运行时最近两年的全部闭合 `1h` K，直接刷新自 Binance FAPI，并保存 raw/normalized 数据湖分区、资金费历史和合约过滤器快照。
- OOS：最后三个月固定为 locked out-of-sample；搜索和排序不得读取该区间。
- 硬门槛：年化权益倍率 `>=10.0x`（即年化收益 `>=900%`）、胜率 `>=50%`、最大回撤严格小于 `20%`。
- 执行：闭合 K 产生信号，下一根 `1h` open 市价成交；入场后立即具备 stop-market/TP 保护；同 K 双触发按 stop-first；跳空穿越 stop 按 open 成交。
- 成本：`0.001` fee/fill、`4 bps` slippage/fill，并计入 Binance 历史资金费。

## 指标与搜索面

搜索覆盖 EMA/MACD、RSI、Stochastic、CCI、Williams %R、ADX/DI、ATR、Bollinger、Keltner、Donchian、rolling VWAP、成交量、动量、wick/body 结构、`4h/12h/1d` 闭合 regime、固定/风险预算仓位、固定 bracket/trailing exit 及 long/short/both。

## 当前状态

`V1 registered diagnostic baseline；V2 registered paper-audit observation；not live-ready`。

2026-07-02 共生成 `300,768` 组配置（`768` curated + `300,000` random），`41,898` 组满足最低评分条件，prefit 硬门槛命中 `0`。prefit 预冻结冠军为 `Keltner breakout + CCI reversal` ensemble：prefit `2.82x` 年化倍率、`-18.68%` 回撤、`68.29%` 胜率；最近三个月 locked OOS 降至 `0.17x`、`-42.73%`、`38.46%`。该边界按用户要求登记为 `BTC-1H-Adaptive-Regime-V1`，但不生成 live spec。

V1 全参数消融覆盖两腿 `78/78` 个字段槽：`27` 个 active tunable、`12` 个 contract fixed、`35` 个 baseline fixed、`4` 个 neutral fixed。clean interface 仅保留 `27` 个可调参数，删除或硬编码 `51` 个槽，和 V1 逐笔完全等价。

clean tune 每腿各采样 `150,000` 组，组合 `122,500` 组；得到 scaled frontier observation：prefit `3.18x / -13.99% / 84.85%`，reused holdout `1.52x / -13.48% / 81.82%`，current full `2.88x / -13.99% / 84.42%`；K+2 prefit `2.50x / -19.70% / 80.30%`。该观察已按用户要求登记为 `BTC-1H-Adaptive-Regime-V2`，但仍需新增 forward trades 与生产 runner，状态为 `paper-audit observation / not live-ready`。

## 入口

- `btc-1h-ar-core-ledger.md`：家族主账。
- `canonical-specs/btc-1h-ar-v1-baseline-spec.md`：V1 完整冻结规格。
- `decision-log.md`：研究决策。
- `scripts/fetch_btc_binance_1h.py`：两年 K 线、资金费、合约快照抓取与质量审计。
- `scripts/research_btc_1h_adaptive_regime_search.py`：locked OOS 多指标宽搜索。
- `scripts/audit_btc_1h_adaptive_regime_boundary.py`：延迟、成本、仓位、单腿、参数邻域、月度、bootstrap 与实盘可执行审计。
- `scripts/btc_1h_ar_v1.py`：V1 冻结配置与复现入口。
- `scripts/research_btc_1h_ar_v1_full_ablation.py`：V1 `78/78` 字段槽全参数消融。
- `scripts/btc_1h_ar_v1_clean.py`：27 参数 clean-equivalent interface。
- `scripts/research_btc_1h_ar_v1_clean_tune.py`：prefit-only 双腿高密度微调。
- `scripts/audit_btc_1h_ar_v1_scaled_frontier.py`：最终缩放前沿、K+2、成本、邻域与 forward-readiness 审计。
- `diagnostics/btc-binance-1h-data-quality-2026-07-02.md`：两年数据质量报告。
- `diagnostics/btc-1h-adaptive-regime-search-2026-07-02.md`：30 万组主搜索报告。
- `diagnostics/btc-1h-adaptive-regime-boundary-audit-2026-07-02.md`：最终 NO-GO 审计。
- `ablations/btc-1h-ar-v1-full-parameter-ablation-2026-07-02.md`：V1 全参数消融与删参分类。
- `research-notes/btc-1h-ar-v1-clean-parameter-tune-2026-07-02.md`：clean surface 微调。
- `research-notes/btc-1h-ar-v1-scaled-frontier-audit-2026-07-02.md`：当前首选 paper-audit observation。
- `artifacts/`：可复现证据；默认由 `.gitignore` 忽略。
