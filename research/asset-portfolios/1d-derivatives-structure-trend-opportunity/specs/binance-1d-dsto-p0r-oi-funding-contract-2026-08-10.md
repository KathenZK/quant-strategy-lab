# BIN-1D-DSTO P0R/P1 OI + Funding 修订合同

## 1. 修订原因与证据边界

- Family：`Binance-1D-Derivatives-Structure-Trend-Opportunity`
- Alias：`BIN-1D-DSTO`
- 状态：`explore / diagnostic-only / not promoted / not live-ready`
- 原 [P0/P1 合同](binance-1d-dsto-p0-p1-contract-2026-08-10.md) 要求六个 metrics 字段全历史、全 5 分钟网格和 30 日窗口 `100%` 完整；官方日包实际存在缺行、错位 timestamp 和大段 ratio null，因此原 P0 已失败，禁止按原合同运行 P1。
- 本修订在**未生成 long/flat/short label、未读取未来 5 日收益、未训练模型**时冻结。修订依据只包括 source schema/质量和精确端点容量；不得据后续经济结果继续删特征、改阈值或改资产。
- 原 full-field 失败不会被覆盖；[P0 source-quality 诊断](../diagnostics/binance-1d-dsto-p0-source-quality-2026-08-10.md) 与本路线结果分别记账。

## 2. 研究问题

在官方 positioning/taker 字段不可形成可信连续面板后，只保留可逐 anchor fail-closed 接受的 open interest 精确端点，并加入已审计的历史 funding pressure。检验 OI + funding 是否能在同一 daily-anchor / fixed-5d 经济问题上严格超越 price-only control。

这不是降低经济门禁，也不是把缺值补成可用值；任何缺端点、重复端点、非正 OI、无效 funding 或 peer 不足的 anchor 直接删除。

## 3. 数据、时间与 HYPE 硬锁

- Universe：`BTCUSDT / ETHUSDT / BNBUSDT / SOLUSDT / TRXUSDT`。
- OI source：Binance Vision USD-M daily metrics ZIP，`[2021-12-01, 2025-05-31) UTC`；每个 ZIP 必须继续通过 S3 ETag/MD5、ZIP CRC、SHA256 与 source manifest 身份校验。
- Price/funding：已审计 direct `1h` OHLCV 与官方 funding/mark，严格 `<2025-05-31T00:00:00Z`。
- Anchor：每日 `00:00 UTC`，`[2021-12-08, 2025-05-25) UTC`；起点只由最长 `168h` causal warmup 决定。
- HYPE：rows/files/requests 必须全部为零；本合同没有 HYPE transfer。
- gapful 全量 metrics 拼接只可位于 `data/cache/binance_1d_dsto_p0_unaccepted/`，不得伪装为 accepted feature。耐久研究证据是 source manifest、质量报告和经过本合同逐 anchor 接受后的 panel。

## 4. 精确端点准入

每个本地 asset-anchor 只读取以下严格早于 anchor 的原始 timestamp：

1. `anchor - 5m`
2. `anchor - 6h`
3. `anchor - 24h`
4. `anchor - 72h`
5. `anchor - 168h`

五个 timestamp 必须精确存在且唯一；`sum_open_interest` 和 `sum_open_interest_value` 必须有限且大于零。禁止 nearest、round、forward-fill、backfill、线性插值或跨日替代。

Funding 使用 `funding_nominal_ts < anchor`：

- `24h/72h/168h` 窗口至少分别有 `3/9/20` 条；
- 最后一条距 anchor 不超过 `8h`；
- 所有 rate 有限；
- 只使用 anchor 前已发生记录。

Market aggregate 只使用 target 之外同期合格资产，至少 `3/4` peers；不足则删除该 target-anchor。资产缺失本身不作为模型特征。

## 5. P0R 容量门

1. usable anchors `>=6,100`；
2. 每资产 `>=1,200`；
3. 每个 accepted anchor 的本地端点与 funding 全部通过第 4 节，且 market peers `>=3`；
4. long/flat/short label 各 `>=500`；
5. source manifest 身份通过，原 full-field `quality_pass=false` 被显式保留；
6. HYPE rows/files/requests 全部为零。

任一失败即停止 P1。冻结前仅做 source-only 预审得到 `6,118` 个候选 anchor；该数字不含 label 或收益筛选。

