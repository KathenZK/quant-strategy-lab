# Scripts

本目录将保存当前 Goal 的数据审计、continuation-meter 验证、真实 lot/quantity campaign、受治理参数搜索、稳健性和导出脚本。研究脚本不得直接下单。

- `sync_binance_assets_15m.py`：刷新 BTC/ETH/HYPE 官方 Binance closed 15m OHLCV/funding，写入标准数据湖并生成 fail-closed 审计。
- `audit_binance_mtf_ptc_data.py`：复核标准数据湖、raw/normalized parity、三资产统一 cutoff 和冻结切分，任一 blocker 即停止。
- `research_continuation_meter_v0.py`：只在 development/validation 验证 4h/12h/24h onset 对未来 24h/72h/168h barrier-first continuation 的可排序性，不读取 locked evaluation。
- `audit_continuation_meter_v0.py`：对冻结的 24h onset 做 long/short、年份、Brier skill、标准化系数和 leave-one-feature-out 归因；仍不读取 locked evaluation。
- `diagnose_pullback_entry_v0.py`：在 validation 对强 continuation candidates 公平比较即时追价与冻结的 1h pullback + 15m restart 成交质量，不运行 locked evaluation。
- `diagnose_pullback_entry_v1_early_onset.py`：V0 失败后保持回调规则不变，只测试预声明的 4h/12h earlier onset 是否解决确认过晚问题。
- `search_probe_entry_v0.py`：在 development inner split 对60个预声明样本组合运行真实成本 probe-only 搜索，每资产只把唯一胜出参数送入原 validation；不运行 locked evaluation。
- `research_campaign_engine_v0.py`：逐 15m、真实 quantity/fee/slippage/funding、多 lot 独立 stop、pending attempt、MFE eligibility、risk maintenance 和逐 bar liquidation MDD 内核。
- `search_regime_campaign_v1.py`：在 BTC/ETH 2021/2022/2023 expanding development folds 比较 7d/28d 纯价格方向先验、0/1/3 layers 与 half-reduce；HYPE 只作单折探索。
- `search_limit_retest_v2.py`：比较 restart market 与 25%/50%、1h/4h 因果限价回踩，盘中 limit fill 使用保守 same-bar 语义。
- `audit_risk_scaling_v1.py`：只对 BTC 历史前沿运行 1x/2x/3x risk scaling 与 base/stress 边界，不读取 locked evaluation。
