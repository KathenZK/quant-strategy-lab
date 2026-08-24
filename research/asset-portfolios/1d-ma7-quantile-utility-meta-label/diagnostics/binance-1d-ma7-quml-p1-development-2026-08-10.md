# BIN-1D-MA7-QUML P1 盲测诊断

## 复核更正（优先于下文原始输出）

- 当前证据状态：P0 容量与 source quality 有效；P1 `invalidated evidence / explore / not promoted / not live-ready`。
- 21资产 event panel 的 leave-target-out market features 在 outer/inner split 前一次性生成；held asset 的 source history仍进入其他训练资产的 market aggregates，违反冻结合同的“held asset 全历史排除”。
- 下文 quantile/control 数值只保留为受污染历史输出，不能用于 ranking、calibration 或模型增量归因。Second-fresh outcome 已揭示，脚本现已 fail closed；不得修复后在同一篮子重新宣称盲测。
- “不补第三组历史资产、不读 HYPE”继续有效；下一有效证据只能来自全新机制或未见时间窗。

## 原始结论（已撤回）

- 状态：`DEVELOPMENT_HARD_GATE_FAILED / explore / not promoted / not live-ready`
- P0 容量与质量通过；P1 quantile policy 在第二组八个未见资产上失败。
- 失败不是单一 threshold 口径问题：OOF ranking 接近零、预测严重过度乐观，inner 选择在 outer 上系统性翻负。
- 根据冻结合同，终止 pooled historical maturity-selection 路线；不运行 P2、不补第三组历史资产 holdout、不读取 HYPE。

## 数据与执行口径

- 市场：Binance USD-M USDT perpetual。
- 资产：legacy 13 资产训练；BCH/ETC/XLM/ATOM/VET/NEAR/AAVE/FIL 仅作 second-fresh outer。
- 截止：严格 `<2025-05-31T00:00:00Z`。
- 成本：fee `0.001/fill`、主 slippage `8bps/fill`、`0.25x`、实际 funding。
- 成交：闭合日线 maturity signal，下一 UTC daily open 入场。
- HYPE：requests/files/rows/features/train/evaluation 均为 `0`。
- BCH/ETC/XLM 的 FAPI 历史请求在读取 outcome 前遭遇明确 IP ban；改用 Binance Vision 官方月包，并用日包补齐月包缺失小时。共核验 `601` 个 ZIP 的 ETag/MD5、CRC、SHA256，最终小时缺口、日线重建差异、funding blocker 均为 `0`。其余五资产沿用官方 direct FAPI 数据。

## P0

- 全 21 资产 eligible events：`5,880`。
- second-fresh events：`2,197`；每资产 `243–304`。
- long / short：`1,142 / 1,055`。
- event identity：`90dbc962a0ed88f69375687a8ac7c937b1c16760bcdf7b280e5f2c70be92aa7a`。
- 1h 连续性、24 根 UTC 日线重建、47-feature contract、方向容量与 HYPE lock 全部通过。

## P1 主结果

| 指标 | Train-quantile | Absolute control |
| --- | ---: | ---: |
| selected | 158 | 527 |
| `z_8bps` mean | -0.06943% | -0.05568% |
| PF | 0.910 | 0.926 |
| compound | -12.96% | -33.69% |
| event-sequence MDD | -30.56% | -62.64% |
| 正资产 | 3/8 | 4/8 |
| 正 outer folds | 10/32 | 15/32 |
| ranking Spearman | 0.0173 | 0.0011 |
| cluster bootstrap `P(mean>0)` | 31.26% | 24.84% |

Quantile 相对 control 的 common-OOF mean utility 增量仅 `+0.01306%/event`，
`P(Δutility>0)=65.94%`，低于冻结门槛 `90%`。两条 policy 都亏损，不能把
quantile 较小的绝对回撤解释为可迁移 alpha。

## 失效机制

1. **Ranking 不存在**：second-fresh 上 Spearman 仅 `0.0173`；高预测分位没有单调更高的 realized utility。
2. **Calibration 失真**：selected mean prediction 约 `+0.81%`，realized mean 却为 `-0.069%`。
3. **Inner overfit**：合格 inner 组合普遍为正，outer 对应组合系统性翻负；32 folds 的 `(alpha, quantile, route)` 选择高度离散。
4. **时间与资产非平稳**：仅 NEAR/AAVE/FIL 为正，近期 `3m/6m/1y` quantile slices 全负。
5. **不是单边故障**：long 与 short 都为负，删方向或删资产属于揭示后修补。

## `z_lag1` 口径审计

Quantile selected 的 executable-only `z_lag1` 为 `126` 笔、mean `+0.1636%`、PF
`1.232`，但不能解释成延迟入场优势：

- 缺失 lag 的 `32` 笔全部是持有一天即 MA7 recross 的亏损单；
- 在同一 `126` 笔可执行事件上，即时 `z_8bps` mean 约 `+0.232%`，lag1 mean
  `+0.164%`，延迟一天反而少约 `6.9bps/event`；
- 正值来自缺失机制先剔除最差事件，不是 lag 改善。

因此禁止据此新开“一律 lag1”参数线。

## Gate 与终止决定

仅 P0、方向覆盖、时间块覆盖与 HYPE lock 通过；样本门、主经济性、正资产、
正 folds、ranking、bootstrap、相对 control 增量、stress 与双改善全部失败。

复核后按证据污染边界终止：

- 不保存模型，不运行 P2；
- 不在 second-fresh 上改 quantile/alpha/route；
- 不补第三组历史资产 holdout；
- 不把本轮解释成 pooled historical maturity-selection 的有效证伪；
- HYPE 继续锁定。

后续若继续，只能使用未见时间窗或全新机制合同，并在 fold 内重建 market
aggregates；不能把本次输出当新一轮训练后再在相同历史上宣称验证。

## 证据

- [冻结合同](../specs/binance-1d-ma7-quml-p0-p1-contract-2026-08-10.md)
- [P0 source quality](../artifacts/p0_price_data_2026-08-10/p0_data_quality_manifest.json)
- [Vision fallback manifest](../artifacts/p0_price_data_2026-08-10/p0_vision_fallback_manifest.json)
- [P0 event capacity](../artifacts/p0_events_2026-08-10/p0_capacity.json)
- [P1 summary](../artifacts/p1_development_2026-08-10/p1_summary.json)
- [P1 report](../artifacts/p1_development_2026-08-10/p1_report.json)
- [P1 manifest](../artifacts/p1_development_2026-08-10/manifest.json)