## 6. Outcome、成本与 label

沿用原合同：

- anchor open 入场，`+120h` open 退出，固定 `0.25x`；
- funding 严格使用 `entry < funding.ts < exit`；
- fee `0.001/fill`；
- 主列 `4bps/fill`，保守 label `8bps/fill`，另报 `12bps/fill`、funding-off 和 entry/exit 同延迟 `+1h`；
- `LONG`：`long_z_8bps >= +0.0025`；
- `SHORT`：`short_z_8bps >= +0.0025`；
- 否则 `FLAT`。

## 7. 冻结特征

Price-only control 仍为原合同八项：

1. `return_24h`
2. `return_72h`
3. `return_168h`
4. `realized_vol_24h`
5. `realized_vol_168h`
6. `efficiency_24h`
7. `efficiency_72h`
8. `close_location_168h`

Local OI/funding 增量十四项：

9. `oi_log_change_6h`
10. `oi_log_change_24h`
11. `oi_log_change_72h`
12. `oi_log_change_168h`
13. `oi_value_log_change_24h`
14. `oi_acceleration_24h_72h = oi_log_change_24h - oi_log_change_72h / 3`
15. `price_oi_confirmation_24h`
16. `price_oi_confirmation_72h`
17. `funding_sum_24h`
18. `funding_sum_72h`
19. `funding_sum_168h`
20. `funding_acceleration_24h_72h = funding_sum_24h - funding_sum_72h / 3`
21. `funding_positive_share_168h`
22. `oi_funding_crowding_24h = oi_log_change_24h * funding_sum_24h`

Leave-target-out market 八项：

23. `market_median_oi_change_24h`
24. `market_median_oi_change_72h`
25. `market_median_oi_change_168h`
26. `market_positive_oi_breadth_24h`
27. `market_median_funding_sum_24h`
28. `market_positive_funding_breadth_24h`
29. `local_minus_market_oi_change_24h`
30. `local_minus_market_funding_sum_24h`

Full 模型共 30 项；control 只用前 8 项。禁止 asset id、symbol one-hot、missingness feature 和全样本标准化。

## 8. 模型、CV 与执行排程

- 模型候选、超参数和 threshold 完全沿用原合同：四个 L2 Logistic `C`、两个固定 LightGBM、threshold `{0.45, 0.55, 0.65}`。
- Nested `LOAO × expanding time`、120h purge、held-asset 隔离、asset-balanced weights 和 inner admission 门全部不变。
- 每资产成交后 120h 内忽略后续 anchor；禁止重叠、反手或叠仓。
- Full 与 control 使用完全相同 accepted anchors 和 outer folds，各自独立 nested 选择。

## 9. P1 硬门

沿用原合同全部经济门：

1. P0R 通过；
2. OOF trades `>=300`，每资产 `>=40`，long/short 各 `>=100`；
3. 主 `z_4bps` mean `>0`、PF `>=1.15`；
4. 至少 `4/5` held assets mean 为正；
5. 至少 `15/20` outer folds mean 为正；
6. confidence/return Spearman `>0.03`，至少 `4/5` 资产为正；
7. `asset × 90d` cluster bootstrap `P(mean>0)>=0.90`；
8. 对共同 OOF anchors 的 full-control utility delta，bootstrap `P(Δ>0)>=0.90`；
9. 至少两个 OI/funding feature 的跨 fold permutation importance 中位数 `>0`；
10. `8bps` 与 funding-off mean `>0`、PF `>=1.05`；
11. lag `+1h` 全覆盖、mean `>0`、PF `>=1.05`。

`12bps`、threshold `±0.05`、model choice、资产/方向/fold/90d block及最近 `1d/7d/1m/3m/6m/1y` 仅报告，不参与选择。

## 10. 失败处理

- P0R 或 P1 失败：`HARD-GATE-FAILED`，不保存 frozen model，不读取 HYPE，不 transfer。
- 不得在失败后增加 asset-specific threshold、方向参数、更多树容量、MA7/root 或缺值代理。
- 若 OI/funding 失败，说明当前可可信提取的 Binance 公共 derivatives 历史未证明跨资产 5 日增量；basis、liquidation、order-book 或其他提供商数据必须另立数据合同。
