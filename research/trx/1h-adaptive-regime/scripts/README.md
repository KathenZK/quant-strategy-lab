# Scripts

- `fetch_trx_binance_1h.py`：抓取并审计 Binance `TRXUSDT` perpetual 最近两年闭合 `1h` K、资金费与交易规则快照。
- `research_trx_1h_adaptive_regime_search.py`：在最近三个月 locked OOS 不可见的前提下执行多指标宽搜索。
- `research_trx_1h_adaptive_regime_refine.py`：只读取宽搜索 prefit 参数，在 train/validation 上做邻域微调；OOS 仍只在冻结后揭盲。
- `audit_trx_1h_persistent_regime_boundary.py`：覆盖持续 EMA/MACD/Donchian 趋势与 Bollinger/RSI/Stochastic/VWAP 均值回归状态的乐观上界；不能作为 promotion 证据。
- `audit_trx_1h_live_feasibility.py`：精确复现领先观察值并执行 K+2、`8 bps` 滑点、额外手续费和生产状态机审计。
- `research_trx_1h_ar_v1base_full_ablation.py`：精确复现 `V1base`，覆盖两个组件全部 `StrategyConfig` 字段槽，生成 `V2` clean 参数面与删参证据。
- `audit_trx_1h_ar_v2_strict_ablation_slices.py`：读取已登记 `V2` clean 参数面，执行 retained 参数消融、最近 `1d/7d/1m/3m/6m/1y` 分片和逐笔成交重放。

统一从仓库根目录使用 `uv run python ...` 运行。

复现顺序：fetch → broad search → refine → persistent boundary → live feasibility → V1base full ablation → V2 strict ablation/slices。所有搜索脚本的默认 seed、搜索规模和输出路径均已冻结在源码中。
