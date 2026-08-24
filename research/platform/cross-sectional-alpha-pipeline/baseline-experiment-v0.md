# Baseline Experiment V0 — Binance USD-M 4H/24H Cross-Sectional Residual Alpha

## 1. 身份与目的

- Experiment ID：`BIN-CS-BASELINE-V0`
- 类型：平台验收 baseline，不是策略版本。
- 状态：`preregistered design / not run / diagnostic-only / not promoted / not live-ready`。
- 目的：验证从 PIT universe 到 OOF RankIC、简单 long-short、成本与 capacity proxy 的完整链路；不以收益达到某个数字作为验收。
- 禁止：在同一历史揭示后反复修改 features、universe、label、K、成本或模型并继续称为 V0。

## 2. 为什么选择这个 baseline

当前本地最完整的全市场输入是 Binance USD-M `15m` normalized OHLCV（历史月档约 788 个合约），而不是旧 MHCSML 使用过、现已清理的全市场 `1h` OHLCV。funding 与 mark-price 历史仍较完整；全市场 OI、真 basis、orderbook 和 Hyperliquid panel 尚不完整。

因此 V0：

- 只用 Binance；
- 从完整 `15m` 聚合 `1h`；
- 不用 OI、真 basis、liquidation、orderbook、market cap；
- 先 Ridge/规则 diagnostics，后加 LightGBM control；
- 成本使用 conservative taker baseline，容量只标记为 ADV proxy。

## 3. Data contract

### 3.1 Source

- Venue / market：Binance USD-M USDT linear perpetual。
- Primary OHLCV：`data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m/`。
- 历史主源：`binance_vision_kline_monthly`。
- Funding：`data/normalized/funding_rates/...`，actual settlement events。
- Mark price：`data/normalized/mark_price_klines/.../timeframe=1h/`，仅作 mark premium/风险 feature；coverage 不过 gate 时整组删除，不补 0。
- Data cutoff：取“所有全市场月档均完整的最后一个 UTC 月末”，初始候选为 `< 2026-07-01 00:00 UTC`；运行前由 manifest 确认，不按少数主力尾部延伸。

### 3.2 `15m -> 1h` aggregation

每个 `(instrument_id, UTC hour)` 必须正好四根闭合 `15m`：

```text
open         = first(open)
high         = max(high)
low          = min(low)
close        = last(close)
volume       = sum(volume)
quote_volume = sum(quote_volume)
trade_count  = sum(trade_count)
taker_buy_*  = sum(taker_buy_*)
vwap         = sum(quote_volume) / sum(volume)
```

任何缺根、重复、open time 不在 UTC 15m 网格或 source identity 冲突，该小时 fail closed。聚合层写入 experiment artifact/cache，不伪装成交易所原生 `1h`。

### 3.3 Data splits

- Development：`2020-01-01 <= ts < 2025-01-01`（subject to per-symbol listing）。
- Validation/OOF folds：`2023-01-01` 起半年滚动 outer folds，最终历史 fold 到 `< 2026-01-01`。
- Reused holdout diagnostic：`2026-01-01 <= ts < 2026-07-01`；该历史已被其他家族多次查看，只可做 plumbing/regime 诊断，不是 clean OOS。
- Prospective OOS：V0 pipeline/spec/model/portfolio/cost 全冻结并完成全市场数据同步后，取下一个完整 UTC 日作为 `oos_start`，预注册 `90d`；不得回填错过的 signal。

实际边界写入 registry，不能在结果揭示后移动。

## 4. Universe contract

### 4.1 Primary: `historical_dynamic_liquidity_top100`

在每个 signal K0：

1. 当时是 USDT linear perpetual 且状态可交易；
2. 非 stablecoin / fiat proxy / index / delivery contract；
3. onboard/listing age >= `30d`；若历史 metadata 不完整，同时要求 first trusted bar age >= `30d`；
4. 过去 `30d` 1h coverage >= `99%`；
5. 过去 `7d` average daily quote volume >= `10m USDT`；
6. 按 K0 及以前的 7d ADV 降序，取 Top 100；
7. 平手按 canonical instrument ID；
8. 保存 eligibility/reason/rank/membership SHA。

若有效 breadth < `40`，该时点不做 quantile portfolio，只报告 coverage blocker。

### 4.2 Diagnostic control: `current_top100_retrospective`

只在单独 experiment ID 下运行，冻结 as-of symbol list，强制标记：

```text
SURVIVORSHIP_BIASED_DIAGNOSTIC = true
eligible_for_selection_or_oos = false
```

## 5. Signal and execution time

