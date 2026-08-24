# BIN-1D-MA7-RSI6-DAPML P1 Pooled Development 合同

## 1. 身份、目标与权限

- Family：`Binance-1D-MA7-RSI6-Direction-Aligned-Pooled-ML`
- 阶段：P1 `development-only` pooled event-quality 研究
- 状态：`explore / diagnostic-only / not promoted / not live-ready`
- 目标：验证方向对齐特征能否在新时间和未见资产上稳定排序成本后 MA7 穿越事件。
- P1 不是组合回测，不处理同时信号的资金分配、账户总杠杆或组合路径 MDD；通过也只能取得一次性 sealed validation 揭示资格。
- validation 揭示仍须用户单独明确批准；P1 脚本必须输出 `validation_authorized=false`。

## 2. P0 冻结输入

继承 [P0 数据与特征合同](binance-1d-ma7-rsi6-dapml-p0-data-feature-contract-2026-08-10.md)：

- Universe：`BTC / ETH / BNB / SOL / TRX`；
- development 截止：`2025-08-06 UTC`；
- 所有资产共同 sealed：`2025-08-07` 至 `2026-08-06 UTC`；
- direct `1h`、24 根小时 K 聚合 `1d`、官方实际 funding 与 `1h` mark；
- 日线收盘确认、次日开盘成交、`3×ATR7` fixed stop；
- fixed `1×`、每 fill fee `0.001`、不利 slippage `4 bps`、实际 funding；
- RSI6 `80/20` 极值后反向确认、反向 MA7 穿越、无最长持仓。

P0 development 事件固定为：

| Asset | Events | Long | Short |
| --- | ---: | ---: | ---: |
| BTC | 449 | 224 | 225 |
| ETH | 458 | 229 | 229 |
| BNB | 389 | 195 | 194 |
| SOL | 362 | 181 | 181 |
| TRX | 433 | 216 | 217 |
| Total | 2,091 | 1,045 | 1,046 |

事件 identity SHA256：

```text
c9bdf1d4e32fa85f11b6b2d5e9de3062d05489acef8ddc68497bfd3a65970b83
```

行数或 hash 不一致时停止，不得训练。

## 3. 特征与资产权重

### 3.1 主特征

主模型只使用 P0 冻结的 19 个方向对齐字段：

```text
aligned_prev_gap_atr
aligned_close_gap_atr
aligned_cross_span_atr
aligned_ma7_slope_1_atr
aligned_ma7_slope_3_atr
prior_side_duration
aligned_body_atr
range_atr
rejection_wick_atr
opposition_wick_atr
aligned_close_location
aligned_return_3_atr
aligned_return_5_atr
aligned_rsi6
aligned_rsi6_delta_1
directional_rsi_extreme_5
counter_rsi_extreme_5
directional_rsi80_last5
counter_rsi20_last5
```

- 主模型不输入 `asset id`、裸 `side`、quote volume 或 trade count。
- 连续字段已按本资产 signal-day ATR 归一化，不做全样本 z-score；Logistic 的 scaler 只在每折训练集拟合。
- 每折使用 asset-balanced sample weight：每个训练资产总权重相同，避免穿越次数多的资产支配模型。

### 3.2 Raw 对照

`logistic_ev_raw_control` 使用 BTC P1 的 20 个原始 `MA+K+RSI` 字段，包括裸 `side`，但不添加 side interaction。它只用于检验方向对齐改写是否真正增加跨资产可辨识性。

## 4. 冻结模型

### 4.1 唯一主候选：Logistic-EV aligned

```text
StandardScaler
LogisticRegression(
  C=1.0,
  solver=lbfgs,
  max_iter=2000,
  class_weight=None,
  random_state=20260810
)
```

每折只用训练集、按 asset-balanced weight 计算：

```text
mean_win  = weighted mean(net_return where net_return > 0)
mean_loss = weighted mean(net_return where net_return <= 0)
predicted_ev = P(win) * mean_win + (1 - P(win)) * mean_loss
```

不做概率校准、特征选择、交互搜索或模型容量搜索。

### 4.2 对照与诊断

- `logistic_ev_raw_control`：同模型、raw 特征，只满足方向对齐消融。
- `lgbm_ev_aligned_diagnostic`：相同 aligned 特征和 EV 换算，参数固定如下，只作非线性诊断，不能在本合同下替代主模型取得 validation 资格。

