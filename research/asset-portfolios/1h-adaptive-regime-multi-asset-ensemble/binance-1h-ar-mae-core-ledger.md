# Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble 主账

## 家族身份

- Full family name：`Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble`
- Short id：`BIN-1H-AR-MAE`
- Market：Binance USD-M Futures perpetual，`TRXUSDT / SOLUSDT / HYPEUSDT / ETHUSDT / BTCUSDT / BNBUSDT`
- Timeframe：`1h`
- 机制：六个单资产 1h adaptive-regime 家族最新登记版本的多资产组合；各 sleeve 保持家族冻结交易路径，不做信号层融合。当前正式登记版 `V1` 采用全账户单仓槽位、先到先得结构。

本家族是组合研究线，不改变、不代表任何成分家族的版本身份。成分版本引用必须带家族全名。

## 当前状态

`Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble-V1 registered single-position version / NO-GO / not promoted / not live-ready`。

2026-07-07 应用户要求，将 `TRX-1H-Adaptive-Regime-V3`、`SOL-1H-Adaptive-Regime-V2`、`HYPE-1H-Adaptive-Regime-V4`、`ETH-1H-Adaptive-Regime-V3`、`BTC-1H-Adaptive-Regime-V4`、`BNB-1H-Adaptive-Regime-V3` 组合为等权多资产组合并完成首次回测。全期（小时再平衡口径）年化 `4.07x`、最大回撤 `-4.43%`、胜率 `89.66%`（`522` 笔）；但成分策略全部是 diagnostic NO-GO 版本，最近三个月 reused holdout 组合年化降至 `1.62x`，且无任何生产执行证据，因此本组合不是 candidate、paper-live、dry-run、handoff 或 live 版本。

同日按用户要求补测了“全账户单仓、先到先得”结构，并在用户后续指令下正式登记为 `Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble-V1`（短 id：`BIN-1H-AR-MAE-V1`）：全期年化 `287.01x` 但最大回撤 `-21.43%` 穿破 `<20%` 硬门槛，且阻塞反事实未做逐 K 联合状态机重演，因此 `V1` 只是 diagnostic registered version，不是 candidate、paper-live、dry-run、handoff 或 live。

2026-07-09 对 V1 做风险覆盖层与 TRX MACD 消融诊断：全局 `3x` cap 虽可把最差回撤压到 `-19.99%`，但额外 `4 bps/fill` 滑点即失败到 `-20.18%`；全局 `2.5x` cap 在基准成本下为 `122.81x / -18.68% DD`，额外 `4 bps/fill` 下为 `88.47x / -19.19% DD`，是下一轮冻结候选中相对更稳的方向。但该结果仍是账户层 overlay，不是逐 K 联合状态机重演，不登记为新版本。

同日 `quant-runner` 接入 `kind = six_asset_ensemble` dry-run（六资产联合状态机近似，live 禁止）。这只是 runtime 观察接线，不改变 `NO-GO / not promoted / not live-ready`，也不等于研究回测路径已对拍。见 `runner-tracking/binance-1h-ar-mae-v1-runner-status.md`。

## 成分版本冻结表

| Sleeve | 成分版本 | 成分主账 | V1 账户槽位 |
| --- | --- | --- | --- |
| TRX | `TRX-1H-Adaptive-Regime-V3` | `../../trx/1h-adaptive-regime/trx-1h-ar-core-ledger.md` | 候选交易参与全账户单仓竞争；中选时占用全额账户权益 |
| SOL | `SOL-1H-Adaptive-Regime-V2` | `../../sol/1h-adaptive-regime/sol-1h-ar-core-ledger.md` | 候选交易参与全账户单仓竞争；中选时占用全额账户权益 |
| HYPE | `HYPE-1H-Adaptive-Regime-V4` | `../../hype/1h-adaptive-regime/hype-1h-ar-core-ledger.md` | 候选交易参与全账户单仓竞争；中选时占用全额账户权益 |
| ETH | `ETH-1H-Adaptive-Regime-V3` | `../../eth/1h-adaptive-regime/eth-1h-ar-core-ledger.md` | 候选交易参与全账户单仓竞争；中选时占用全额账户权益 |
| BTC | `BTC-1H-Adaptive-Regime-V4` | `../../btc/1h-adaptive-regime/btc-1h-ar-core-ledger.md` | 候选交易参与全账户单仓竞争；中选时占用全额账户权益 |
| BNB | `BNB-1H-Adaptive-Regime-V3` | `../../bnb/1h-adaptive-regime/bnb-1h-ar-core-ledger.md` | 候选交易参与全账户单仓竞争；中选时占用全额账户权益 |

组合回测前逐 sleeve 与成分主账 current full 指标核对，annual/DD/win/trades 全部一致（脚本内硬校验，漂移即抛错）。

## 版本规则

