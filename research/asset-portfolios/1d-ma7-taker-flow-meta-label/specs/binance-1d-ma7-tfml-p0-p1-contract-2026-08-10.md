# BIN-1D-MA7-TFML P0/P1 Taker-Flow Expected-Utility 合同

## 1. 目标与边界

- Family：`Binance-1D-MA7-Taker-Flow-Meta-Label`
- Alias：`BIN-1D-MA7-TFML`
- 状态：`explore / diagnostic-only / not promoted / not live-ready`
- 研究问题：冻结 V6-style maturity event 上，原生 5 分钟 aggressor/taker quote flow 能否直接预测成本后 `z_8bps` 经济幅度，并严格超越使用相同 continuous model/policy 的 price-only control。

本家族保留 LMML 的 root、maturity、entry、exit、成本、funding 与 event identity，但不再以 `label=1[z_8bps>0]` 为模型 target。BPML 已显示 binary probability 的 OOF AUC 约 `0.51–0.53`、收益 Spearman 却为负；本家族改用 continuous expected utility，不继承 BPML 的模型或 promotion 证据。

本合同在下载完整五资产 5m flow 历史、构建 flow features 或运行任何 outcome-conditioned model 前冻结。

## 2. Event、时间与 HYPE 硬锁

- Event substrate：[LMML frozen event panel](../../1d-ma7-later-maturity-meta-label/artifacts/p1_development_2026-08-10/p0_p1_events.parquet)
- Rows：`1,448`
- Identity：`f224974f99f65a0ee53545e4fca8870a65555c4dafc4a42c12bfb623ebc1a777`
- Development assets：`BTCUSDT / ETHUSDT / BNBUSDT / SOLUSDT / TRXUSDT`
- Development cutoff：source/event 均严格 `<2025-05-31T00:00:00Z`
- HYPE：P0/P1 requests/files/rows/features/train/evaluation 全部为零。

P1 即使通过，也不得直接读取 HYPE。下一步必须先冻结模型和 policy，再用 `2025-05-31` 之后、尚未进入本轮研究的五资产数据做一次 P2 expanding temporal validation；只有 P2 通过才允许另立 HYPE exposed-target transfer 合同。

## 3. 官方 Source 与质量

Binance Vision USD-M monthly：

```text
data/futures/um/monthly/klines/<SYMBOL>/5m/<SYMBOL>-5m-YYYY-MM.zip
```

Source-only listing 已确认到 `2025-05`：

- BTC/ETH：各 `65` 月；
- BNB：`64` 月；
- SOL：`57` 月；
- TRX：`65` 月；
- 合计压缩体积约 `110.64 MiB`。

每个 ZIP 必须通过 S3 ETag/MD5、bytes、CRC、SHA256；CSV 固定 12 列。`open_time` 唯一递增、落在 UTC 5 分钟边界，`close_time=open_time+5m-1ms`；OHLC 有限且正，volume/quote/count/taker-buy 非负，`taker_buy_volume<=volume`、`taker_buy_quote_volume<=quote_volume`（仅允许浮点 `1e-10` 相对误差）。

Raw 存 `data/raw/taker_flow/...`。任何 source gap 都原样记录，gapful 拼接只存 `data/cache/binance_1d_ma7_tfml_p0_unaccepted/`；accepted event panel 只能由第 4 节逐 event 准入后进入 family artifacts。禁止插值、nearest、round、API 回填或把 missingness 当特征。

## 4. 因果准入

决策边界为冻结 `entry_ts`。Local 与 peer source 只允许：

```text
open_time < entry_ts
close_time < entry_ts
```

每个 local/peer 必须以 `entry_ts-5m` 结尾，并有连续 `360h = 4,320` 根 5m bars。Target local 不合格即删除；leave-target-out 同期 peers 至少 `3/4` 合格。

定义：

- `buy_quote=taker_buy_quote_volume`
- `sell_quote=quote_volume-buy_quote`
- `net_quote=buy_quote-sell_quote=2*buy_quote-quote_volume`
- window imbalance：`sum(net_quote)/sum(quote_volume)`
- 零成交 bar 的 `net_quote=0`；per-bar imbalance 只在 `quote_volume>0` 上计算，不能以 0 参与 persistence/std。
- `side=+1/-1`；`aligned(x)=side*x`。

## 5. P0 容量门

1. usable events `>=1,300`；
2. 每资产 `>=200`；
3. long/short 各 `>=550`；
4. usable rate `>=90%`；
5. accepted target 与至少三个 peers 都有完整 4,320-row causal window；
6. source identity/schema/field constraints 通过，gap 被显式保留；
7. HYPE requests/files/rows `0/0/0`。

任一失败即停止 P1。

## 6. 冻结 Flow 特征

Local 十七项：

