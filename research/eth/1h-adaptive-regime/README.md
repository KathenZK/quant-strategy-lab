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

`ETH-1H-Adaptive-Regime-V3 registered diagnostic clean tuned observation / NO-GO / not promoted / not live-ready`。

首轮 `600,768` 组广搜的 prefit 冻结冠军已按用户要求登记为 V1。V1 的 locked OOS 为 `0.5196x / -20.87% / 14.29% / 7 trades`，因此登记不改变 NO-GO 状态。预提交 Pareto 精调另生成 `300,000` 个邻域配置，仍为 `0` 个 hard-gate hit，不替换 V1 身份。

V1 全参数消融覆盖两腿 `78/78` 个字段槽：`29` 个 active tunable、`30` 个 baseline-fixed remove、`3` 个 neutral-fixed remove、`4` 个 path-fixed remove、`12` 个 contract fixed。clean interface 删除或硬编码 `49` 个槽，仅保留 `29` 个可调参数，并与 V1 逐笔完全等价。

clean tune 每腿各评估 `150,001` 组，组合 `122,500` 组；冻结 observation 的 prefit 为 `3.4333x / -15.02% / 73.33%`，current full `2.6071x / -18.93% / 71.30%`，均比 V1 收益更高、回撤更小。该 observation 已按用户要求登记为 `ETH-1H-Adaptive-Regime-V2`；最近三个月 reused holdout 仍为 `0.4323x / -18.93% / 50.00%`，因此 V2 仍为 `NO-GO / not live-ready`。

V2 全参数消融覆盖 `29/29` 个 clean 参数槽；单字段 high-win gate 命中 `0`。随后基于 V2 消融域重新做高胜率组合微调，找到 observation `ETH-1H-AR-V2-ABLATION-GUIDED-TUNE-2026-07-06` 并按用户要求登记为 `ETH-1H-Adaptive-Regime-V2.1`：prefit `3.7853x / -14.98% / 91.67% / 36`，current full `3.0277x / -19.55% / 87.50% / 40`，满足“收益高于 V2、胜率 80% 以上、回撤 20% 以下”的 current-full 形状；但 reused holdout 仍为 `0.7048x / -19.55% / 50.00% / 4`，K+2 与 double-cost 压力会穿 `20%` 回撤，因此不 promotion。

V2.1 全参数消融覆盖 `29/29` 个 clean 参数槽，`bb_break.ema_htf` 与 `bb_break.max_aligned_funding_bps` 判定为 merged-path inert 并硬编码，clean surface 收敛到 `27` 个可调参数且与 V2.1 逐笔等价。在干净参数面上微调得到 observation `ETH-1H-AR-V2-1-CLEAN-TUNE-2026-07-07` 并按用户要求登记为 `ETH-1H-Adaptive-Regime-V3`：prefit `4.0591x / -12.15% / 100.00% / 42`，current full `3.3084x / -15.70% / 95.65% / 46`，相对 V2.1 收益更高、胜率更高、回撤更小；但 reused holdout 仍为 `0.8706x / -15.70% / 50.00% / 4`（负收益），K+2 下 holdout 胜率 `25%`，因此不 promotion。

## 入口

- `eth-1h-ar-core-ledger.md`：家族主账。
- `decision-log.md`：研究决策。
- `canonical-specs/eth-1h-ar-v1-baseline-spec.md`：V1 冻结配置、执行契约与指标。
- `canonical-specs/eth-1h-ar-v2-clean-tuned-spec-2026-07-06.md`：V2 clean tuned observation 冻结参数、指标与边界。
- `canonical-specs/eth-1h-ar-v2-1-high-win-tuned-spec-2026-07-06.md`：V2.1 high-win tuned observation 冻结参数、近期失败解释与边界。
- `canonical-specs/eth-1h-ar-v3-clean-tuned-spec-2026-07-07.md`：V3 clean tuned observation 冻结参数、指标与边界。
- `scripts/eth_1h_ar_v1.py`：V1 独立复现入口。
- `scripts/eth_1h_ar_v2.py`：V2 clean tuned observation 独立复现入口。
- `scripts/research_eth_1h_ar_v1_full_ablation.py`：V1 `78/78` 字段槽全参数消融。
- `scripts/eth_1h_ar_v1_clean.py`：29 参数 clean-equivalent interface。
- `scripts/research_eth_1h_ar_v1_clean_tune.py`：prefit-only clean 参数高密度微调。
- `scripts/audit_eth_1h_ar_v1_clean_tune.py`：成本、延迟、66 个邻域、月度、bootstrap 和 live 边界审计。
- `scripts/research_eth_1h_ar_v2_full_ablation.py`：V2 `29/29` clean 参数槽全参数消融。
- `scripts/research_eth_1h_ar_v2_ablation_guided_tune.py`：基于 V2 消融域的高胜率组合微调。
- `scripts/eth_1h_ar_v2_1.py`：V2.1 high-win tuned observation 独立复现入口。
- `scripts/research_eth_1h_ar_v2_1_full_ablation.py`：V2.1 `29/29` clean 参数槽全参数消融与 inert 删参判定。
- `scripts/eth_1h_ar_v2_1_clean.py`：27 参数 V2.1 clean-equivalent interface，fail closed 校验逐笔等价。
- `scripts/research_eth_1h_ar_v2_1_clean_tune.py`：V2.1 干净参数面严格改善微调。
- `scripts/fetch_eth_binance_1h.py`：两年 K 线、资金费、合约快照抓取与质量审计。
- `scripts/research_eth_1h_adaptive_regime_search.py`：locked OOS 多指标宽搜索。
- `diagnostics/eth-binance-1h-data-quality-2026-07-03.md`：本轮两年数据质量审计。
- `ablations/eth-1h-ar-v1-full-parameter-ablation-2026-07-03.md`：V1 全参数消融与删参分类。
- `ablations/eth-1h-ar-v2-full-parameter-ablation-2026-07-06.md`：V2 clean 参数全消融。
- `ablations/eth-1h-ar-v2-1-full-parameter-ablation-2026-07-07.md`：V2.1 clean 参数全消融与 inert 删参分类。
- `research-notes/eth-1h-ar-v1-clean-parameter-tune-2026-07-03.md`：clean 参数微调。
- `research-notes/eth-1h-ar-v1-clean-tune-audit-2026-07-03.md`：微调 observation 最终审计。
- `research-notes/eth-1h-ar-v2-ablation-guided-tune-2026-07-06.md`：V2 消融引导高胜率微调 observation。
- `research-notes/eth-1h-ar-v2-1-clean-tune-2026-07-07.md`：V2.1 干净参数面严格改善微调 observation。
- `artifacts/`：可复现证据；默认由 `.gitignore` 忽略。
