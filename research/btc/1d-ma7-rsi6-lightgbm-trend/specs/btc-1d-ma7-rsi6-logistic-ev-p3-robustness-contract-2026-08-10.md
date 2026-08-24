# BTC-1D-MA7-RSI6 Logistic-EV P3 稳健性合同

## 1. 身份与权限

- Family：`BTC-1D-MA7-RSI6-LightGBM-Trend`
- 阶段：P3 `development-only` Logistic-EV 稳健性确认；`explore / diagnostic-only / not promoted / not live-ready`
- P3 来源：P2 的预注册 `logistic_ev_core` 对照产生后续线索；P3 不改写 P2 主模型失败结论。
- 冻结 validation `2025-08-07` 至 `2026-08-06 UTC` 继续禁止读取、预测或画图。
- P3 即使通过也不自动揭示 validation；必须先汇报，再由用户单独明确批准一次性揭示。

## 2. 不变项与事件一致性

P3 完整继承 [P1 development 合同](btc-1d-ma7-rsi6-lgbm-p1-development-contract-2026-08-07.md)的事件、特征、交易时序、RSI6/MA7/stop 退出、`1×` 仓位、手续费、滑点和 funding。

- 事件数必须为 `449`。
- Event identity SHA256 必须为 `941246a90a2fe403b6de152e1527bb4ed1890ee84fdb32095b3a2eb87a3fd529`。
- P3 不增加、删除或重选特征；使用固定 `MA+K+RSI` core 20 特征。
- P3 不改变正标签：成本后 `net_return > 0`。
- P3 不改变四个外层 walk-forward 的 `40% + 4 blocks` 和 purge 规则。

## 3. Logistic-EV 模型

每个外层 fold 只用该 fold 过去事件拟合：

```text
StandardScaler
LogisticRegression(
  C=1.0,
  penalty=L2,
  solver=lbfgs,
  max_iter=2000,
  class_weight=None,
  random_state=20260807
)
```

训练集内计算：

```text
mean_win  = mean(net_return where net_return > 0)
mean_loss = mean(net_return where net_return <= 0)

predicted_ev =
  P(win) * mean_win
  + (1 - P(win)) * mean_loss
```

- `mean_win/mean_loss` 每折只使用该折训练集，不使用 test 或未来事件。
- 不做概率校准、class weighting、模型容量搜索、特征选择或系数筛选。

## 4. 固定 edge 与压力线

主交易规则固定为：

```text
take = predicted_ev > 0.0100
```

- 等于 `1.00%` 不入场。
- P3 不再运行 nested edge 搜索。
- `0.50%` 与 `1.50%` 只作对称压力线，不能替换主 `1.00%` edge。
- combined、long-only、short-only 都使用同一固定 edge。

## 5. 主经济与排序门禁

冻结路线必须满足：

1. 外层 OOS 交易数 `>=30`；
2. 成本后复合净收益 `>0`；
3. PF `>=1.20`；
4. 日频 mark-to-market MDD 不差于同方向 all-cross 基线；
5. 至少 `3/4` 折净收益优于对应 all-cross 基线；
6. `Spearman(predicted_ev, realized net_return) > 0.10`；
7. 至少 `3/4` 折中，预测 EV 最高五分位的实际平均净收益高于该折全体。

路线优先级沿用 P1/P2：combined 优先；combined 未通过时才允许 long-only 或 short-only 独立评估。

## 6. P3 新增稳健性门禁

### 6.1 绝对折收益

- 主 `1.00%` edge 至少 `3/4` 个外层 fold 的绝对复合净收益严格 `>0`。
- “优于亏损基线但自身仍亏损”不能满足本项。

### 6.2 Edge 压力

冻结路线分别应用 `0.50%` 与 `1.50%` edge；两条压力线都必须：

- OOS 复合净收益 `>0`；
- PF `>=1.10`。

压力线不要求达到主路线交易数门槛，也不用于选择方向。

### 6.3 分层交易 bootstrap

- 使用主 `1.00%` edge 的外层 OOS 已选交易；
- 按外层 fold 分层，在每折内有放回抽取与该折原交易数相同的交易；
- 合并四折抽样交易，按 `prod(1 + net_return) - 1` 计算 bootstrap 复合收益；
- 固定 seed `20260810`，重复 `10,000` 次；
- `P(bootstrap compounded return > 0) >= 95%` 才通过；
- 同时报告 `2.5% / 50% / 97.5%` 分位数。

bootstrap 只评估交易收益不确定性，不重排历史路径、不替代真实 MDD。

## 7. 路线冻结与 validation

- combined 只有在第 5–6 节全部通过时才取得 P3 candidate 身份。
- combined 失败后，单边路线按相同全部门禁独立评估。
- 多个单边通过时，优先 bootstrap 正收益概率更高者；并列时选择最差外层 fold 收益更高者。
- P3 通过后完整 development 模型仍固定 `1.00%` edge。
- P3 通过只产生 `candidate / validation eligible`，不授权揭示 validation。
- 用户单独批准后，未来 validation 仍沿用 P1/P2 的五项门禁：`>=10` 笔、净正、PF `>=1.10`、收益优于基线、MDD 不差于基线；不得根据 validation 改模型或 edge。

## 8. 必须交付

- P2/P3 OOS Logistic-EV prediction identity 一致性；
- 主 `1.00%` edge 的 combined/long/short 四折及总指标；
- `0.50% / 1.50%` 压力线；
- `10,000` 次分层 bootstrap；
- scaler、Logistic 系数、intercept、训练集 mean win/loss 和模型 hash；
- 系数跨折符号与幅度稳定性、预测 EV 五分位、典型高 EV 赢家/输家；
- P3 通过时生成完整 self-contained 交易路径 HTML；失败时不生成候选图；
- validation 必须保持 `not revealed`，直到用户另行明确批准。
