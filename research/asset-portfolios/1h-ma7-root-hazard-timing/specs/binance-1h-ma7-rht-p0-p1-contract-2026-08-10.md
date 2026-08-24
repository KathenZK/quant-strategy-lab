# BIN-1H-MA7-RHT P0/P1 非 HYPE Root-Hazard 合同

## 1. 目标与边界

- Family：`Binance-1H-MA7-Root-Hazard-Timing`
- Alias：`BIN-1H-MA7-RHT`
- 状态：`explore / diagnostic-only / not promoted / not live-ready`
- 问题：daily soft MA7 cross 建立方向 prior 后，逐小时可见路径能否在成本后选择比立即入场更好的唯一时点，并跨资产、跨时间迁移。
- 本合同冻结数据、root、候选行、标签、特征、权重、模型、CV、first-hit 与硬门；结果后不得降门或挑资产挽救。

本研究不是 LMML P2，不使用旧 maturity buffer/slope、CTLS、HYPE label、事后最优小时、asset id 或动态加减仓。

## 2. 数据与 HYPE 硬锁

- Universe：`BTCUSDT / ETHUSDT / BNBUSDT / SOLUSDT / TRXUSDT`。
- 输入：已审计 Binance FAPI direct `1h`、恰有 24 根小时 K 的 UTC `1d`、官方 funding/mark。
- 数据边界：所有输入 `ts < 2025-05-31T00:00:00Z`。
- 建模 root 要求 `cross_ts < 2025-05-20T00:00:00Z`，保证最长候选、持有与 `+6h` 延迟结果在边界内。
- 代码只允许打开固定 15 个五资产文件；basename 含 `hype` 或 symbol 不在白名单时，必须在读取、散列前失败。
- 输出必须声明 `hype_rows_consumed=0`、`hype_files_opened=0`。
- 本合同没有 HYPE 解锁阶段；即使通过，也须另立 transfer 合同。

P0 先复现完整边界内的 raw-cross inventory，并分开报告 root cutoff 后的 eligible roots；不能把两者混写。

## 3. Root 与逐小时候选

日线 row `D` 表示 `[D,D+1d)`，其收盘在 `D+1d 00:00 UTC` 可见：

```text
long : close[D-1] <= SMA7[D-1] and close[D] > SMA7[D]
short: close[D-1] >= SMA7[D-1] and close[D] < SMA7[D]
```

- `side=+1/-1`，`root_start = D+1d`。
- 不使用 maturity；每个 raw cross 只建立一个 root。
- 候选 `decision_ts = root_start + k hours`，`k=0..119`。
- 特征只使用 `ts < decision_ts` 的闭合小时 K 与当时已闭合日线；在 `decision_ts` 对应小时 open 成交。
- 每个 UTC 日边界先处理刚闭合日线：若 `side*(close-SMA7)<=0`，旧 root 结束，不生成该边界候选；同一边界的新反向 root 可生成 `k=0`。
- root admissions 在首次日线 recross 或 `root_start+120h` 结束，取较早者。
- 缺 K、重复 K、非闭合 K、`ATR7<=0`、日线/小时重建不一致均 fail closed，不插值。

## 4. Landmark 标签与执行

每个候选都独立回答“若现在入场，结果如何”；即使某个早期候选事后赚钱，后续候选行仍保留，禁止标签依赖删行。

```text
entry_reference = hourly_open[decision_ts]
entry_fill      = entry_reference * (1 + side * slippage)
```

退出取较早者：

1. entry 后首个完整 UTC 日收盘满足 `side*(close-SMA7)<=0`，在该日结束边界的小时 open 退出；
2. `entry_ts+120h` timeout。

实际 funding 使用事件时间，严格满足 `entry_ts < funding.ts < exit_ts`。固定 `0.25x`，fee `0.001/fill`：

```text
z = 0.25 * (
  side * (exit_fill-entry_fill)/entry_fill
  + Σ(-side * funding_rate * mark_price / entry_fill)
  - entry_fee
  - exit_fee * exit_fill/entry_fill
)
label = 1[z_8bps > 0]
```

主列与预生成压力：

- `z_8bps` 主标签；
- `z_4bps` 仓库默认成本对照；
- `z_12bps` 更严成本；
- `z_funding_off`：`8 bps`、funding 置零；
- `z_lag1h / z_lag6h`：不重新评分，entry 延迟；若 root 已 recross 或缺完整结果则不可执行。

`root_information_end` 是该 root 所有主/压力标签需要的最晚 timestamp。

## 5. 冻结特征

所有价格差除以 cross 日冻结 `ATR7`；禁止结果后增删：

1. `is_short`
2. `age_frac = k/120`
3. `cross_distance_atr`
4. `cross_slope_1_atr`
5. `cross_slope_2_atr`
6. `aligned_root_displacement_atr`
7. `aligned_return_1h_atr`
8. `aligned_return_6h_atr`
9. `aligned_return_24h_atr`
10. `signed_efficiency_6h`
11. `signed_efficiency_24h`
12. `giveback_from_root_mfe_atr`
13. `root_mae_atr`
14. `realized_vol_24h_atr`
15. `aligned_funding_carry_24h`