1. `aligned_taker_imbalance_1h`
2. `aligned_taker_imbalance_6h`
3. `aligned_taker_imbalance_24h`
4. `aligned_taker_imbalance_72h`
5. `aligned_taker_imbalance_change_6h_24h`
6. `aligned_taker_imbalance_change_24h_72h`
7. `aligned_taker_imbalance_z14d`
8. `aligned_flow_persistence_6h`
9. `aligned_flow_persistence_24h`
10. `taker_imbalance_std_24h`
11. `taker_imbalance_range_24h`
12. `max_quote_volume_share_24h`
13. `max_trade_count_share_24h`
14. `quote_volume_ratio_24h_14d`
15. `trade_count_ratio_24h_14d`
16. `aligned_flow_return_divergence_24h`
17. `flow_price_correlation_24h`

计算规则：

- z/reference：当前 24h window imbalance 相对之前 14 个非重叠 UTC-aligned 24h windows 的 population z-score；
- persistence：活跃 5m bars 中 `side*per_bar_imbalance>0` 的比例，活跃 bars 必须分别至少为理论 rows 的 `90%`；
- concentration：当前 24h 最大单 bar quote/count 占 window 总量；
- volume/count ratio：当前 24h 总量除之前 14 日中位数；
- divergence：`aligned_flow_z14d - aligned_return_z14d`；return z 使用相同 14 个非重叠窗口的 log return；
- flow-price correlation：当前 24h 活跃 bars 的 per-bar imbalance 与 close-to-close log return Pearson；有效 pairs `>=260`，零方差则删除 event。

Leave-target-out 六项：

18. `market_median_aligned_taker_imbalance_6h`
19. `market_median_aligned_taker_imbalance_24h`
20. `market_median_aligned_taker_imbalance_72h`
21. `market_aligned_flow_breadth_24h`
22. `local_minus_market_aligned_taker_imbalance_24h`
23. `market_median_aligned_flow_return_divergence_24h`

禁止 symbol/asset id、absolute price、future normalization、source availability 或结果后删特征。

## 7. Model 与 Policy

- `price_utility_control`：冻结 47 个 LMML price/root/hourly/funding/market features。
- `flow_only`：`is_short + maturity_age_days + 23` flow features，仅作诊断。
- `price_plus_flow`：price control + 23 flow features，主 full。
- Target：continuous `z_8bps`，已包含 fee、8bps/fill slippage、0.25x leverage 与实际 funding。
- Model：`StandardScaler + Ridge`，asset-balanced sample weights。
- `alpha in {1, 10, 100, 300, 1000}`。
- predicted-utility threshold `{0.0000, 0.0005, 0.0010, 0.0015}`。
- route：`combined / long_only / short_only`。

Flow permutation 固定 20 repeats，按 test-row policy utility decrease 计算；最终至少 15 folds 才能形成 feature importance。

## 8. Nested LOAO × Expanding Time

- Outer：五 held assets × 后 60% 时间四块，共 20 folds。
- Train：其余四资产，`exit_ts < test_start-5d`；test 只含 held asset。
- Inner：outer train 内 `50% initial + 3 expanding blocks`，相同 purge。
- 候选先满足：总 accepted `>=40`、每 inner fold `>=8`、三折 `z_8bps` mean 都 `>0`、合并 PF `>=1.05`；combined 另要求 long/short 各 `>=15`。
- 排序：最差折 mean、合并 mean、PF、更高 predicted threshold、更大 alpha（更强 shrinkage）、`combined > long_only > short_only`。
- 无合格候选固定 `NO_SELECTION`，不得使用 outer outcome 补选。

Full/control/flow-only 独立 nested 选择，但共享完全相同 accepted panel、folds 与 target。

## 9. P1 硬门

Full 必须全部满足：

1. P0 通过；
2. OOF accepted `>=100`、每资产 `>=15`，combined 时 long/short 各 `>=30`；
3. `z_8bps` mean `>0`、PF `>=1.15`；
4. 至少 `4/5` held assets mean 正；
5. 至少 `15/20` outer folds mean 正；
6. predicted utility / `z_8bps` Spearman `>0.03`，至少 `4/5` 资产为正；
7. `asset×90d` bootstrap `P(mean>0)>=0.90`；
8. common OOF、未选 utility=0 的 full-control `P(Δutility>0)>=0.90`；
9. 至少两个 flow features 在 `>=15` folds 的 permutation median `>0`；
10. `z_4bps`、funding-off、可执行 lag1 mean `>0`、PF `>=1.05`，lag 可执行率 `>=75%`；
11. 至少 `3/5` 资产相对 all-matured OOF 同时提高 compound 并降低 MDD，每资产 selected `>=15`。

强制报告 alpha/threshold/route choice、每资产/方向/fold/90d block、threshold `±0.0005`、近 `1d/7d/1m/3m/6m/1y`；均不参与选择。

## 10. 失败与后续

- P0/P1 失败：`HARD-GATE-FAILED / explore / not promoted / not live-ready`；不保存模型、不读 HYPE。
- 不得在失败后改成 binary target、按资产 alpha、降低 threshold 到负数、删除失败资产或增加树模型。
- P1 通过只允许冻结 P2 post-cutoff 五资产合同，不构成 HYPE 解锁、promotion 或 live-ready。
