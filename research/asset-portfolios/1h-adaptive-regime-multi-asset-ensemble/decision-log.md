# Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble 决策记录

## 2026-07-07 创建家族并完成首次组合回测

- 背景：用户要求把 TRX/SOL/HYPE/ETH/BTC/BNB 六个 `1h` adaptive-regime 家族的最新登记版本组合成一个新策略并回测。
- 成分冻结：`TRX-1H-Adaptive-Regime-V3`、`SOL-1H-Adaptive-Regime-V2`、`HYPE-1H-Adaptive-Regime-V4`、`ETH-1H-Adaptive-Regime-V3`、`BTC-1H-Adaptive-Regime-V4`、`BNB-1H-Adaptive-Regime-V3`；每 sleeve 复用家族冻结交易路径，运行前与各家族主账 current full 指标硬校验一致（annual/DD/win/trades 零漂移）。
- 组合结构：六个子账户 sleeve 等权 `1/6`；主口径小时再平衡，对照口径不再平衡；权益曲线小时级构建，持仓中按 bar close mark-to-market，出场按冻结 `equity_ret` 对齐。
- 结果：全期（2024-08-17 至 2026-07-02 UTC）再平衡年化 `4.069x`、收益 `+1284.22%`、最大回撤 `-4.43%`、胜率 `89.66%`（`522` 笔、PF `6.627`）；六 sleeve 齐备段（2025-07-14 起）`3.821x / -4.43%`；reused holdout（2026-04-03 起）`1.625x / 75.38% win`；`last_7d` 为 `-1.71%`。六 sleeve 日收益相关性最大 `0.185`，平均毛暴露 `0.247x`。
- 决策：登记为 first combination diagnostic observation（未编号，不登记 Vx），状态 `NO-GO / not promoted / not live-ready`。理由：成分全部是 diagnostic NO-GO 版本；最近三个月是已揭盲 reused holdout 且组合明显走弱；组合层未做 K+2/滑点/成本压力与再平衡摩擦审计；六资产生产状态机、对账、缺 K fail-closed、kill switch 全部缺失。
- 证据：`notes/binance-1h-ar-mae-first-combination-backtest-2026-07-07.md`、`artifacts/binance_1h_ar_mae_first_backtest_2026-07-07.json`、`artifacts/binance_1h_ar_mae_equity_2026-07-07.csv`、`artifacts/binance_1h_ar_mae_trades_2026-07-07.csv`。

## 2026-07-07 单仓先到先得结构回测

- 背景：用户要求测试另一种组合结构——六个策略同时跑，但全账户同一时间只允许一笔持仓，谁先来信号就开谁的仓。
- 规则：单仓槽位先到先得；持仓期间忽略所有其他信号（不抢仓、不提前平仓）；新入场必须严格晚于上一笔出场 K；同小时平手按家族冻结 current-full 年化降序裁决（出现 `22` 次）；中选交易占用全额权益并按 sleeve 冻结杠杆执行（最高 `5x`）。
- 结果：候选 `522` 笔、中选 `371` 笔、阻塞跳过 `151` 笔；全期年化 `287.01x`、最大回撤 `-21.43%`、胜率 `90.30%`、PF `6.862`；reused holdout `7.67x / +65.31% / -19.79% DD / 78.57% win`；`last_7d` 仅 `+0.46%` 且期间回撤 `-15.92%`。
- 决策：登记为 `BIN-1H-AR-MAE-SINGLE-POS-2026-07-07` combination diagnostic observation，`NO-GO / not promoted / not live-ready`。理由：full 与 `last_6m/1y` 回撤 `-21.43%` 穿破 `<20%` 硬门槛；全期收益是样本内强势成分在全额高杠杆下的复利放大，无实盘意义；阻塞后未做逐 K 联合状态机重演（sleeve 内 cooldown 反事实是近似）；成分全部 NO-GO；组合层压力与生产执行审计缺失。
- 证据：`notes/binance-1h-ar-mae-single-position-backtest-2026-07-07.md`、`artifacts/binance_1h_ar_mae_single_position_2026-07-07.json`、`artifacts/binance_1h_ar_mae_single_position_equity_2026-07-07.csv`、`artifacts/binance_1h_ar_mae_single_position_trades_2026-07-07.csv`。

## 2026-07-07 登记为 V1

