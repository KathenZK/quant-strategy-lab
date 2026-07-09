# Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble-V1 风险覆盖层诊断 - 2026-07-09

## 结论

本报告按用户要求，对 `Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble-V1` 做一轮风险约束与 TRX MACD 消融诊断。所有测试都复用 V1 的六个冻结 sleeve 交易路径与单仓先到先得选择规则；本轮只在账户层叠加风险覆盖层，不登记新版本，不改变 V1 的 `NO-GO / not promoted / not live-ready` 状态。

核心结论：

- `cap3x` 可以把 V1 最差窗口回撤从 `-21.43%` 压到 `-19.99%`，但距离 `<20%` 门槛太近；一旦加 `4 bps/fill` 额外滑点，最差回撤扩大到 `-20.18%`，仍失败。
- `cap2.5x` 的回撤缓冲更合理：基准成本下最差窗口 `-18.68%`，额外 `4 bps/fill` 滑点下仍为 `-19.19%`；但 `last_7d` 从 `+0.46%` 变为 `-0.14%`，说明近端交易质量本身偏弱。
- 仅压低或剔除 TRX `macd_flip` 可以消除 `5x` 暴露，但最差回撤仍贴在 `-19.99%` 附近，不能单独解决稳健性问题。
- 双倍 fee+slippage 压力下，`cap3x` 和 `cap2.5x` 都失败，最差回撤约 `-25.5%`；组合对执行成本仍敏感。

因此，若后续要冻结新版本，优先级不是 `cap3x`，而是更保守的 **`V1 + 全账户单笔暴露上限 2.5x`**，并且必须先完成逐 K 联合状态机重演与真实成本压力。

## 方法

复现脚本：

```bash
uv run python research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/scripts/research_binance_1h_ar_mae_v1_risk_overlay_diagnostics.py
```

共测试 `11` 个 observation：

- `v1_baseline_reproduced`：复现已登记 V1。
- `v1_overlay_cap3x_all_selected`：保持 V1 中选交易不变，对每笔中选交易做账户暴露上限 `3x`。
- `v1_overlay_cap2_5x_all_selected`：保持 V1 中选交易不变，对每笔中选交易做账户暴露上限 `2.5x`。
- `v1_overlay_trx_macd_cap3x` / `v1_overlay_trx_macd_cap2_5x`：仅对 TRX `macd_flip` 中选交易降杠杆。
- `v1_filter_no_trx_macd_candidates`：在账户单仓选择前移除 TRX `macd_flip` 候选。
- `v1_filter_no_exposure_gt3x_candidates`：在账户单仓选择前移除所有冻结暴露 `>3x` 的候选。
- `v1_overlay_cap3x_extra_slippage_4bps_per_fill` / `v1_overlay_cap2_5x_extra_slippage_4bps_per_fill`：在 cap 后额外加入 `4 bps/fill` 不利滑点。
- `v1_overlay_cap3x_double_fee_slippage` / `v1_overlay_cap2_5x_double_fee_slippage`：在 cap 后额外加入一整份基准 roundtrip fee+slippage，即等价于 fee+slippage 加倍。

成本压力是交易后账户层近似：按 capped notional 从 `equity_ret` 扣除额外成本；不会改变 stop/target 路径，也不是 K 级成交重演。

## 核心结果