- `V1`：全账户单仓、先到先得的六资产组合版本；六个成分 sleeve 固定为 TRX V3、SOL V2、HYPE V4、ETH V3、BTC V4、BNB V3；候选交易来自各家族冻结路径；同一时间只允许一笔账户级持仓；持仓期间忽略其他所有信号；同小时平手按成分家族冻结 current-full 年化降序裁决；中选交易占用全额权益并按 sleeve 冻结杠杆执行。`V1` 是 diagnostic registered version，`NO-GO / not live-ready`。
- `BIN-1H-AR-MAE-FIRST-2026-07-07` 是 V1 登记前的等权 `1/6` 组合 diagnostic observation，不是正式版本，不改变 `V1` 身份。
- 后续若用户要求登记 `V2` 或更高版本，必须冻结：成分版本清单、账户级持仓/资金规则、冲突/平手优先级、组合窗口与证据链接，并更新本主账。
- 任何成分家族升级版本（例如 TRX V4）不自动进入本组合；组合成分变更必须作为新 observation 或新版本重新回测并记录。
- 进入 promotion 状态前必须完成组合层 K+2/滑点/成本压力、再平衡/单仓资金结构审计和六资产生产状态机的 live-executable 审计。

## 版本与观察记录

| Version / Observation | Status | 结构 | 关键指标 | Evidence | Live readiness |
| --- | --- | --- | --- | --- | --- |
| `BIN-1H-AR-MAE-FIRST-2026-07-07` | first combination diagnostic / not promoted | 六 sleeve 等权 `1/6`，小时再平衡主口径 + 不再平衡对照 | full `4.069x / +1284.22% / -4.43% DD / 89.66% win / 522 trades / PF 6.627`；六 sleeve 齐备段 `3.821x / -4.43%`；reused holdout `1.625x / +12.72% / 75.38% win`；`last_7d -1.71%`；日收益相关性最大 `0.185`；平均毛暴露 `0.247x`、最大 `1.83x` | `notes/binance-1h-ar-mae-first-combination-backtest-2026-07-07.md`；`artifacts/binance_1h_ar_mae_first_backtest_2026-07-07.json`；`scripts/research_binance_1h_ar_multi_asset_ensemble_backtest.py` | `NO-GO / not live-ready`：成分全 NO-GO、reused holdout 走弱、组合层压力与 runner 审计缺失 |
| `Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble-V1` (`BIN-1H-AR-MAE-V1`) | registered single-position version / not promoted | 全账户单仓槽位、先到先得；持仓期间忽略所有其他信号；同小时平手按家族 current-full 年化降序；中选交易占用全额权益并按 sleeve 冻结杠杆（最高 `5x`）执行 | full `287.01x / -21.43% DD / 90.30% win / 371 trades / PF 6.862`（候选 `522` 笔、阻塞跳过 `151` 笔）；reused holdout `7.67x / +65.31% / -19.79% DD / 78.57% win / 42 trades`；`last_7d +0.46% / -15.92% DD`；`last_1m +58.18% / -15.92% DD`；`last_3m +66.01% / -19.79% DD`；`last_6m +1089.35% / -21.43% DD`；`last_1y +13315.39% / -21.43% DD` | `specs/binance-1h-ar-mae-v1-full-reproduction-spec-2026-07-07.md`；`specs/binance-1h-ar-mae-v1-single-position-spec-2026-07-07.md`；`notes/binance-1h-ar-mae-single-position-backtest-2026-07-07.md`；`artifacts/binance_1h_ar_mae_single_position_2026-07-07.json`；`scripts/research_binance_1h_ar_mae_single_position_backtest.py` | `NO-GO / not live-ready`：full 与 `last_6m/1y` DD `-21.43%` 穿破 `<20%` 硬门槛；阻塞后未做逐 K 联合状态机重演（cooldown 反事实近似）；成分全 NO-GO；无压力与 runner 审计 |
| `BIN-1H-AR-MAE-V1-RISK-OVERLAY-2026-07-09` | diagnostic observation / not registered | 复用 V1 中选规则，测试全局 `3x`/`2.5x` cap、TRX `macd_flip` cap/剔除、`>3x` 候选过滤和成本压力；均为账户层 overlay | `cap3x` full `192.49x / -19.99% DD`，但 extra `4 bps/fill` 后 `134.46x / -20.18% DD` 失败；`cap2.5x` full `122.81x / -18.68% DD`，extra `4 bps/fill` 后 `88.47x / -19.19% DD`；double fee+slippage 下 `3x/2.5x` 均约 `-25.5% DD` 失败 | `notes/binance-1h-ar-mae-v1-risk-overlay-diagnostics-2026-07-09.md`；`artifacts/binance_1h_ar_mae_v1_risk_overlay_diagnostics_2026-07-09.json`；`artifacts/binance_1h_ar_mae_v1_risk_overlay_matrix_2026-07-09.csv`；`scripts/research_binance_1h_ar_mae_v1_risk_overlay_diagnostics.py` | `NO-GO / not live-ready`：overlay 未重演逐 K 联合状态机；成本压力是交易后近似；成分全 NO-GO；若冻结下一版需优先审计 `cap2.5x` |

## Promotion 边界

- 成分家族的 promotion 门槛与失败边界全部继承；组合不清洗 reused holdout 失败、K+2/8bps 压力失败与执行审计缺失。
- 最近三个月对全部六个家族都是已揭盲区间，组合层同样不得当作 fresh OOS 使用。
- 小时再平衡的资金划转摩擦未计入；促升前必须给出实盘可执行的再平衡（或不再平衡）资金结构。
- 在完成组合层 live-executable 审计并取得新增 runner 观察证据前，禁止标记为 candidate、paper-live、dry-run、handoff 或 live。