```text
objective=binary
n_estimators=120
learning_rate=0.03
num_leaves=7
max_depth=3
min_child_samples=20
subsample=0.8
subsample_freq=1
colsample_bytree=0.8
reg_alpha=0.5
reg_lambda=2.0
random_state=20260810
n_jobs=1
deterministic=true
force_col_wise=true
```

## 5. 时间 OOS 与 edge

### 5.1 外层

- 按 unique `signal_ts` 切分，禁止同一天的不同资产进入 train/test 两侧。
- 初始 `40%` 日期训练，剩余日期顺序分为四个外层测试块。
- 每折训练事件必须同时满足 `signal_ts < first_test_signal` 和 `exit_ts < first_test_signal`。

### 5.2 Inner edge

- 每个外层训练集再按 unique signal date 做 `50% + 3 blocks` nested walk-forward。
- 候选 edge 固定为 `0 / 0.50% / 1.00%`。
- 只有 `predicted_ev > edge` 才选择；等于不选。
- 合格 edge 要求每个 inner test fold 至少 `20` 笔，且所有训练资产在三折合计各至少 `5` 笔。
- 排序先最大化三折最差 `mean net_return`，并列时选更低 edge，再选更多交易。
- 无合格 edge 的外层输出 no-selection，不得降低门槛。

## 6. Temporal OOS 主门禁

路线顺序为 combined 优先；combined 失败后才允许 long-only / short-only。冻结路线必须同时满足：

1. 外层 OOS 选择事件总数 `>=100`；
2. 五个资产各至少 `10` 笔；
3. equal-event 复合成本后收益 `>0`；
4. PF `>=1.20`；
5. 至少 `3/4` 外层 fold 绝对复合收益 `>0`；
6. 至少 `3/4` fold 的选择事件平均收益高于同路线 all-cross；
7. 总选择事件平均收益高于同路线 all-cross；
8. `Spearman(predicted_ev, net_return) >0.10`；
9. 至少 `3/4` fold 的预测 EV 最高五分位实际平均收益高于该 fold 全部事件；
10. 按 `outer fold × asset` 分层的 `10,000` 次 trade bootstrap 中，复合收益为正概率 `>=95%`。

bootstrap seed 固定 `20260810`，报告 `2.5% / 50% / 97.5%` 分位数。

## 7. Leave-one-asset + time OOS 门禁

对五个 held asset 分别执行四个外层时间折：

- test 只含 held asset 当前未来时间块；
- train 只含其他四资产，且严格早于 test 首日并 purge 未结束事件；
- edge 仍只在该折训练集内 nested 选择；
- 不允许用 held asset 的任何训练行、均值或 scaler。

与 temporal 路线相同的 combined/单边路线必须满足：

1. 五个 held asset 各至少 `10` 笔；
2. 至少 `4/5` 资产 equal-event 复合收益 `>0`；
3. held-asset 合并复合收益 `>0`；
4. 合并 PF `>=1.10`；
5. 合并选择事件平均收益高于 held-asset all-cross；
6. 合并 `Spearman(predicted_ev, net_return) >0.05`。

## 8. 方向对齐消融门禁

主 aligned Logistic 与 raw Logistic 必须使用相同时间折、edge 集和路线。Aligned 必须：

1. temporal OOS 选择事件平均收益高于 raw；
2. leave-one-asset OOS 选择事件平均收益高于 raw；
3. 五个 held asset 中至少三个的复合收益高于 raw。

任一不满足都说明“方向对齐解决结构问题”的假设未获支持。

## 9. 总判定与后续

P1 通过要求：

```text
temporal OOS 全门禁
AND leave-one-asset + time OOS 全门禁
AND direction-aligned ablation 全门禁
```

- P1 失败：不揭示任何 sealed period，不继续在同一特征/edge 集上微调。
- P1 通过：只标记 `validation eligible / not authorized`，先汇报，再等待用户单独授权。
- sealed validation 即使未来通过，也仍不是 promotion；还缺同时信号仲裁、组合总杠杆、组合路径 MDD、压力测试和 live-executable audit。

## 10. 必须交付

- P0 event hash 一致性；
- 三个模型的 temporal 四折、nested edge 和分资产结果；
- 五资产 leave-one-asset × 四时间折；
- aligned/raw 消融；
- 主路线分层 bootstrap；
- Logistic 系数、scaler、mean win/loss 与状态 hash；
- `1d/7d/1m/3m/6m/1y` development-end recent slices，仅作 audit；
- 失败时只保留 JSON/Parquet 与 Markdown diagnostic，不生成 trade-path HTML。