- Base bar：`1h`；只用闭合 bar。
- Decision cadence：每 `4h`，UTC `00/04/08/12/16/20` 对应的 K0 闭合后。
- Signal time：K0 close 之后。
- Entry：下一根 `1h` K1 open，加 adverse slippage。
- Exit labels：K5 open (`4h`) 与 K25 open (`24h`)。
- Missing/nontradable path：`path_valid=false`，label 为空，不前向填 price。
- 组合每 `4h` 可再平衡；24h sleeve 重叠，必须逐 sleeve/position 记账，不能把 overlapping labels 当独立账户复利。

## 6. Feature manifest（目标约 45 个）

所有 rolling feature 先逐 symbol 计算，再在同一 K0 的 eligible universe 做 cross-sectional transform。

### 6.1 Time-series base features

| Family | Features |
| --- | --- |
| Momentum/reversal | returns `1/4/12/24/72/168h`；EMA spreads `6/24`, `24/96`；MA distance `24/96`；short reversal `1h vs 24h` |
| Volatility/path | realized vol `12/24/72/168h`；downside/upside vol `24/168h`；ATR/price `24/168h`；rolling drawdown `72/336h` |
| Candle geometry | range/price、body/range、upper/lower wick、close location，均含 `1h` 与 `24h` rolling mean 的受控子集 |
| Volume/liquidity | quote-volume shock `6/24/168h`；trade-count shock `24h`；taker imbalance `1/24h`；ADV7d；Amihud `24h`；average trade size `24h` |
| Funding/mark | latest funding、funding mean/zscore/event sum `24/168h`；mark premium level/zscore `24/168h`（coverage gate） |
| Lifecycle | first-trusted-bar age、metadata listing age、coverage30d、liquidity rank |
| Market/BTC context | BTC returns `4/24/168h`；market equal-weight returns；breadth；dispersion；rolling BTC beta；residual momentum |

最终精确 feature names、公式、lookback、source hash、null policy 和 coverage 写入 `feature_manifest.json`。V0 冻结后不能静默增删。

### 6.2 Cross-sectional transforms

对预注册连续 features：

1. same-ts eligible universe 1%/99% winsorize；breadth < 40 时不生成；
2. percentile rank `[0,1]`；
3. robust z-score `(x - median) / MAD`，MAD=0 时为空；
4. 保存 pre/post coverage 与 transform parameters。

不做 sector、market-cap、liquidity 或 vol 完全 neutralization。ADV/vol exposure 只报告；另有受控 cap/weight arm。

## 7. Labels

对 `h in {4h, 24h}` 输出：

```text
label_raw_long_h
label_long_net_h
label_short_net_h
label_market_residual_h
label_btc_beta_residual_h
label_cross_sectional_rank_h
label_long_mae_h / label_short_mae_h
label_path_valid_h
```

公式：

```text
long_net  = exit_open / entry_open - 1 - round_trip_cost - funding_sum
short_net = 1 - exit_open / entry_open - round_trip_cost + funding_sum
```

`market_residual` 使用当时 path-valid universe 的 robust equal-weight future return；`btc_beta_residual` 的 beta 只用 K0 及以前 rolling window，future BTC return 只在 label 中使用。

## 8. Diagnostics-first sequence

### Stage A — Single feature diagnostics

- per-ts IC/RankIC；
- mean/median/ICIR/positive share；
- Q1–Q5 与 top-bottom spread/monotonicity；
- `1/4/8/12/24/72h` decay（同一 score）；
- coverage/breadth/turnover；
- fold/year/BTC-regime stability；
- feature Spearman correlation/clusters；
- BH-FDR for the declared feature-horizon family。

Stage A 不运行策略参数搜索。

### Stage B — Frozen rule composites

最多三个预注册 composite：

1. momentum-relative-strength；
2. short-term reversal；
3. funding-crowding + momentum interaction。

每个 composite 只用经济方向预先固定的 rank features；不按 revealed CAGR 调权。

### Stage C — Linear model

- Ridge primary；Lasso/ElasticNet control；
- nested purged expanding WF；purge `24h`，embargo `24h`；
- hyperparameter grid 总 trial 数预先登记且很小；
- selection metric：validation mean RankIC，再以 turnover/cost作为 constraint；
- 只使用 OOF predictions 构建 portfolio。

### Stage D — LightGBM control

只有 A–C 的 manifests、tests、registry 和 diagnostics 全部 PASS 后才运行：

- fixed conservative parameter set；
- regression L1 primary；ranker control；
- seeds `7/17/29/42` 固定；
- 不扩 feature count；
- 与 Ridge 使用完全相同 folds/labels/portfolio/cost。

## 9. Portfolio baselines

每个 score/horizon 同时输出：

1. top decile long / bottom decile short，equal weight，gross `1.0`、net `0`；
2. top K/bottom K：`K=max(3, floor(0.1*breadth))`，作为 decile 的同义实现校验；
3. score-proportional within selected tails；
4. inverse-vol scaled selected tails（risk control arm）。

共同约束：

