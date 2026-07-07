# BNB-1H-Adaptive-Regime

`BNB-1H-Adaptive-Regime`（短 id：`BNB-1H-AR`）是 Binance USD-M Futures `BNBUSDT` perpetual `1h` 多指标自适应策略研究家族，与 BTC、ETH、SOL、HYPE 或其他资产 family 没有版本继承关系。

## 研究目标

- 数据：运行时最近两年的全部闭合 `1h` K，直接刷新自 Binance FAPI，并保存 raw/normalized 数据湖分区、资金费历史和合约过滤器快照。
- OOS：最后三个月固定为 locked out-of-sample；参数生成、搜索、排序和组合冻结不得读取该区间。
- 硬门槛：年化权益倍率 `>=10.0x`（即年化收益 `>=900%`）、胜率 `>=50%`、最大回撤严格小于 `20%`。
- 成本：`0.001` fee/fill、`4 bps` adverse slippage/fill，并逐笔计入 Binance 历史资金费。
- 执行：闭合 K 产生信号，下一根 `1h` open 市价成交；入场后保护性 bracket 立即生效；同 K 双触发 stop-first；跳空穿越 stop 按 open 成交；trailing 只在完整 K 闭合后更新并从下一根 K 生效。

## 指标与搜索面

搜索覆盖 EMA/MACD、RSI、Stochastic、CCI、Williams %R、ADX/DI、ATR、Bollinger、Keltner、Donchian、rolling VWAP、成交量、动量、wick/body 结构、`4h/12h/1d` 闭合 regime、资金费过滤、固定/风险预算仓位、固定 bracket/trailing exit 及 long/short/both。

## 当前状态

`NO-GO / not promoted / not live-ready`。

完整搜索没有 prefit hard-gate 命中；唯一冻结 primary 在最近三个月 locked OOS 明显失效。2026-07-06 追加的 `<=3x` 高胜率趋势/反转搜索找到 `ema_pullback+wick_reject` 样本内观察形态，并登记为 `BNB-1H-Adaptive-Regime-V1` diagnostic observation；但 locked OOS `0.64x / -22.86% DD / 68.42% win`，仍未通过。`BNB-1H-Adaptive-Regime-V2` 已登记为 V1 clean-equivalent 可执行版本（交易路径逐笔一致），完成多窗口验证与 V2 全参数消融（`27` 活动字段、`0` 可再删）。V2 消融引导微调找到 tuned observation：prefit `3.37x / -18.24% / 89.42%`、reused OOS `1.22x / -15.53% / 81.25%`、full `2.94x / -18.24% / 88.33%`，但 reused OOS 属二次读取，不改变 `NO-GO / not promoted / not live-ready` 结论。本家族没有生产 runner。后续 BNB 研究已拆分到独立的 `../15m-adaptive-regime/`，不得把 15m 结果写回本家族版本线。

## 入口

- `bnb-1h-ar-core-ledger.md`：家族主账。
- `decision-log.md`：研究决策与状态变化。
- `scripts/fetch_bnb_binance_1h.py`：最近两年 K 线、资金费、合约快照抓取与质量审计。
- `scripts/research_bnb_1h_adaptive_regime_search.py`：locked OOS 多指标宽搜索。
- `scripts/research_bnb_1h_ar_v1_full_ablation.py`：V1 全参数消融与 clean spec 证据生成。
- `scripts/bnb_1h_ar_v2.py`：V2 clean 参数可执行定义、V1 路径等价验证与多窗口回测。
- `scripts/research_bnb_1h_ar_v2_full_ablation.py`：V2 全参数域扫描消融。
- `scripts/research_bnb_1h_ar_v2_micro_tune.py`：V2 消融引导微调（prefit-only 选参）。
- `canonical-specs/bnb-1h-ar-v1-parameter-spec-2026-07-06.md`：V1 原始冻结参数规格。
- `canonical-specs/bnb-1h-ar-v1-clean-parameter-spec-2026-07-06.md`：V1 删除 no-op 字段后的等价 clean 参数规格。
- `canonical-specs/bnb-1h-ar-v2-parameter-spec-2026-07-07.md`：V2 clean-equivalent 版本参数规格。
- `research-notes/bnb-1h-ar-v2-multiwindow-backtest-2026-07-07.md`：V2 路径等价验证与多时间窗口分片。
- `research-notes/bnb-1h-ar-v2-micro-tune-2026-07-07.md`：V2 微调 tuned observation（reused OOS，不 promotion）。
- `diagnostics/bnb-1h-adaptive-regime-search-2026-07-03.md`：完整搜索与 locked OOS NO-GO 证据。
- `diagnostics/bnb-1h-ar-cap3-highwin-search-2026-07-06-cap3-highwin.md`：`<=3x` 高胜率趋势/反转搜索，样本内接近目标但 locked OOS 失败。
- `ablations/bnb-1h-ar-v1-full-parameter-ablation-2026-07-06.md`：V1 全参数消融，识别 `32` 个交易路径不变的 no-op 字段。
- `ablations/bnb-1h-ar-v2-full-parameter-ablation-2026-07-07.md`：V2 全参数域扫描消融，`27` 个活动字段、无可再删参数。
- `artifacts/`：Parquet、JSON、CSV 等可复现证据；默认由 `.gitignore` 忽略。