| Observation | Selected | Max exposure | Full annual | Full return | Full DD | Reused holdout annual | Holdout return | Holdout DD | Last 7d return | Worst DD | DD gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| V1 baseline | `371` | `5.0x` | `287.01x` | `+3,999,748%` | `-21.43%` | `7.67x` | `+65.31%` | `-19.79%` | `+0.46%` | `-21.43%` | fail |
| cap all to `3x` | `371` | `3.0x` | `192.49x` | `+1,893,142%` | `-19.99%` | `6.57x` | `+59.11%` | `-16.54%` | `+0.46%` | `-19.99%` | pass, 贴线 |
| cap all to `2.5x` | `371` | `2.5x` | `122.81x` | `+816,068%` | `-18.68%` | `5.14x` | `+49.77%` | `-15.92%` | `-0.14%` | `-18.68%` | pass |
| TRX MACD cap `3x` | `371` | `3.5x` | `237.75x` | `+2,811,394%` | `-19.99%` | `6.32x` | `+57.60%` | `-17.31%` | `+0.46%` | `-19.99%` | pass, 贴线 |
| TRX MACD cap `2.5x` | `371` | `3.5x` | `226.59x` | `+2,569,211%` | `-19.99%` | `6.02x` | `+55.72%` | `-17.13%` | `+0.46%` | `-19.99%` | pass, 贴线 |
| remove TRX MACD | `344` | `3.5x` | `188.29x` | `+1,816,492%` | `-19.99%` | `7.66x` | `+65.26%` | `-15.92%` | `+0.46%` | `-19.99%` | pass, 贴线 |
| filter exposure `>3x` | `319` | `3.0x` | `56.04x` | `+187,771%` | `-19.99%` | `4.91x` | `+48.12%` | `-16.77%` | `+0.46%` | `-19.99%` | pass, 贴线 |
| cap `3x` + extra slip | `371` | `3.0x` | `134.46x` | `+966,972%` | `-20.18%` | `4.81x` | `+47.38%` | `-17.25%` | `-0.05%` | `-20.18%` | fail |
| cap `2.5x` + extra slip | `371` | `2.5x` | `88.47x` | `+441,597%` | `-19.19%` | `3.86x` | `+39.58%` | `-16.82%` | `-0.60%` | `-19.19%` | pass |
| cap `3x` + double cost | `371` | `3.0x` | `54.66x` | `+179,186%` | `-25.49%` | `2.21x` | `+21.60%` | `-25.49%` | `-1.31%` | `-25.49%` | fail |
| cap `2.5x` + double cost | `371` | `2.5x` | `38.88x` | `+94,615%` | `-25.58%` | `1.89x` | `+16.97%` | `-25.58%` | `-1.77%` | `-25.58%` | fail |

## 解读

`3x` cap 是最小改动，但不是稳健改动。它通过压低 TRX `macd_flip` 等高暴露交易，把原 V1 的最大回撤刚好压回线内；然而最差窗口只剩约 `1.3 bps` 回撤余量，任何成交摩擦、资金费偏差或真实下单滑点都可能让它重新失败。

`2.5x` cap 的收益仍明显高于等权组合，且基准成本和额外 `4 bps/fill` 压力下都守住 `<20%` 回撤线。它的代价是近端 `last_7d` 从小正转小负，说明 V1 的近端优势并不厚；这不是坏事，反而暴露了真实边际。

TRX `macd_flip` 的确是最高暴露源，V1 中选 `37` 笔 TRX MACD；但只处理它无法形成足够回撤缓冲。原因是组合还有其他 `3.5x` 或 `3x` sleeve，在单仓全额权益结构下，账户尾部风险不是单一腿的问题。

## 当前失败边界

本轮仍不能 promotion，原因如下：

1. 本轮是账户覆盖层 overlay，不是逐 K 联合状态机重演；被阻塞交易没有反向影响各 sleeve 后续 cooldown 与信号序列。
2. 成本压力为交易后近似，不改变 stop/target 路径，也不模拟 K+2 延迟、gap 跳空或真实下单失败。
3. 双倍 fee+slippage 下 `cap3x` 与 `cap2.5x` 都失败，说明策略仍需要执行成本冗余。
4. 成分家族全部仍是 diagnostic NO-GO，组合不能清洗成分层的问题。

## 决策

本轮登记为未编号 diagnostic observation：`BIN-1H-AR-MAE-V1-RISK-OVERLAY-2026-07-09`。不登记 `V1.1` 或 `V1.2`。

后续建议：

1. 若要冻结下一版，优先考虑 `V1 + 全账户单笔暴露 cap 2.5x`，而不是 `3x`。
2. 在冻结前先实现逐 K 联合状态机重演，确认阻塞后各 sleeve 的后续信号不会大幅漂移。
3. 对 `cap2.5x` 做真实 K+2、额外滑点、double-cost、资金费扰动和缺 K fail-closed 压力；当前交易后成本近似只能作为筛查。

## 证据

- 汇总 JSON：`../artifacts/binance_1h_ar_mae_v1_risk_overlay_diagnostics_2026-07-09.json`
- 对照矩阵 CSV：`../artifacts/binance_1h_ar_mae_v1_risk_overlay_matrix_2026-07-09.csv`
- 复现脚本：`../scripts/research_binance_1h_ar_mae_v1_risk_overlay_diagnostics.py`