- allow cash；
- single-name gross <= `5%`；
- 每腿 target notional <= trailing 24h quote volume 的预注册 participation cap；
- post-weight dollar neutrality tolerance `1e-8`；
- 记录 pre/post BTC beta，但 V0 不强制 beta-neutral；
- 每次调仓生成 target/order/fill/position/funding ledger。

## 10. Cost and capacity proxy

### Baseline cost

- taker fee：`0.001/fill`；
- adverse slippage：`4bps/fill`；
- round trip before funding：`28bps`；
- funding：actual settlements；
- turnover：由 target weight change 精确计算；
- 无法取得 spread/depth 时，不把 `4bps` 描述为真实 impact。

### Stress

- `1.5x` fee+slippage；
- entry delay `+1h`；
- universe ADV threshold `5m/10m/20m` 仅作预注册 robustness，不选主口径；
- top N `50/100/150` 仅作 breadth sensitivity，不选主口径。

### Capacity proxy

Capital grid：`10k, 25k, 50k, 100k, 250k, 500k, 1m USDT`。

每个资金规模输出 order/ADV participation、cap-binding share、unfilled/reduced notional、fixed-cost post-cost performance。可增加明确标记的 `sqrt(participation)` impact scenario，但在 top-of-book/L2 校准前必须写：

```text
capacity_status = PROXY_ONLY
live_capacity_claim_allowed = false
```

## 11. Experiment registry

V0 运行前 receipt 必须含：

- git commit 与 dirty flag；
- exact config/spec SHA；
- source partitions + SHA/size/row range；
- instrument/universe/feature/label/dataset manifests SHA；
- fold boundaries、purge、embargo；
- models、parameter count、seeds；
- declared trials by family；
- selection metric；
- reused-holdout/prospective-OOS policy；
- output artifact hashes。

任何变更生成新 experiment ID；不得覆盖 V0 receipt。

## 12. Suggested config

以下是待 Phase 1 CLI 消费的冻结配置形状，不表示当前 CLI 已实现：

```yaml
experiment_id: BIN-CS-BASELINE-V0
venue: binance
market_type: perp
quote_asset: USDT
source_timeframe: 15m
panel_timeframe: 1h
decision_cadence: 4h
universe:
  mode: historical_dynamic
  min_listing_days: 30
  min_coverage_30d: 0.99
  adv_window_days: 7
  min_adv_usdt: 10000000
  top_n: 100
labels:
  horizons: [4h, 24h]
  entry: next_bar_open
  targets: [raw, long_net, short_net, market_residual, btc_beta_residual, rank]
features:
  manifest: baseline-v0-feature-manifest
  cs_winsor: [0.01, 0.99]
  cs_rank: true
  cs_robust_zscore: true
split:
  method: expanding_walk_forward
  purge: 24h
  embargo: 24h
models: [rule_composite, ridge]
portfolio:
  mode: top_bottom_decile
  weighting: equal
  gross_cap: 1.0
  dollar_neutral: true
  single_name_cap: 0.05
cost:
  fee_per_fill: 0.001
  slippage_bps_per_fill: 4.0
  funding: actual
capacity_capital_usdt: [10000, 25000, 50000, 100000, 250000, 500000, 1000000]
```

## 13. Acceptance criteria

V0 平台验收 PASS 需要：

1. data/universe/panel/feature/label/dataset/registry manifests 全部存在且 SHA 可复算；
2. PIT、future perturbation、cross-talk、K0/K1/Kh、missing path、funding/short formula tests 全过；
3. OOF prediction 无训练内样本、purge/embargo 无 future-window overlap；
4. IC/RankIC/ICIR/quantile/decay/coverage/breadth/stability/correlation 全部生成；
5. portfolio ledger 权重、turnover、cost、funding、PnL 守恒；
6. capacity proxy 随 capital 单调执行，并正确标记 `PROXY_ONLY`；
7. actual trial count 与 registry 一致；
8. Ridge、rule composite 的比较使用相同 universe/folds/labels/cost；
9. reused holdout 不被写成 clean OOS；
10. 不触碰现有 CTA/HYPE 或恢复已归档 CSLGBM/MHCSML 状态。

无论历史收益正负，只要以上全部通过，V0 的“平台 baseline”可以判定完成；策略本身仍是 `diagnostic-only / not promoted / not live-ready`。

## 14. Failure policy

- data/universe/label blocker：停止模型；
- feature coverage blocker：删除整组需新 manifest/experiment ID，不允许按收益挑缺失处理；
- diagnostics 无稳定 RankIC：记录 weak/no alpha，仍可完成平台验收；
- fixed cost 后为负：记录 no tradable alpha，不加杠杆挽救；
- capacity proxy 很低：这是目标研究事实，不是失败理由，但必须限制结论与资金范围；
- prospective OOS 失败：`HARD-GATE-FAILED / not promoted / not live-ready`，不得在同一窗口调参。
