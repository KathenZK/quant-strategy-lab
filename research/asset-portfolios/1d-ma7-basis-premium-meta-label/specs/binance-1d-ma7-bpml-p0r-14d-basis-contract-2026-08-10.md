# BIN-1D-MA7-BPML P0R 14 日 Basis 修订合同

## 1. 修订原因

原 [P0/P1 合同](binance-1d-ma7-bpml-p0-p1-contract-2026-08-10.md) 使用连续 `744h`（当前 24h + 之前 30 日）窗口。948 个官方 ZIP 的身份/schema/OHLC 均通过，但跨资产存在少量整日缺包和单根缺口；逐 event fail-closed 后只接受 `1,233/1,448（85.15%）`，未达到 `>=1,300 / >=90%`，原 P0 明确失败，证据保留在 [原 30 日容量 JSON](../artifacts/p0_data_2026-08-10/p0_original_30d_capacity.json)。

本修订在未读取 `label/z_8bps/z_4bps/z_funding_off/z_lag1`、未训练模型、未统计任何 feature-outcome 关系时冻结。修订依据只有 source timestamp continuity 与 event 的 asset/side/entry timestamp。

## 2. 唯一变化

- 每个 local/peer 的完整准入窗口从 `744h` 改为 `360h`：当前 `24h` + 之前连续 `14d=336h`。
- `aligned_premium_z30d` 改名并重定义为 `aligned_premium_z14d`。
- `aligned_mark_index_basis_z30d` 改名并重定义为 `aligned_mark_index_basis_z14d`。
- z-score 仍为最近 24h 均值相对其之前完整 hourly reference 的 `(x-mean)/population_std`。
- population std 非有限或 `<=0` 时直接删除 event；禁止 epsilon、补值或替代。

其余 local/market features、price control、label、模型、nested LOAO、threshold/route、成本、stress、增量门、HYPE 锁与失败处理全部继承原合同，不得改变。

## 3. P0R 容量门不降

继续要求：

1. usable events `>=1,300`；
2. 每资产 `>=200`；
3. long/short 各 `>=550`；
4. usable rate `>=90%`；
5. 每个 accepted target 与至少三个 leave-target-out peers 的 premium/mark/index 共同 `360h` 精确连续；
6. 948 个 source archive 身份/schema 通过，原 source continuity failure 显式保留；
7. HYPE rows/files/requests 全部为零。

冻结前 source-only 预审为 `1,335（92.20%）`，BTC/ETH/BNB/SOL/TRX 分别 `283/288/264/227/273`，long/short `718/617`；这些数字未读取经济结果，只用于确认修订不是机械不可满足。

## 4. 选择与冻结模型

若 full 通过所有原 P1 硬门，最终 frozen choice 取 20 个 outer fold choice 的众数；同票依次选择更高 threshold、更小 `C`、`combined > long_only > short_only`。该 final choice 只用于全 development panel 冻结，不回写 OOF。

## 5. 失败处理

P0R 失败则停止。P0R 通过但 P1 失败，则本 family 记为 `HARD-GATE-FAILED`，不保存模型、不读取 HYPE；不得再按 outcome 改成 7 日、按资产窗口或 asset-specific threshold。
