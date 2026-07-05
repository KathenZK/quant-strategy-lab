# ETH-1H-Adaptive-Regime

`ETH-1H-Adaptive-Regime`（短 id：`ETH-1H-AR`）是 Binance USD-M Futures `ETHUSDT` perpetual `1h` 多指标自适应策略研究家族，与 BTC、HYPE 及其他资产 family 无版本继承关系。

## 研究目标

- 数据：运行时最近两年的全部闭合 `1h` K，直接刷新自 Binance FAPI，并保存 raw/normalized 数据湖分区、资金费历史和合约过滤器快照。
- OOS：最后三个月固定为 locked out-of-sample；搜索、排序和参数选择不得读取该区间。
- 硬门槛：年化权益倍率 `>=10.0x`（即年化收益 `>=900%`）、胜率 `>=50%`、最大回撤严格小于 `20%`。
- 执行：闭合 K 产生信号，下一根 `1h` open 市价成交；入场后立即具备 stop-market/TP 保护；同 K 双触发按 stop-first；跳空穿越 stop 按 open 成交。
- 成本：`0.001` fee/fill、`4 bps` slippage/fill，并计入 Binance 历史资金费。

## 指标与搜索面

搜索覆盖 EMA/MACD、RSI、Stochastic、CCI、Williams %R、ADX/DI、ATR、Bollinger、Keltner、Donchian、rolling VWAP、成交量、动量、wick/body 结构、`4h/12h/1d` 闭合 regime、固定/风险预算仓位、固定 bracket/trailing exit 及 long/short/both。

## 当前状态

`ETH-1H-Adaptive-Regime-V1 registered diagnostic baseline / NO-GO / not promoted / not live-ready`。

首轮 `600,768` 组广搜的 prefit 冻结冠军已按用户要求登记为 V1。V1 的 locked OOS 为 `0.5196x / -20.87% / 14.29% / 7 trades`，因此登记不改变 NO-GO 状态。预提交 Pareto 精调另生成 `300,000` 个邻域配置，仍为 `0` 个 hard-gate hit，不替换 V1 身份。

V1 全参数消融覆盖两腿 `78/78` 个字段槽：`33` 个 active tunable、`30` 个 baseline-fixed remove、`3` 个 neutral-fixed remove、`12` 个 contract fixed。clean interface 删除或硬编码 `45` 个槽，仅保留 `33` 个可调参数，并与 V1 逐笔完全等价。

clean tune 每腿各评估 `150,001` 组，组合 `122,500` 组；冻结 observation 的 prefit 为 `3.4333x / -15.02% / 73.33%`，current full `2.6071x / -18.93% / 71.30%`，均比 V1 收益更高、回撤更小。最近三个月 reused holdout 仍为 `0.4323x / -18.93% / 50.00%`，因此该结果不登记新版本，仍为 `NO-GO / not live-ready`。

## 入口

- `eth-1h-ar-core-ledger.md`：家族主账。
- `decision-log.md`：研究决策。
- `canonical-specs/eth-1h-ar-v1-baseline-spec.md`：V1 冻结配置、执行契约与指标。
- `scripts/eth_1h_ar_v1.py`：V1 独立复现入口。
- `scripts/research_eth_1h_ar_v1_full_ablation.py`：V1 `78/78` 字段槽全参数消融。
- `scripts/eth_1h_ar_v1_clean.py`：33 参数 clean-equivalent interface。
- `scripts/research_eth_1h_ar_v1_clean_tune.py`：prefit-only clean 参数高密度微调。
- `scripts/audit_eth_1h_ar_v1_clean_tune.py`：成本、延迟、66 个邻域、月度、bootstrap 和 live 边界审计。
- `scripts/fetch_eth_binance_1h.py`：两年 K 线、资金费、合约快照抓取与质量审计。
- `scripts/research_eth_1h_adaptive_regime_search.py`：locked OOS 多指标宽搜索。
- `diagnostics/eth-binance-1h-data-quality-2026-07-03.md`：本轮两年数据质量审计。
- `ablations/eth-1h-ar-v1-full-parameter-ablation-2026-07-03.md`：V1 全参数消融与删参分类。
- `research-notes/eth-1h-ar-v1-clean-parameter-tune-2026-07-03.md`：clean 参数微调。
- `research-notes/eth-1h-ar-v1-clean-tune-audit-2026-07-03.md`：微调 observation 最终审计。
- `artifacts/`：可复现证据；默认由 `.gitignore` 忽略。