- 背景：用户明确要求“把这个组合策略记为 V1”。这里的“这个组合策略”按上下文指 2026-07-07 刚完成的全账户单仓、先到先得结构，而不是此前等权 `1/6` observation。
- 登记版本：`Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble-V1`（短 id：`BIN-1H-AR-MAE-V1`）。
- 冻结身份：成分固定为 TRX V3、SOL V2、HYPE V4、ETH V3、BTC V4、BNB V3；全账户单仓槽位；先到先得；持仓期间忽略其他全部信号；同小时平手按家族 current-full 年化降序；中选交易占用全额权益并按 sleeve 冻结杠杆执行。
- 指标：full `287.01x / -21.43% DD / 90.30% win / 371 trades / PF 6.862`；reused holdout `7.67x / +65.31% / -19.79% DD / 78.57% win / 42 trades`；`last_7d +0.46% / -15.92% DD`；`last_1m +58.18% / -15.92% DD`；`last_3m +66.01% / -19.79% DD`；`last_6m +1089.35% / -21.43% DD`；`last_1y +13315.39% / -21.43% DD`。
- 决策：登记为 `V1` 但状态保持 `NO-GO / not promoted / not live-ready`。理由：full 与 `last_6m/1y` 回撤 `-21.43%` 穿破 `<20%` 硬门槛；阻塞后未做逐 K 联合状态机重演；成分全部是 diagnostic NO-GO；组合层压力与生产执行审计缺失。
- 证据：`specs/binance-1h-ar-mae-v1-full-reproduction-spec-2026-07-07.md`、`specs/binance-1h-ar-mae-v1-single-position-spec-2026-07-07.md`、`binance-1h-ar-mae-core-ledger.md`、`notes/binance-1h-ar-mae-single-position-backtest-2026-07-07.md`。

## 2026-07-09 quant-runner dry-run 接入

- 背景：用户要求在 `quant-runner` 实现 `BIN-1H-AR-MAE-V1`，达到可跑 dry-run。
- 实现：`kind = six_asset_ensemble`；六资产联合状态机 dry-run（非 lab 冻结交易路径后筛选的 diagnostic 近似）；live 禁止；`configs/dryrun.toml` 增加 `six-asset-ensemble-dry-run`。
- 验证：本地 `smoke-test` 通过；本地 `run-once` 返回 `flat_no_signal`（当前小时无 due 候选）。
- 决策：dry-run 可观察，但状态仍为 `NO-GO / not promoted / not live-ready`。未改变 promotion 结论；`replay-dry-run` 与研究路径对拍未完成。
- 证据：`runner-tracking/binance-1h-ar-mae-v1-runner-status.md`。

## 2026-07-09 V1 风险覆盖层与 TRX MACD 消融诊断

- 背景：用户要求按优化建议做一轮 V1 风险约束、TRX MACD 消融与成本压力诊断。
- 方法：保持 V1 六个冻结 sleeve 交易路径与全账户单仓先到先得选择规则；只在账户层叠加风险覆盖层，包括全局 `3x`/`2.5x` cap、TRX `macd_flip` cap 或剔除、`>3x` 候选过滤，以及 cap 后的额外 `4 bps/fill` 滑点和 double fee+slippage 压力。成本压力为交易后账户层近似，不是逐 K 成交重演。
- 结果：V1 baseline 复现为 full `287.01x / -21.43% DD`；全局 `3x` cap 为 `192.49x / -19.99% DD`，但加 `4 bps/fill` 额外滑点后失败为 `134.46x / -20.18% DD`；全局 `2.5x` cap 为 `122.81x / -18.68% DD`，加 `4 bps/fill` 后仍为 `88.47x / -19.19% DD`；double fee+slippage 下 `3x` 与 `2.5x` 都失败，最差回撤约 `-25.5%`。
- 决策：登记为未编号 diagnostic observation `BIN-1H-AR-MAE-V1-RISK-OVERLAY-2026-07-09`，不登记 `V1.1/V1.2`，状态 `NO-GO / not promoted / not live-ready`。若后续要冻结新版本，优先研究 `V1 + 全账户单笔暴露 cap 2.5x`，并先完成逐 K 联合状态机重演与真实 K+2/成本压力。
- 证据：`notes/binance-1h-ar-mae-v1-risk-overlay-diagnostics-2026-07-09.md`、`artifacts/binance_1h_ar_mae_v1_risk_overlay_diagnostics_2026-07-09.json`、`artifacts/binance_1h_ar_mae_v1_risk_overlay_matrix_2026-07-09.csv`、`scripts/research_binance_1h_ar_mae_v1_risk_overlay_diagnostics.py`。
