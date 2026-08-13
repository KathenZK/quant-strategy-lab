# BIN-1D-DSTO P0/P1 数据与模型合同

## 1. 目标与边界

- Family：`Binance-1D-Derivatives-Structure-Trend-Opportunity`
- Alias：`BIN-1D-DSTO`
- 状态：`explore / diagnostic-only / not promoted / not live-ready`
- 问题：在官方 metrics 共同覆盖期内，derivatives structure 能否在每日固定锚点预测成本后 5 日 long/flat/short，并严格超越同容量的 price-only control。
- 本合同在下载共同历史前冻结数据、anchor、特征、label、模型、CV、执行排程与硬门；不得结果后增加 MA7/root、删资产、按方向或资产设参数。

本家族不是 DSML 降门：它删除稀疏 maturity event，建立新的高容量 daily-anchor target；也不是 VIPR/PIC 的 entry/exit 变体。

## 2. 数据与 HYPE 硬锁

- Universe：`BTCUSDT / ETHUSDT / BNBUSDT / SOLUSDT / TRXUSDT`。
- Metrics：Binance Vision USD-M daily metrics ZIP，范围 `[2021-12-01, 2025-05-31) UTC`。
- Price/funding：已审计 direct `1h` OHLCV 与官方 funding/mark，严格 `<2025-05-31T00:00:00Z`。
- Anchor：每日 `00:00 UTC`，范围 `[2022-01-01, 2025-05-25) UTC`；前 30 日只作 feature warmup，后六日容纳 120h outcome 与 lag。
- HYPE：S3 prefix、下载清单、文件名、features、model universe 与输出禁止 HYPE；rows/files/requests 均必须为零。本合同无 transfer。

ZIP 必须通过 CRC，下载 bytes 的 MD5 必须等于 S3 ETag，并另存 SHA256。CSV 的 schema、symbol、UTC 5 分钟网格、唯一性、正 OI/OI value/ratios、有限数值全部 fail closed。

Raw ZIP 存入：

```text
data/raw/derivatives_metrics/exchange=binance/market_type=perp/
timeframe=5m/source=binance_vision/date=<UTC>/symbol=<slug>.zip
```

接受后的按资产合并输入存入 `data/features/binance_1d_dsto_p0/`；artifact manifest 保留每个 source key、ETag、bytes、SHA256 与 feature identity。

## 3. P0 容量与质量门

- 每个 metrics 日应有 288 个 `5m` timestamp，从 `00:00` 到 `23:55 UTC`；缺日、缺行、重复或跨日均 fail closed。
- Direct `1h` 必须无缺口，metrics/price/funding 时间单调且不晚于 cutoff。
- 每个 anchor 的 metrics 特征只用 `ts < anchor`；last observation age `<=5m`，6h/24h/72h/168h 与 30d window 均需 100% 完整。
- 每个 anchor 必须有 entry open、`+120h` exit open 和 `+1h` lag 对应完整结果。

P0 必须：

1. usable anchors `>=6,100`；
2. 每资产 `>=1,200`；
3. 五资产全部 source day coverage `=100%`；
4. long/flat/short label 各 `>=500`；
5. HYPE rows/files/requests 均为零。

任一失败即停止 P1。

## 4. Anchor outcome 与三分类 label

Anchor `t` 在 `open[t]` 成交，固定 `0.25x`，在 `open[t+120h]` 退出。Funding 严格使用 `t < funding.ts < t+120h`；fee `0.001/fill`。

同时预生成 long/short：

- `4bps/fill` 主经济列；
- `8bps/fill` 保守 label/stress；
- `12bps/fill`；
- funding-off；
- entry/exit 同延迟 `+1h`。

分类使用保守结果：

```text
LONG  if long_z_8bps  >= +0.0025
SHORT if short_z_8bps >= +0.0025
FLAT  otherwise
```

若 long/short 同时过门则数据或公式错误。`0.0025` 是 `0.25x` sleeve 的 `+0.25%` equity hurdle，不参与结果后调整。

## 5. 冻结 price-only control 特征

全部只用 anchor 前闭合 `1h`：

1. `return_24h`
2. `return_72h`
3. `return_168h`
4. `realized_vol_24h`
5. `realized_vol_168h`
6. `efficiency_24h`
7. `efficiency_72h`
8. `close_location_168h`

Return 使用 endpoint log difference；realized vol 是对应小时 log return 的 RMS；efficiency 是 signed endpoint log return 除以逐小时 absolute log-return path sum（零分母取零）；close location 是最后 close 在过去 168 根 high/low 区间中的 `[0,1]` 位置。

## 6. 冻结 derivatives 增量特征

Local：