效率分母为对应闭合小时路径绝对变动之和，零分母取零。MFE/MAE 只用 root start 至 decision 前已闭合 high/low；funding context 只用 `funding.ts < decision_ts`。

静态 control 只使用前五项，采用同一 CV 与 first-hit 选择。

## 6. Root 权重、模型与 first-hit

若 root `r` 有 `n_r` 行：

```text
row_weight = 1 / n_r
sum(row_weight within root) = 1
```

该权重同时传给 `StandardScaler` 与 Logistic；禁止 `class_weight` 和额外 asset-balanced weight。

主模型与 control 均固定：

```text
StandardScaler
L2 LogisticRegression(
  C in {0.03, 0.10, 0.30, 1.00},
  solver="lbfgs",
  max_iter=3000,
  random_state=20260810
)
threshold in {0.50, 0.55, 0.60, 0.65}
route = combined
```

OOF/live first-hit：按每个 root 的 `decision_ts` 排序，选择首个 `probability >= threshold` 的候选；命中后该 root 不再入场。不得按资产或方向另选 threshold。

## 7. 防泄漏与 nested LOAO/time

- 切分单位是完整 `root_id`，禁止同一 root 跨 train/test。
- 全局按 unique `root_start`：前 40% 初始历史，后 60% 分四个 outer time blocks；再与五个 held-out asset 组成 20 折。
- test：仅 held asset 当前 block 的完整 roots。
- train：仅其他四资产，且 `root_information_end < test_start-120h`。
- held asset 不进入 train、scaler、threshold 或缺失处理。
- inner：outer train 内 `50% initial + 3 expanding blocks`，相同 root grouping、purge 与 embargo。

每个 `C × threshold` 必须在 inner 中：

- 三折各 first-hit `>=15` roots，合计 `>=60`；
- long/short 各 `>=15`；
- 三折 `mean z_8bps > 0`；
- 合并 PF `>=1.05`。

合格组合按最差折 mean、合并 mean、PF、更高 threshold、更小 C 排序。无合格组合时 outer fold 为 `NO_SELECTION`，不得降门。

## 8. Development 硬门

全部满足才可保存 frozen model：

1. eligible roots `>=1,800`，每资产 `>=300`；
2. OOF first-hit roots `>=150`，每资产 `>=20`，long/short 各 `>=50`；
3. 覆盖至少 12 个绝对 UTC 90 日 block；
4. 聚合 `z_8bps` mean `>0`、PF `>=1.15`；
5. 至少 `4/5` held assets mean 为正；
6. 至少 `15/20` outer folds mean 为正，无交易折计失败；
7. 对每个至少 12 行且非恒定的 OOF root 计算 `Spearman(p,z_8bps)`：root 中位数 `>0.05`，且至少 `4/5` 资产的中位数为正；
8. `asset × 90d` cluster bootstrap 10,000 次，`P(mean z_8bps>0)>=0.90`；
9. 与同 root `k=0` 立即入场配对：`Δmean>0` 且 cluster bootstrap `P(Δmean>0)>=0.90`；
10. 至少 `3/5` 资产相对立即入场同时提高累计事件收益并降低事件序列 MDD；
11. full 相对静态 control：按所有 OOF roots、未交易 utility=0，cluster bootstrap `P(Δutility>0)>=0.90`。

## 9. 压力门与审计

- `z_4bps` 报告；
- `z_12bps` 与 funding-off：mean `>0`、PF `>=1.05`；
- `lag1h`：可执行率 `>=90%`、全选中 root mean `>0`、可执行样本 PF `>=1.05`；
- `lag6h`、`threshold±0.05` 强制报告但不单独阻断；
- 每项按总计、资产、方向、outer fold、90 日 block 报告；
- recent `1d/7d/1m/3m/6m/1y` 锚定 development end，只作审计、不参与选择。

## 10. 失败后的固定转向

任一硬门失败即关闭“跨资产共享 daily MA7 raw-cross prior”，不再添加树、asset id、方向 route、threshold、窗口或 maturity 变体。

下一机制必须同时更换 root 来源与目标：原生 `1h` volatility-normalized impulse/breakout 建 root，明确 pullback/reclaim 入场，固定 bracket/timeout；先做透明 rule-based 跨资产验证。BNB/SOL 若局部为正只能记作 asset-specific observation，不能作为 HYPE 迁移。

## 11. 证据要求

- root inventory/data-quality JSON；
- root table、person-period panel；
- main/control OOF row scores与 first-hit decisions；
- inner/outer 选择、gate、bootstrap、压力与 recent slices；
- 通过时的 frozen model，否则明确无模型；
- manifest、SHA256、中文 diagnostic、decision log 与索引更新。
