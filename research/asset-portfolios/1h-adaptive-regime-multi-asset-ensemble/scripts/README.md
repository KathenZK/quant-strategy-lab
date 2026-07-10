# Scripts

- `research_binance_1h_ar_multi_asset_ensemble_backtest.py`：首次组合回测。加载六个家族最新登记版本的冻结交易路径（TRX V3、SOL V2、HYPE V4、ETH V3、BTC V4、BNB V3），逐 sleeve 与主账 current full 指标硬校验后，构建等权 `1/6` 组合的小时权益曲线（再平衡 + 不再平衡两口径），输出全期、六 sleeve 齐备段、reused holdout 与 `1d/7d/1m/3m/6m/1y` 分片指标、日收益相关性和毛暴露统计到 `../artifacts/`。
- `research_binance_1h_ar_mae_single_position_backtest.py`：`Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble-V1` 单仓先到先得结构回测。复用首个脚本的 sleeve loader 与硬校验，全账户只保留一个持仓槽位（先到先得、持仓期间忽略其他信号、同小时平手按家族 current-full 年化降序），中选交易占用全额权益并按 sleeve 冻结杠杆执行；输出同一组窗口指标、槽位占用统计与逐笔中选交易到 `../artifacts/`。
- `research_binance_1h_ar_mae_v1_risk_overlay_diagnostics.py`：V1 风险覆盖层诊断。保持 V1 冻结 sleeve 交易路径与单仓先到先得选择规则，测试全局 `3x`/`2.5x` 暴露 cap、TRX `macd_flip` cap/剔除、`>3x` 候选过滤和额外滑点/双倍成本压力；输出对照矩阵与 JSON 到 `../artifacts/`。该脚本是账户层 overlay，不是逐 K 联合状态机重演。
- `research_binance_1h_ar_mae_v1_trx_tail_risk_optimization.py`：定位 TRX MACD 高暴露尾部根因，测试全局 signal-ATR 风险预算、账户 DD guard 与 TRX 初始止损风险预算；证明全局 `1% ATR` 虽可显著降 DD，但对所有 sleeve 过度降杠杆。
- `research_binance_1h_ar_mae_v1_trx_targeted_tail_overlay.py`：只缩放中选的 TRX `macd_flip`，以 signal ATR 计划止损风险和入场前账户 DD 决定暴露；非 TRX 交易不变。prefit-only 选参后输出完整窗口、额外滑点/双倍成本、单笔 MAE 与账户状态叠加 MAE 尾部。

复现：

```bash
uv run python research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/scripts/research_binance_1h_ar_multi_asset_ensemble_backtest.py
uv run python research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/scripts/research_binance_1h_ar_mae_single_position_backtest.py
uv run python research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/scripts/research_binance_1h_ar_mae_v1_risk_overlay_diagnostics.py
uv run python research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/scripts/research_binance_1h_ar_mae_v1_trx_tail_risk_optimization.py
uv run python research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/scripts/research_binance_1h_ar_mae_v1_trx_targeted_tail_overlay.py
```

依赖：六个成分家族的 `scripts/` 与数据湖数据已就绪（各家族 loader 自带数据质量校验）。
