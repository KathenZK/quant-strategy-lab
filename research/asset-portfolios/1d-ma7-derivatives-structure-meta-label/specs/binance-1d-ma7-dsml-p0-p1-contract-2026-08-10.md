# BIN-1D-MA7-DSML P0/P1 数据与模型合同

## 1. 目标与边界

- Family：`Binance-1D-MA7-Derivatives-Structure-Meta-Label`
- Alias：`BIN-1D-MA7-DSML`
- 状态：`explore / diagnostic-only / not promoted / not live-ready`
- 问题：在冻结的 V6-style maturity 经济事件上，OI、top-trader/global positioning、taker flow 与 leave-target-out 市场结构能否提供局部价格路径没有的严格 OOF 增量。
- 本合同在下载/查看历史 metrics 结果前冻结 source、event identity、特征、模型、CV、threshold 与硬门；不得结果后删资产、分方向救援或加入本地技术指标。

本家族不改写 LMML 的 root、maturity、entry、exit、费用、funding 或标签，不使用 VIPR locked holdout，也不是 DAPML/LMML 的价格特征续调。

## 2. 数据源与 HYPE 硬锁

- Event substrate：固定读取 LMML 证据 `p0_p1_events.parquet`，预期 `1,448` 行；先核对 event identity SHA256，不一致即失败。
- Derivatives source：Binance Vision USD-M daily metrics archive：

```text
data/futures/um/daily/metrics/<SYMBOL>/<SYMBOL>-metrics-<YYYY-MM-DD>.zip
```

- Assets：`BTCUSDT / ETHUSDT / BNBUSDT / SOLUSDT / TRXUSDT`；metrics 与 event 均严格 `ts < 2025-05-31T00:00:00Z`。
- Native fields：`create_time`、`symbol`、`sum_open_interest`、`sum_open_interest_value`、`count_toptrader_long_short_ratio`、`sum_toptrader_long_short_ratio`、`count_long_short_ratio`、`sum_taker_long_short_vol_ratio`。
- ZIP 必须通过 CRC；CSV schema、symbol、UTC、5 分钟网格、唯一性、数值有限性、OI/OI value/ratio 正值均 fail closed。
- Raw ZIP 保存在标准数据湖 `data/raw/derivatives_metrics/...`；接受后的合并特征输入保存在 `data/features/binance_derivatives_metrics_p0/`，并由 artifact manifest 记录 URL、日期、状态、字节数与 SHA256。
- 下载清单、代码、文件名、模型 universe 都禁止 `HYPE`；输出必须声明 HYPE rows/files/requests 均为零。
- 本合同没有 HYPE 解锁阶段。

## 3. 因果快照与覆盖

对 event 的 `signal_ts=t`，任何 metrics 行必须满足 `create_time < t`。Local 与每个 peer 均计算：

- last observation age `<=15m`；
- 6h/24h/72h window 实际行数至少为预期的 `95%`；
- 30d reference window 实际行数至少为预期的 `95%`；
- 168h OI lag 必须存在且 lag observation age `<=15m`。

任一 local 条件失败，event 不可用。Cross-market 至少有三个**不含 target asset**的 peer 完整，按可用 peers 等权聚合；held target 永远不进入自己的 market aggregate。

P0 容量门：

1. usable events `>=1,300`；
2. 每资产 `>=200`；
3. long/short 各 `>=550`；
4. usable rate `>=90%`；
5. 每资产 source date coverage `>=95%`，且事件窗口不存在未记录的断层。

P0 任一失败则停止，不拟合 P1。

## 4. 冻结特征

比率统一先取自然对数；方向对齐比率定义为 `side * log(ratio)`。OI change 为 log difference，不按方向取反，因为 OI 上升同时可确认 long/short 风险扩张。

Local 18 项：

1. `is_short`
2. `maturity_age_days`
3. `aligned_taker_log_mean_6h`
4. `aligned_taker_log_mean_24h`
5. `aligned_taker_log_mean_72h`
6. `aligned_taker_log_change_24h`
7. `aligned_global_ls_log_mean_24h`
8. `aligned_global_ls_log_z30d`
9. `aligned_top_account_log_mean_24h`
10. `aligned_top_account_log_z30d`
11. `aligned_top_position_log_mean_24h`
12. `aligned_top_position_log_z30d`
13. `aligned_top_minus_global_24h`
14. `oi_log_change_6h`
15. `oi_log_change_24h`
16. `oi_log_change_72h`
17. `oi_log_change_168h`
18. `oi_value_log_change_24h`

