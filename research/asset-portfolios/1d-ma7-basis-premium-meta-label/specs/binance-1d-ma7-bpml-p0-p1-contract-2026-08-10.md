# BIN-1D-MA7-BPML P0/P1 数据与模型合同

## 1. 目标与边界

- Family：`Binance-1D-MA7-Basis-Premium-Meta-Label`
- Alias：`BIN-1D-MA7-BPML`
- 状态：`explore / diagnostic-only / not promoted / not live-ready`
- 问题：官方 premium-index 与 mark/index basis 能否在冻结的 V6-style maturity 事件上，区分可支付成本的低拥挤趋势延续与高拥挤噪声，并严格超越原 LMML price-path 模型。

本家族不改写 LMML root、maturity、entry、exit、label、费用、funding 或事件身份。它不是 DSML 的缺值修复：DSML 测试 OI/positioning/taker；本家族使用独立、长历史、原生 `1h` basis/premium K 线。

本合同在下载完整 basis 历史和读取其经济结果前冻结。已完成的 source-only S3 listing 只确认五资产从上市期至 `2025-05` 均有月包，未生成 feature、label 条件统计或模型结果。

下载后、读取 event label 或运行模型前，source audit 发现 BTC premium `2020-12` 官方包缺 `2020-12-01T23:00:00Z` 一根。原“每个 ZIP 全月连续”要求因此 fail closed；修订为保留 gapful 原始拼接于 cache、每个 event 对完整窗口逐项准入。原缺口必须永久进入质量报告，不得补值或把 gapful 拼接标为 accepted feature。

## 2. 冻结事件与 HYPE 硬锁

- Event substrate：[LMML frozen event panel](../../1d-ma7-later-maturity-meta-label/artifacts/p1_development_2026-08-10/p0_p1_events.parquet)
- Event rows：`1,448`
- Event identity SHA256：`f224974f99f65a0ee53545e4fca8870a65555c4dafc4a42c12bfb623ebc1a777`
- Assets：`BTCUSDT / ETHUSDT / BNBUSDT / SOLUSDT / TRXUSDT`
- Development cutoff：所有 source row 与 event 均严格 `<2025-05-31T00:00:00Z`
- HYPE：P0/P1 下载清单、文件、特征、训练、选择与输出均禁止 HYPE，rows/files/requests 必须全部为零。

只有 P1 全部硬门通过并写出冻结模型后，才允许另立 HYPE exposed-target transfer 合同。P1 失败时不得读取 HYPE basis、V6 schedule 或 432 日 outcome。

## 3. 官方 Source 与质量门

Binance Vision USD-M monthly `1h` ZIP：

```text
data/futures/um/monthly/premiumIndexKlines/<SYMBOL>/1h/
data/futures/um/monthly/markPriceKlines/<SYMBOL>/1h/
data/futures/um/monthly/indexPriceKlines/<SYMBOL>/1h/
```

每个 ZIP 必须：

- S3 ETag/MD5、bytes、ZIP CRC 与 SHA256 身份通过；
- 只有一个 CSV，schema 固定为 Binance kline 12 列；
- `open_time` 唯一、递增并落在精确 UTC 小时，`close_time=open_time+1h-1ms`；官方缺根按 dataset/asset/timestamp 原样记录；
- mark/index OHLC 有限且大于零，premium OHLC 有限并满足 `low <= open/close <= high`；
- source identity、symbol、dataset、month 与路径一致。

Raw ZIP 存入标准数据湖 `data/raw/derivatives_basis/...`；未接受的 gapful 按资产/dataset 拼接只存入 `data/cache/binance_1d_ma7_bpml_p0_unaccepted/`。真正接受的 event panel 只由第 4 节逐 event 准入后写入 family artifacts。禁止插值、nearest、round、跨月替代或把 API 当前值回填历史。

## 4. 因果窗口

LMML 的 `signal_ts` 是 maturity 日 K 的开盘 timestamp；实际决策边界为冻结 `entry_ts = signal_ts + 1d`。Basis 特征只允许使用：

```text
open_time < entry_ts
close_time < entry_ts
```

每个 event 的 local premium/mark/index 必须：

- 最后一根为 `entry_ts - 1h`；
- premium、mark、index 先按精确 timestamp inner join，最后连续 `744h` 每根都必须存在且唯一；
- 前 `6h/24h/72h` 完整；
- z-score reference 为“最近 24h 均值”之前的完整 `30d` hourly 分布；
- mark 与 index 在每个 timestamp 一一对应；
- `mark_index_basis = log(mark_close / index_close)`。

Leave-target-out market aggregate 至少有三个不含 target 的完整 peers；不足则删除 event。held target 不得进入自己的 market aggregate、scaler、threshold 或模型选择。

## 5. P0 容量门

1. usable events `>=1,300`；
2. 每资产 `>=200`；
3. long/short 各 `>=550`；
4. usable rate `>=90%`；
5. accepted event 的全部 local window 完整，market peers `>=3`；
6. HYPE rows/files/requests 全部为零。

任一失败即停止 P1。

## 6. 冻结 Basis/Premium 特征

`side=+1/-1`；`aligned(x)=side*x`。Local 十六项：

1. `aligned_premium_close`
2. `aligned_premium_mean_6h`
3. `aligned_premium_mean_24h`
4. `aligned_premium_mean_72h`
5. `aligned_premium_change_24h`
6. `aligned_premium_z30d`
7. `premium_vol_24h`
8. `premium_range_24h`
9. `premium_crowded_fraction_24h`
10. `aligned_mark_index_basis_close`
11. `aligned_mark_index_basis_mean_24h`
12. `aligned_mark_index_basis_mean_72h`
13. `aligned_mark_index_basis_change_24h`
14. `aligned_mark_index_basis_z30d`
15. `mark_index_basis_vol_24h`
16. `aligned_premium_minus_mark_basis_24h`

