# Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble-V1 单仓先到先得规格 - 2026-07-07

## 版本身份

- Full version：`Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble-V1`
- Short id：`BIN-1H-AR-MAE-V1`
- Family：`Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble`
- Market：Binance USD-M Futures perpetual，`TRXUSDT / SOLUSDT / HYPEUSDT / ETHUSDT / BTCUSDT / BNBUSDT`
- Timeframe：`1h`
- Status：`dry-run / not live-ready`（实际启用与 live/dry-run 模式以 quant-runner 为准）

`V1` 是按用户指令登记的全账户单仓、先到先得组合版本。登记只冻结研究身份和复现口径，不代表 candidate、paper-live、dry-run、handoff 或 live。

## 成分版本

| Sleeve | 成分版本 | 成分机制 |
| --- | --- | --- |
| TRX | `TRX-1H-Adaptive-Regime-V3` | `macd_flip + stoch_reversal` |
| SOL | `SOL-1H-Adaptive-Regime-V2` | `donchian_break + vwap_revert` |
| HYPE | `HYPE-1H-Adaptive-Regime-V4` | `di_cross + stoch_reversal` |
| ETH | `ETH-1H-Adaptive-Regime-V3` | `bb_break + rsi_reversal` |
| BTC | `BTC-1H-Adaptive-Regime-V4` | `keltner_break + cci_reversal` |
| BNB | `BNB-1H-Adaptive-Regime-V3` | `ema_pullback + wick_reject` |

所有成分 sleeve 均复用各自家族冻结交易路径。组合回测脚本在合并前硬校验每个 sleeve 的 current full 指标，annual/DD/win/trades 与成分主账一致后才继续。

## 账户级组合规则

- 六个成分策略同时跑，各自按照家族冻结状态机生成候选交易。
- 全账户同一时间只允许一笔持仓。
- 按候选交易的 `entry_ts` 先到先得；已持仓期间，其他所有资产和所有腿的候选交易直接跳过。
- 任何新信号都不会抢仓、不会提前平掉当前持仓。
- 新入场必须严格晚于上一笔中选交易的 `exit_ts`；若 `entry_ts <= blocked_until`，该候选交易跳过。
- 同一小时多个候选入场时，按家族冻结 current-full 年化降序裁决：`HYPE > TRX > BTC > ETH > BNB > SOL`。本次回测出现 `22` 次同小时平手。
- 中选交易占用全账户权益，并按 sleeve 冻结杠杆执行；最高单笔冻结暴露为 `5.0x`。
- 阻塞只移除候选交易，不改变中选交易的入场、出场、成交价、费用、滑点或 funding。

重要近似：阻塞后的每个 sleeve 没有重新逐 K 重演 cooldown 和内部状态机。也就是说，被跨资产阻塞的交易在本回测中只是从已经冻结的 sleeve 交易路径里删除；真实联合状态机可能因为未成交而释放/改变后续 cooldown。promotion 前必须重写为逐 K 联合状态机。

## 数据、成本与执行口径

- 组合窗口：`2024-08-17T06:00:00Z -> 2026-07-02T03:00:00Z`。
- HYPE sleeve 计分起点：`2025-07-14T10:00:00Z`；此前 HYPE 不提供候选交易。
- 数据源：各成分家族冻结数据湖，数据质量由各家族 loader 校验。
- 费用：`0.001` fee/fill。
- 滑点：`4 bps` adverse slippage/fill。
- Funding：逐笔计入 Binance 历史 funding。
- 执行：继承各 sleeve 家族契约：闭合 `1h` K 产生信号，下一根 open 成交，保护 stop 即时有效，stop-first，gap 穿 stop 按 open 成交。
- 分片用途：全部窗口均为冻结后审计，不参与选参。

## 冻结回测结果

| Window | Annual | Return | Max DD | Trades | Win | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| full | `287.01x` | `+3,999,748%` | `-21.43%` | `371` | `90.30%` | `6.862` |
| all six active | `168.91x` | `+14,063%` | `-21.43%` | `207` | `88.41%` | `5.275` |
| reused holdout | `7.67x` | `+65.31%` | `-19.79%` | `42` | `78.57%` | `2.310` |
| `last_7d` | `1.27x` | `+0.46%` | `-15.92%` | `3` | `66.67%` | `1.423` |
| `last_1m` | `265.91x` | `+58.18%` | `-15.92%` | `19` | `89.47%` | `5.021` |
| `last_3m` | `7.65x` | `+66.01%` | `-19.79%` | `42` | `78.57%` | `2.310` |
| `last_6m` | `147.89x` | `+1089.35%` | `-21.43%` | `101` | `85.15%` | `4.618` |
| `last_1y` | `134.60x` | `+13315.39%` | `-21.43%` | `212` | `88.21%` | `4.885` |

槽位统计：候选交易 `522` 笔，中选 `371` 笔，因账户级持仓阻塞跳过 `151` 笔；平均单笔暴露 `2.60x`，最大暴露 `5.0x`，持仓时间中位数 `7h`，账户有仓小时占比 `35.6%`。

## 决策

`V1` 当前为 `dry-run / not live-ready`。以下是继续阻塞 live 的 historical pre-dry-run findings：

- full、`last_6m`、`last_1y` 最大回撤均为 `-21.43%`，穿破仓库 `<20%` 硬门槛。
- reused holdout 虽然收益为正，但最大回撤 `-19.79%` 几乎贴线，且该区间对成分家族和组合研究均不是 fresh OOS。
- 全期高年化来自样本内强势成分在全账户高杠杆下的复利放大，不能作为 promotion 依据。
- 阻塞后未做逐 K 联合状态机重演，存在 cooldown 反事实近似。
- 成分版本均有未关闭的研究门禁；组合层未完成 K+2、8 bps、double-cost 压力和 live 审计。

## 证据

- 主账：`../binance-1h-ar-mae-core-ledger.md`
- 回测报告：`../notes/binance-1h-ar-mae-single-position-backtest-2026-07-07.md`
- 汇总 JSON：`../artifacts/binance_1h_ar_mae_single_position_2026-07-07.json`
- 权益曲线：`../artifacts/binance_1h_ar_mae_single_position_equity_2026-07-07.csv`
- 中选交易：`../artifacts/binance_1h_ar_mae_single_position_trades_2026-07-07.csv`
- 复现脚本：`../scripts/research_binance_1h_ar_mae_single_position_backtest.py`

复现：

```bash
uv run python research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/scripts/research_binance_1h_ar_mae_single_position_backtest.py
```