Leave-target-out market 8 项：

19. `market_median_aligned_taker_24h`
20. `market_median_aligned_global_ls_24h`
21. `market_median_aligned_top_account_24h`
22. `market_median_aligned_top_position_24h`
23. `market_median_oi_change_24h`
24. `market_median_oi_change_72h`
25. `market_aligned_taker_positive_breadth`
26. `local_minus_market_oi_change_24h`

禁止 asset id、symbol one-hot、价格/MA/RSI/ATR/volume feature、未来 OI、插值和全样本缺失填充。静态 control 只用前两项。

## 5. Label、权重与模型

- 主 label：冻结 LMML `label = 1[z_8bps>0]`。
- 经济列：冻结 `z_4bps / z_8bps / z_funding_off / z_lag1`。
- 每个 event 一行；训练 sample weight 令每个资产权重和相同，再归一到样本数。

候选模型：

1. `StandardScaler + L2 LogisticRegression`：
   - `C in {0.03, 0.10, 0.30, 1.00}`
   - `solver=lbfgs`、`max_iter=3000`、`random_state=20260810`
2. `LightGBM LGBMClassifier`：
   - `num_leaves in {7, 15}`
   - `n_estimators=200`、`learning_rate=0.03`
   - `max_depth=-1`、`min_child_samples=50`
   - `reg_lambda=5.0`、`subsample=1.0`、`colsample_bytree=1.0`
   - `random_state=20260810`、单线程 deterministic

共同 threshold：`{0.50, 0.55, 0.60, 0.65}`。静态 control 只运行 Logistic 同一 `C/threshold` 网格。

## 6. Nested LOAO × expanding time

- 外层：与 LMML 相同，五个 held asset × 后 60% 时间四个 expanding blocks，共 20 folds。
- Test：held asset 当前完整时间块。
- Train：其余四资产，且 event `exit_ts < test_start-5d`；held asset 不进入 scaler、模型、threshold、缺失处理或 aggregate。
- Inner：outer train 内 `50% initial + 3 expanding blocks`，相同 event grouping、purge 与 embargo。
- 每个 model × hyperparameter × threshold 在 inner 必须：合计 accepted `>=60`、long/short 各 `>=15`、三折 mean `z_8bps>0`、合并 PF `>=1.05`。
- 合格项按最差折 mean、合并 mean、PF、更高 threshold、较低复杂度排序。无合格项的 outer fold 固定 `NO_SELECTION`。

OOF probability 与选择必须逐 outer fold 产生；禁止用全历史重拟合结果替代。

## 7. P1 硬门

全部满足才算 derivatives structure 有增量：

1. P0 容量门通过；
2. OOF accepted `>=100`，每资产 `>=15`，long/short 各 `>=30`；
3. 聚合 `z_8bps` mean `>0`、PF `>=1.15`；
4. 至少 `4/5` held assets mean 为正；
5. 至少 `15/20` outer folds mean 为正，无交易折计失败；
6. probability 对连续 `z_8bps` Spearman `>0.03`，且至少 `4/5` 资产为正；
7. `asset × 90d` cluster bootstrap 10,000 次，`P(mean>0)>=0.90`；
8. 相对静态 control：对全部共同 OOF events，未选择 utility=0，cluster bootstrap `P(Δutility>0)>=0.90`；
9. derivatives feature permutation importance 中，至少两个非静态特征在跨 fold 中位 importance `>0`；
10. `z_4bps`、funding-off、`z_lag1` 均 mean `>0`、PF `>=1.05`，lag 可执行率 `>=90%`。

强制报告 model choice 稳定性、每资产/方向/fold/90d block、threshold `±0.05`、recent `1d/7d/1m/3m/6m/1y`；recent 只作审计。

## 8. 失败与证据

- P0/P1 任一失败：`HARD-GATE-FAILED / explore / not promoted / not live-ready`；不保存 frozen model、不读取 HYPE、不进行 transfer。
- 不得在失败后添加 asset id、价格指标、方向 route、更多树容量或 threshold。
- Basis/premium、liquidation 或真正订单簿是不同信息源，只能另立合同；本合同失败不能把它们事后补进来。

必须保留 source manifest、数据质量/容量 JSON、feature panel、OOF predictions、inner/outer selection、control、bootstrap、stress、报告/摘要、manifest/SHA256、中文 diagnostic、decision log、同步/研究脚本和回归测试。
