# Scripts

- `fetch_trx_binance_1h.py`：抓取并审计 Binance `TRXUSDT` perpetual 最近两年闭合 `1h` K、资金费与交易规则快照。
- `research_trx_1h_adaptive_regime_search.py`：在最近三个月 locked OOS 不可见的前提下执行多指标宽搜索。
- `research_trx_1h_adaptive_regime_refine.py`：只读取宽搜索 prefit 参数，在 train/validation 上做邻域微调；OOS 仍只在冻结后揭盲。
- `audit_trx_1h_persistent_regime_boundary.py`：覆盖持续 EMA/MACD/Donchian 趋势与 Bollinger/RSI/Stochastic/VWAP 均值回归状态的乐观上界；不能作为 promotion 证据。
- `audit_trx_1h_live_feasibility.py`：精确复现领先观察值并执行 K+2、`8 bps` 滑点、额外手续费和生产状态机审计。
- `trx_1h_ar_v1.py`：正式登记的 `TRX-1H-Adaptive-Regime-V1` 基线实现与配置导出。
- `trx_1h_ar_v2.py`：正式登记的 `TRX-1H-Adaptive-Regime-V2` clean 参数实现；校验与 V1 逐交易路径完全一致。
- `trx_1h_ar_v3.py`：正式登记的 `TRX-1H-Adaptive-Regime-V3` 微调参数实现；校验 V3 指标与 V2 消融引导微调观察值一致并导出配置。
- `research_trx_1h_ar_v1_full_ablation.py`：覆盖 V1 两个组件全部 `StrategyConfig` 字段槽，生成 V2 clean 参数面的删参证据。
- `research_trx_1h_ar_v2_full_ablation.py`：覆盖 V2 对外暴露 clean 参数槽 `36/36`，输出 one-at-a-time 全参数消融、标准分片和逐笔成交重放。
- `research_trx_1h_ar_v2_ablation_guided_tune.py`：基于 V2 消融结果与 clean-surface pair pool 做 train/validation/prefit-only 微调，并输出冻结后 holdout、标准分片和执行审计。
- `audit_trx_1h_ar_v1_clean_strict_ablation_slices.py`：历史 V1 clean-equivalent 严格审计脚本；当前正式 V2 证据以 `research_trx_1h_ar_v2_full_ablation.py` 为准。
- `research_trx_1h_ar_recent_adaptation_search.py`：在已解锁近期行情上做近期适配复搜，输出标准分片、曝光缩放边界和逐笔成交重放；只能作为 diagnostic evidence。

统一从仓库根目录使用 `uv run python ...` 运行。

复现顺序：fetch → broad search → refine → persistent boundary → live feasibility → V1 config → V1 full ablation → V2 config → V2 full ablation → V2 ablation-guided tune → V3 config → recent adaptation search。所有搜索脚本的默认 seed、搜索规模和输出路径均已冻结在源码中。