Leave-target-out 六项：

17. `market_median_aligned_premium_24h`
18. `market_median_aligned_mark_basis_24h`
19. `market_premium_crowded_breadth`
20. `market_mark_basis_crowded_breadth`
21. `local_minus_market_aligned_premium_24h`
22. `local_minus_market_aligned_mark_basis_24h`

定义：

- `change_24h`：最近 24h 均值减前一个 24h 均值，再按 side 对齐；
- `z30d`：最近 24h 均值相对其之前 30 日完整 hourly 分布的 z-score，再按 side 对齐；
- `vol`：hourly close 的总体标准差，不按方向；
- `range`：最近 24h `max(high)-min(low)`；
- crowded fraction：最近 24h 中 `side * value > 0` 的比例；
- market crowded breadth：同期 peers 中 `aligned_*_mean_24h > 0` 的比例；
- premium-minus-mark：`side * (premium_mean_24h - mark_index_basis_mean_24h)`。

禁止 absolute price、asset id、symbol one-hot、missingness feature、未来 normalization 与结果后删特征。

## 7. Control、Full 与模型

- `price_control`：LMML 冻结的全部 causal price/root/hourly/funding/market features，顺序与冻结事件 panel 一致。
- `basis_only`：`is_short + maturity_age_days + 22` 个 basis 特征，仅作机制诊断，不能单独触发 HYPE 解锁。
- `price_plus_basis`：price control + 22 basis 特征；这是主 full route。

Primary model 对 full/control 完全相同：

- `StandardScaler + L2 LogisticRegression`
- asset-balanced sample weights
- `C in {0.03, 0.10, 0.30, 1.00}`
- threshold `{0.50, 0.55, 0.60, 0.65, 0.70}`
- route `combined / long_only / short_only`
- `solver=lbfgs`、`max_iter=3000`、`random_state=20260810`

禁止结果后增加树模型容量。Basis-only 使用相同候选但只报告。

Basis permutation importance 固定为：每个已选 outer 模型在本 fold test 中分别随机置换一个 basis feature `20` 次，记录“原策略全 test-row utility（未选=0）减置换后 utility”的均值；随机种子由 `20260810 + fold/asset/feature` 固定，最终取各 fold importance 中位数。

## 8. Nested LOAO × Expanding Time

- 外层：五 held assets × 后 60% 时间四个 expanding blocks，共 20 folds。
- Train：其余四资产，且 `exit_ts < test_start-5d`；test 为 held asset 当前 block。
- Inner：outer train 内 `50% initial + 3 expanding blocks`，相同 purge 和 asset isolation。
- 每个候选先满足：总 accepted `>=40`、每 inner fold `>=8`、三折 mean `z_8bps>0`、合并 PF `>=1.05`；combined 另要求 long/short 各 `>=15`。
- 合格项按最差折 mean、合并 mean、PF、更高 threshold、更低复杂度、`combined > long_only > short_only` 排序；无合格项固定 `NO_SELECTION`。

Full、price control、basis-only 使用完全相同 accepted event panel 和 outer folds，各自独立 nested 选择。

## 9. P1 硬门

主 full 必须全部满足：

1. P0 通过；
2. OOF accepted `>=100`，每资产 `>=15`；combined 时 long/short 各 `>=30`；
3. `z_8bps` mean `>0`、PF `>=1.15`；
4. 至少 `4/5` held assets mean 为正；
5. 至少 `15/20` outer folds mean 为正；
6. probability/`z_8bps` Spearman `>0.03`，至少 `4/5` 资产为正；
7. `asset × 90d` cluster bootstrap `P(mean>0)>=0.90`；
8. 对共同 OOF events、未选择 utility=0，full-control bootstrap `P(Δutility>0)>=0.90`；
9. 至少两个 basis feature 在至少 `15` 个 outer folds 有 permutation 结果，且跨 fold importance 中位数 `>0`；
10. `z_4bps`、funding-off、可交易 `z_lag1` mean `>0`、PF `>=1.05`，lag 可执行率 `>=75%`；
11. 相对 all-matured baseline，至少 `3/5` 资产同时提高累计事件收益并降低事件序列 MDD。

强制报告 basis-only、model/route choice、每资产/方向/fold/90d block、threshold `±0.05` 及最近 `1d/7d/1m/3m/6m/1y`；不参与选择。

`z_lag1` 可执行率门在读取 basis 或运行模型前由冻结 event schema 从 `90%` 修正为 `75%`：原 `1,448` events 中仅 `79.70%` 的一日滞后仍早于冻结 exit，缺失不是数据缺口而是原 probe 已结束；继续要求 `90%` 会使该 stress 在机制上不可满足。

## 10. 失败处理

- P0/P1 任一失败：`HARD-GATE-FAILED / explore / not promoted / not live-ready`。
- 不保存 frozen model，不下载/读取 HYPE，不生成 transfer score 或组合路径。
- 不得在失败后按资产/方向设 threshold、删 basis 特征、增加模型容量或改变 maturity target。
- 若本轮失败，结合 LMML/RHT/DSML/DSTO 证据，判定当前公共 price/OI/funding/basis 信息未证明可以跨资产识别 V6-style 漏趋势；后续只能等待 clean prospective 或引入 liquidation/order-book/外部数据的新合同。