9. `taker_log_mean_6h`
10. `taker_log_mean_24h`
11. `taker_log_mean_72h`
12. `taker_log_change_24h`
13. `global_ls_log_mean_24h`
14. `global_ls_log_z30d`
15. `top_account_log_mean_24h`
16. `top_account_log_z30d`
17. `top_position_log_mean_24h`
18. `top_position_log_z30d`
19. `top_minus_global_24h`
20. `oi_log_change_6h`
21. `oi_log_change_24h`
22. `oi_log_change_72h`
23. `oi_log_change_168h`
24. `oi_value_log_change_24h`
25. `price_oi_confirmation_24h = return_24h * oi_log_change_24h`
26. `price_oi_confirmation_72h = return_72h * oi_log_change_72h`

Leave-target-out market：

27. `market_median_taker_log_24h`
28. `market_median_global_ls_log_24h`
29. `market_median_top_account_log_24h`
30. `market_median_top_position_log_24h`
31. `market_median_oi_change_24h`
32. `market_median_oi_change_72h`
33. `market_positive_taker_breadth`
34. `local_minus_market_oi_change_24h`

Market aggregate 必须使用另外四资产，禁止 target 泄漏、asset id、symbol one-hot、全样本标准化或插值。

Ratio feature 先取自然对数。`mean_6h/24h/72h` 是对应完整 5 分钟窗口均值；`change_24h` 是最近 24h 均值减前一个 24h 均值；`z30d` 用最近 24h 均值相对其之前完整 30 日 5 分钟分布的 z-score。OI change 用 anchor 前最后一条与精确 `6/24/72/168h` lag 条目的 log difference。

## 7. 模型、权重与 policy

Full 使用 34 项；control 只用前 8 项。两者使用完全相同候选：

1. `StandardScaler + LogisticRegression`：
   - `C in {0.03, 0.10, 0.30, 1.00}`
   - `solver=lbfgs`、`max_iter=3000`、`random_state=20260810`
2. `LGBMClassifier`：
   - `num_leaves in {7, 15}`
   - `n_estimators=200`、`learning_rate=0.03`
   - `min_child_samples=50`、`reg_lambda=5.0`
   - `subsample=1.0`、`colsample_bytree=1.0`
   - deterministic、单线程、`random_state=20260810`

训练 sample weight 使五资产权重和相同。Policy：

```text
direction = argmax(P_LONG, P_SHORT)
trade only if max(P_LONG, P_SHORT) >= threshold
           and max(P_LONG, P_SHORT) > P_FLAT
threshold in {0.45, 0.55, 0.65}
```

每个 asset 按 anchor 排序，成交后 120h 内其余 anchor 忽略；不得重叠、反手或叠仓。

## 8. Nested LOAO × expanding time

- 外层：五 held assets × 后 60% 时间四个 expanding blocks，共 20 folds。
- Test：held asset 当前 block 全部 anchors。
- Train：其余四资产，且 label exit `< test_start-120h`；held asset 不进入 scaler、模型、threshold 或 aggregate。
- Inner：outer train 内 `50% initial + 3 expanding blocks`，相同 purge、asset isolation 与非重叠 policy。
- 每个 model × hyperparameter × threshold 在 inner 必须：合计 trades `>=120`、long/short 各 `>=40`、三折 mean `z_4bps>0`、合并 PF `>=1.05`。
- 合格项按最差折 mean、合并 mean、PF、更高 threshold、较低模型复杂度排序；无合格项固定 `NO_SELECTION`。

Full 与 control 独立 nested 选择，但共享完全相同 folds。

## 9. P1 硬门

Full 必须全部满足：

1. P0 通过；
2. OOF trades `>=300`，每资产 `>=40`，long/short 各 `>=100`；
3. 主 `z_4bps` mean `>0`、PF `>=1.15`；
4. 至少 `4/5` held assets mean 为正；
5. 至少 `15/20` outer folds mean 为正，无交易折计失败；
6. confidence 对已选方向连续 `z_4bps` Spearman `>0.03`，至少 `4/5` 资产为正；
7. `asset × 90d` cluster bootstrap 10,000 次，`P(mean>0)>=0.90`；
8. Full 相对 control：全部共同 OOF anchors、未交易 utility=0，cluster bootstrap `P(Δutility>0)>=0.90`；
9. 至少两个 derivatives feature 的跨 fold permutation importance 中位数 `>0`；
10. `8bps` 与 funding-off mean `>0`、PF `>=1.05`；
11. lag `+1h` 可执行率 `>=90%`、mean `>0`、PF `>=1.05`。

`12bps`、threshold `±0.05`、model choice、资产/方向/fold/90d block、recent `1d/7d/1m/3m/6m/1y` 强制报告；recent 不参与选择。

## 10. 失败与证据

P0/P1 任一失败：不保存 frozen model、不下载/读取 HYPE、不 transfer。不得在失败后添加 asset id、按资产/方向 threshold、更多树容量或 MA7 filter。Basis/liquidation/order book 只能另立合同。

必须保留 source/feature manifest、P0 quality/capacity、anchor panel、full/control OOF scores/trades、inner/outer selection、importance、bootstrap、stress、摘要/完整 JSON、SHA256、中文 diagnostic、decision log、同步/研究脚本与测试。
