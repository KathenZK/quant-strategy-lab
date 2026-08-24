# BIN-1D-MA7-QUML P0/P1 Quantile-Utility 合同

## 1. 目标与证据边界

- Family：`Binance-1D-MA7-Quantile-Utility-Meta-Label`
- Alias：`BIN-1D-MA7-QUML`
- 状态：`explore / diagnostic-only / not promoted / not live-ready`
- 研究问题：当 price-only Ridge 的收益排序有 fresh 证据、绝对 predicted-utility calibration 却跨资产不稳定时，能否只用训练样本预测分布的 quantile 形成 scale-free policy，并在第二组完全未见资产上稳定筛选 V6-style maturity events。

前序 [TFML Fresh-Universe 诊断](../../1d-ma7-taker-flow-meta-label/diagnostics/binance-1d-ma7-tfml-p1e-fresh-universe-2026-08-10.md) 显示：

- taker flow 相对 price control 的增量已被否定，不能继续使用；
- price-only control 在八个 fresh assets 上 218 笔 mean `+0.1664%`、PF `1.257`、ranking Spearman `0.0916` 且 6/8 资产 ranking 为正；
- 但只有 4/8 资产与 13/32 folds 收益为正、bootstrap `86.36%`，不能 promotion 或 transfer。

本合同在读取 BCH/ETC/XLM/ATOM/VET/NEAR/AAVE/FIL maturity outcome 前冻结。不得使用前两轮 outer outcome 调本轮 quantile、资产或 feature。

## 2. Universe 与 Fresh Holdout

Legacy training universe：

```text
BTC / ETH / BNB / SOL / TRX /
XRP / DOGE / ADA / LINK / LTC / DOT / AVAX / UNI
```

Second-fresh outer universe：

```text
BCH / ETC / XLM / ATOM / VET / NEAR / AAVE / FIL
```

Second-fresh basket 在 outcome 未读时固定：

- Binance USD-M USDT perpetual；
- canonical monthly native `5m` listing 最晚从 `2020-10` 开始并连续列包到 `2025-05`；
- 共 `491` 个 source ZIP、`167,192,685 bytes（159.45 MiB）`；
- BCH/ETC/XLM/ATOM/VET 增加长期支付、PoW 与 L1 暴露；NEAR/AAVE/FIL 增加 2020 年 L1/DeFi/storage 异质性；
- 不按后续事件数、收益、ranking 或模型结果删资产。

Outer held assets 只允许 second-fresh 八资产。13 个 legacy assets 可训练，但其历史 OOF 不计入 P1 gate。

## 3. 数据、Event 与 HYPE 锁

- Cutoff：严格 `<2025-05-31T00:00:00Z`。
- Price：Binance direct USD-M `1h` OHLCV，完整 UTC `1d` 聚合。
- Funding：官方 funding history + endpoint mark / 同小时 mark-price kline open。
- Event：LMML/V6-style soft MA7 cross、最多五日 asymmetric maturity、下一日 open 入场、日线 MA7 recross 或最多五日退出。
- Cost：fee `0.001/fill`、主 slippage `8bps/fill`、`0.25x`、实际 funding；`z_4bps`、funding-off、lag1 同时保留。
- HYPE requests/files/rows/features/train/evaluation：全部为零。

21 个资产必须从 source 重新生成 event：

- local price feature 定义保持 47 项；
- leave-target-out market price features 以 20 个同期 peers 重算；
- 不拼接旧 panel；
- 新 event identity 单独冻结。

## 4. P0 容量门

Second-fresh 必须全部满足：

1. eligible events 合计 `>=1,600`；
2. 每资产 `>=180`；
3. long/short 各 `>=650`；
4. 47 features 与四种 outcome 全部按原规则可审计；lag1 允许因 probe 已结束而缺失；
5. direct `1h` 完整、UTC `1d` 可由 24 根精确重建、funding gap `<=8h`；
6. source identity/SHA256 通过；
7. HYPE `0/0/0`。

任一失败即停止 P1。

## 5. Model

- Features：TFML 的 47 个 price/root/hourly/funding/leave-target-out market features；无 flow/basis/OI、无 asset id。
- Target：continuous `z_8bps`。
- Model：`StandardScaler + Ridge`，asset-balanced weights。
- Alpha：`{1,10,100,300,1000}`。
- Route：`combined / long_only / short_only`。
- Quantile：`{0.80,0.90,0.95}`。

Quantile threshold 只能从**当前拟合 train rows 的 predicted utility** 计算：

1. 按 candidate route 过滤 train predictions；
2. threshold 为对应 quantile；
3. validation/test 只选择 route 合格且 prediction `>=threshold` 的 rows；
4. 不能从 validation/test prediction distribution 重算 quantile；
5. 不能用 held asset 历史 calibration。

这使 policy 仍可应用于单一 HYPE，而不是依赖同日跨资产排名。

## 6. Absolute-Threshold Control

必须在相同 21-asset panel 和完全相同 second-fresh outer folds 上运行原 TFML price control：

- alpha 相同；
- absolute threshold `{0,0.0005,0.0010,0.0015}`；
- route 相同；
- inner eligibility/ranking 相同。

Quantile full 必须严格超越该 control；只证明自身正收益不够。

## 7. Nested LOAO × Expanding Time

- Outer：8 个 second-fresh held assets × 后 60% 时间四块，共 `32` folds。
- Train：其余 20 资产，`exit_ts < test_start-5d`；held asset 全历史排除。
- Test：只含 held asset 当前 block。
- Inner：outer train 内 `50% initial + 3 expanding blocks`，同样 purge。

每个 quantile candidate 的 inner gate：

- 每折 selected `>=8`；
- 三折 mean 全 `>0`；
- 合并 selected `>=40`、PF `>=1.05`；
- combined 时 long/short 各 `>=15`。

排序：最差折 mean、合并 mean、PF、更高 quantile、更大 alpha、`combined > long_only > short_only`。无合格 candidate 固定 `NO_SELECTION`。

## 8. P1 Hard Gate

只在 second-fresh OOF 上计算，Quantile 必须全部满足：

1. P0 通过；
2. selected `>=160`，每资产 `>=15`，至少 `24` 个 asset×90d blocks；combined 被选择时 long/short 各 `>=50`；
3. `z_8bps` mean `>0`、PF `>=1.15`；
4. 至少 `6/8` held assets mean 正；
5. 至少 `24/32` outer folds mean 正；
6. predicted utility / `z_8bps` Spearman `>0.05`，至少 `6/8` 资产为正；
7. `asset×90d` bootstrap `P(mean>0)>=0.90`；
8. common OOF、未选 utility=0 的 quantile-absolute-control `P(Δutility>0)>=0.90`；
9. `z_4bps`、funding-off、lag1 mean `>0`、PF `>=1.05`，lag 可执行率 `>=75%`；
10. 至少 `5/8` 资产相对 all-matured OOF 同时提高 compound 并降低 MDD，每资产 selected `>=15`；
11. HYPE lock。

强制报告 quantile/alpha/route、每资产/方向/fold/90d block、quantile `±0.05`、近 `1d/7d/1m/3m/6m/1y`；均不参与选择。

## 9. Terminal Rule

- P0/P1 失败：`HARD-GATE-FAILED`；不保存模型、不读取 HYPE，并关闭 pooled historical maturity-selection 路线。不得再从剩余 eligible assets 补挑第三组 holdout。
- P1 通过：只允许先冻结 post-cutoff 21 资产 P2 合同；P2 通过前 HYPE 仍锁定。
- 任何 HYPE transfer 必须另立 exposed-target 合同，失败不得反向改 quantile。
