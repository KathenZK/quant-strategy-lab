# BTC-1D-MA7-RSI6-LGBM P2 Expected-Return 合同

## 1. 身份与封存边界

- Family：`BTC-1D-MA7-RSI6-LightGBM-Trend`
- 阶段：P2 `development-only` 期望净收益研究；`explore / diagnostic-only / not promoted / not live-ready`
- P1 已失败；P2 是新的预注册诊断，不得改写 P1 结论。
- P2 继续只读取 `2019-09-09` 至 `2025-08-06 UTC` 的 development 数据。
- 冻结 validation `2025-08-07` 至 `2026-08-06 UTC` 继续禁止读取、预测、画图或用于任何选择。
- P2 通过只取得一次性 validation 揭示资格，不登记版本、不构成 promotion。

## 2. 不变项

P2 完整继承 [P1 development 合同](btc-1d-ma7-rsi6-lgbm-p1-development-contract-2026-08-07.md)的以下内容，不重新搜索：

- 严格 `SMA7` 上穿/下穿候选及多空方向；
- `MA`、五日 `K`、`RSI`、`VOL` 的公式和 point-in-time 边界；
- 事件日收盘确认、次日开盘成交；
- 固定 `1×`、每 fill 手续费 `0.001`、每 fill 不利滑点 `4 bps`、实际 funding；
- RSI6 `80/20` 极值后反向确认、反向 MA7 穿越、固定入场 `3×ATR7` stop；
- 完整 `1h` stop path、gap fill、funding timestamp 规则；
- 无最长持仓、无同方向重入、反向事件合格时允许同开盘反手；
- incomplete event 不读取 validation 补标签。

P2 必须重新生成或校验 P1 的 `449` 个 development 事件；按 `signal/entry/exit timestamp`、`event_id/side/label`、`net_return/net_return_atr`、全部 P1 特征和 `exit_reason` 的冻结字节序计算，P1 event identity SHA256 为 `941246a90a2fe403b6de152e1527bb4ed1890ee84fdb32095b3a2eb87a3fd529`。事件数或 hash 不一致时停止。

## 3. 学习目标

### 3.1 主目标

```text
target_raw = net_return
```

- `net_return` 是固定 `1×` 仓位扣除双边手续费、不利滑点与实际 funding 后的实际事件收益率。
- 原始目标不缩尾、不裁剪、所有事件等权。
- 主模型使用 L2 regression，直接近似条件期望 `E[net_return | features]`。

### 3.2 ATR 诊断目标

```text
target_atr = net_return / (ATR7_signal / entry_fill)
predicted_raw_from_atr =
  predicted_target_atr * (ATR7_signal / entry_fill)
```

- ATR 目标只作独立诊断，不能成为 P2 validation 候选。

## 4. 冻结模型与特征消融

### 4.1 LightGBM Regressor 主容量

```text
objective=regression
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
random_state=20260807
n_jobs=1
deterministic=true
force_col_wise=true
```

- 不搜索模型容量、不 early-stop。
- `lgbm_l2_core`：`MA+K+RSI`，是唯一可取得 validation 资格的 P2 主模型。
- `lgbm_l2_ma`、`lgbm_l2_ma_k`、`lgbm_l2_core_vol`：特征消融。
- `lgbm_l2_atr_diag`：相同 core 特征，预测 ATR 目标后换算为 raw edge，仅作诊断。

### 4.2 Huber 消融

- `lgbm_huber_core` 使用相同容量与 core 特征，`objective=huber`、`alpha=0.9`。
- Huber 只检查极端赢家对 L2 的影响，不能替代主模型取得 validation 资格。

### 4.3 线性与分类对照

- `ridge_core`：`StandardScaler + Ridge(alpha=1.0)`，直接预测 raw net return。
- `logistic_ev_core`：沿用 P1 `StandardScaler + LogisticRegression(C=1.0, L2, lbfgs, max_iter=2000)` 预测 `P(net_return>0)`；再用该训练集内平均正收益与平均非正收益换算：

```text
predicted_ev =
  P(win) * mean(train positive net_return)
  + (1 - P(win)) * mean(train nonpositive net_return)
```

- 线性与分类对照都不能替代 `lgbm_l2_core` 取得 validation 资格。

## 5. Nested walk-forward 与 edge 阈值

- 外层和 inner 的时间切分、purge 规则沿用 P1：外层 `40%` 初始训练 + 四个顺序测试块；每个外层训练集内 `50%` 初始训练 + 三个 inner 测试块。
- edge 阈值固定为 `0 / 0.25% / 0.50% / 1.00%`，对应 `0.0000 / 0.0025 / 0.0050 / 0.0100`。
- 只有 `predicted_net_return > edge_threshold` 才入场；等于阈值不入场。
- 一个 edge 阈值只有在每个 inner fold 都至少产生 `5` 笔、三折合计至少 `15` 笔时才有资格参与排序。
- inner 排序先最大化三折最差复合净收益；并列时选择更低 edge，再选择更多交易。
- 若某个外层训练集不存在合格 edge，该外层模型必须输出 no-selection failure，不得临时降低覆盖要求。
- 完整 development 上按同一 inner 规则冻结未来 validation 的单一 edge；若无合格 edge，则 P2 自动失败。

## 6. Development 经济门禁

主模型路线必须继续满足 P1 的全部经济门禁：

1. 外层 OOS 关闭交易数 `>=30`；
2. 成本后复合净收益 `>0`；
3. Profit Factor `>=1.20`；
4. 日频 mark-to-market MDD 不差于相同方向 all-cross 基线；
5. 四个外层 fold 中至少三个净收益优于对应 all-cross 基线。

路线优先级不变：

- combined 通过则冻结 combined；
- combined 失败时允许 long-only 或 short-only 使用同一折 edge 独立评估；
- 单边选择规则沿用 P1，失效侧必须在 validation 前禁用。

## 7. Development 排序门禁

经济门禁之外，冻结路线还必须同时满足：

1. 全部外层 OOS 的 `Spearman(predicted_net_return, realized_net_return) > 0.10`；
2. 至少三个外层 fold 中，预测收益最高五分位的实际平均净收益高于该 fold 全部候选的实际平均净收益。

Spearman 为 NaN、等于 `0.10` 或 top-quintile 稳定折少于三个都算失败。排序门禁只对 `lgbm_l2_core` 和最终冻结路线计算。

## 8. Validation 预注册门禁

P2 不改变 P1 已冻结的 validation 经济门禁：

1. 关闭交易数 `>=10`；
2. 成本后净收益 `>0`；
3. Profit Factor `>=1.10`；
4. 收益高于同期同方向 all-cross 基线；
5. MDD 不差于同期同方向 all-cross 基线。

P2 的 development 排序门禁用于防止无排序能力的模型取得揭示资格；不在仅一年、最少十笔的 validation 上新增事后 Spearman 阈值。

## 9. 必须交付

- 每个模型/消融的四折 OOS RMSE、MAE、Spearman、edge 分布和交易指标；
- `lgbm_l2_core` combined/long/short 的经济门禁与排序门禁；
- 每折 inner edge 覆盖资格，明确显示被 `5/15` floor 拒绝的 edge；
- raw L2、Huber、ATR 目标、Ridge、Logistic-EV 对照；
- 回归 SHAP、预测收益五分位、典型高预测赢家与高预测输家；
- P1/P2 事件一致性 hash；
- 若通过才生成候选交易路径 HTML；失败则只保留诊断和 validation 封存证据。
