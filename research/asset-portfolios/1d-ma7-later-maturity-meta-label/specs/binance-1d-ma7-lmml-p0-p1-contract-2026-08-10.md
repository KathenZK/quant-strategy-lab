# BIN-1D-MA7-LMML P0/P1 数据与模型合同

## 1. 目标与状态

- Family：`Binance-1D-MA7-Later-Maturity-Meta-Label`
- Alias：`BIN-1D-MA7-LMML`
- 当前阶段：`explore / diagnostic-only / not promoted / not live-ready`
- 研究问题：能否只用决策时已知信息，跨资产识别 soft MA7 cross 后成熟的 probe 中哪些在成本后具有正经济价值，并把固定模型迁移为 HYPE V6 的 state-isolated overlay filter。
- 本合同冻结 P0 数据与事件构造、P1 非 HYPE 模型选择和解锁门；运行结果出来后不得修改合同阈值来挽救失败。

本研究不是：

- `HYPE-1D-MA7-ABT-V7`；
- 已失败 `BIN-1D-MA7-RSI6-DAPML` 的同标签微调；
- 使用 CTLS、稳定趋势段、未来极值或 `trend_hit` 的监督学习；
- promotion、runner handoff 或 live-ready 证明。

## 2. 信息隔离

### 2.1 Development

- 训练资产：`BTCUSDT / ETHUSDT / BNBUSDT / SOLUSDT / TRXUSDT`。
- 数据上限：`ts < 2025-05-31T00:00:00Z`，早于 HYPE 完整日线历史起点。
- 输入：已审计 direct `1h`、恰有 24 根小时 K 的 UTC `1d` 聚合、官方 funding 与 mark。
- 任一输入文件、事件表与代码均记录 SHA256。
- 不读取 DAPML 共同 sealed year，不以 `2025-05-31` 后其他资产市场状态侧漏 HYPE 窗口。

### 2.2 HYPE 锁

- P0/P1 development 进程不得 import、读取或散列 HYPE 数据、V6 trade label、CTLS label 或 missed-reference episode。
- 只有 `development_gate_pass=true` 且冻结模型产物已写入后，独立命令才可加载 HYPE。
- HYPE 432 日已被研究者暴露；后续结果只能称 `exposed-target transfer diagnostic`，不能称 clean OOS。
- 若 P1 失败，不生成 HYPE score、候选排程或组合指标。

## 3. Root 与成熟语义

指标：

- `SMA7`：收盘价简单七日均线；
- `ATR7`：true range 的简单七日均值；
- long `side=+1`，short `side=-1`。

soft raw cross：

```text
long:  close[t-1] <= SMA7[t-1] and close[t] > SMA7[t]
short: close[t-1] >= SMA7[t-1] and close[t] < SMA7[t]
```

从 cross 日到 `cross+5` 日闭合后逐日检查，若先回到 MA7 另一侧则 root 取消。第一根同时满足下列条件的日 K 为 maturity：

```text
distance_atr = side * (close[t] - SMA7[t]) / ATR7[t]
slope_atr    = side * (SMA7[t] - SMA7[t-lookback]) / ATR7[t]

long : distance_atr > 0.00 and slope_atr >= 0.02, lookback=1
short: distance_atr > 0.10 and slope_atr >= 0.02, lookback=2
```

- 等号语义必须与上式一致：buffer 严格 `>`，slope 为 `>=`。
- 同一 root 只保留首次 maturity。
- 所有 maturity 均进入 P0 标签容量；`maturity_age_days=0` 与 later maturity 分层报告。
- 若同一资产同一 entry 时点出现多 root，先按 cross 时间、再按 long-before-short 固定排序。

## 4. Probe 标签与压力结果

### 4.1 主标签

- maturity 日收盘决策，下一完整 UTC 日开盘成交。
- 固定 leverage `0.25x`；非 HYPE 标签不模拟任何移植 core，不共享状态或资本。
- 自 entry 起，首次闭合日收盘回到 MA7 另一侧时，于下一日开盘退出；否则最多持有五日并在对应开盘退出。
- 每 fill fee `0.001`，每 fill adverse slippage `8 bps`，计入实际 funding。
- `z_8bps` 为 probe 对 entry equity 的直接净收益；`label = 1[z_8bps > 0]`。
- purge 使用真实 exit timestamp，并额外 embargo 五日。

### 4.2 同步压力列

同一候选必须预先生成：

- `z_4bps`：每 fill `4 bps`；
- `z_8bps`：主标签；
- `z_funding_off`：`8 bps`、funding 置零；
- `z_lag1`：在 maturity 后再延迟一日，入场前仍位于 root 同侧，否则记为不可交易；退出规则重新从延迟 entry 计算。

P1 不得根据压力结果修改标签或特征。

## 5. 因果特征

所有特征在 maturity 日完整收盘后计算；禁止 asset id、绝对价格、绝对成交量、未来统计量和全样本 normalization。

### 5.1 Root / 日线

- `is_short`、`maturity_age_days`；
- maturity 的 aligned `distance_atr`、`slope_atr`；
- cross 日的 aligned distance/slope、maturity 相对 cross 的 distance/slope 改变量；
- aligned `1d/3d/5d/10d` 收益除以当前 `ATR7`；
- `ER5/ER7/ER14`，其中位移按 side 对齐、路径长度保持非负；
- `ATR7/close`、`ATR7/ATR20`；
- direction-aligned body、range、candidate/opposition wick、close location；
- Wilder `RSI6`、一日变化、五日方向极值；
- `volume`、`quote_volume`、`trade_count` 相对各自过去 20 日中位数的比值。

### 5.2 已闭合小时路径

只使用 maturity 日结束前已经闭合的 direct `1h`：

- aligned `6h/24h/72h` 位移除以 maturity `ATR7`；
- `24h/72h` directional-hour fraction；
- `24h/72h` signed efficiency ratio；
- 最近 `24h` 上行/下行 realized variance ratio 按候选方向对齐；
- 最近 `24h` 收盘在 high-low 区间的位置；
- 最近 `6h` 相对前 `18h` 的 aligned impulse 差。

### 5.3 Funding 与市场状态

- 过去 `24h/72h` side-aligned funding carry，正值表示对候选方向有利；
- 排除当前资产后的五资产横截面 median `1d/3d` 收益、median `ATR7/close` 与上涨 breadth；
- candidate side 与市场 median 对齐后的 `1d/3d` 状态；
- 当前资产 aligned return 减去市场 aligned median 的相对强弱。

所有 rolling、median、scaler 与缺失值处理只允许使用当时及以前数据。

## 6. 冻结模型族

### 6.1 主模型

- 模型：`StandardScaler + L2 LogisticRegression`；
- asset-balanced sample weight；
- 特征集：第 5 节全部字段；
- `C` 网格：`0.03 / 0.10 / 0.30 / 1.00`；
- probability threshold 网格：`0.50 / 0.55 / 0.60 / 0.65 / 0.70`；
- route：`combined / long_only / short_only`，route 也只能在 inner folds 选择。

### 6.2 选择规则

- 外层：五资产 `leave-one-asset-out × 4 expanding-time folds`；
- 外层 train 必须满足 `signal_ts < test_start`、`exit_ts < test_start-5d`；
- 内层：外层 train 内 `3` 个 expanding-time folds；
- 每个 `C × threshold × route` 先满足每 inner fold 至少 `8` 笔、总计至少 `40` 笔；
- 排序依次为：最差 inner fold 的 `z_8bps` 均值、整体均值、PF、更高 threshold、更小 `C`；
- 并列固定取上述顺序，不允许人工挑选。

LightGBM 只允许作为诊断，参数必须在脚本中固定；无论结果如何都不能替代 Logistic 主模型或触发 HYPE 解锁。

## 7. 非 HYPE development 解锁门

下列条件必须全部满足：

1. OOF accepted probes `>=100`，每个 held-out asset `>=12`；
2. 若 route 为 combined，则 long/short 各 `>=30`；单方向 route 只报告对应方向；
3. 覆盖至少 `15` 个互不重叠的 90 日 entry block；
4. 聚合 `z_8bps` 均值 `>0`、PF `>=1.15`；
5. 至少 `4/5` held-out assets 的 `z_8bps` 均值为正；
6. 至少 `15/20` outer folds 的 `z_8bps` 均值为正；
7. OOF probability 与 `z_8bps` 的 Spearman `>0.05`；
8. 以 `asset × 90d block` 为 cluster 的 bootstrap `P(mean z_8bps > 0) >= 0.90`；
9. `z_4bps`、`z_funding_off`、可交易的 `z_lag1` 均值均 `>0` 且 PF `>=1.05`；
10. 相对 all-matured baseline，至少 `3/5` 资产同时提高累计事件收益并降低事件序列 MDD。

任一失败：

- `development_gate_pass=false`；
- HYPE 保持锁定；
- 不可在结果后更换 threshold、route、特征子集或主模型；
- 下一条允许的路线是 materially new 的 `1h` root-level hazard timing，不是继续扩大树容量。

## 8. 模型锁与 HYPE 后续门

P1 通过后，使用全部非 HYPE development 重新拟合；`C/threshold/route` 取外层选择的众数，并列取更高 threshold、更小 `C`、`combined > long_only > short_only`。冻结：

- 数据文件 SHA；
- 事件 identity SHA；
- 特征顺序；
- scaler mean/scale；
- Logistic coefficients/intercept；
- `C/threshold/route`；
- 代码 SHA 与模型状态 SHA。

独立 HYPE transfer 合同必须在加载 HYPE 前补充并冻结。最低要求：

- exact V6 core schedule hash 不变；
- 模型只作为 maturity filter，V6 core 绝对优先；
- reference labels 删除、打乱或翻转后 accepted schedule hash 不变；
- 同时输出共享权益、冻结 core notional 与 probe-only 分解；
- base：`Δreturn >= +5pp` 且 `ΔMDD <= -0.25pp`；
- 8bps/funding-off/lag1：收益增量均正，MDD 分别不恶化超过合同上限；
- 删除最大赢家和逐 root leave-one-out 后仍为正；
- accepted `>=8` 且覆盖至少五个 54 日 block。

即使通过，也不登记 HYPE V7，不提升 V6，不生成 live spec。

## 9. 必须保留的证据

- P0 data/feature/label capacity JSON；
- development event parquet 与 identity SHA；
- 所有 OOF prediction parquet；
- inner/outer fold 选择记录；
- gate summary、bootstrap、per-asset/per-direction/per-time-block 指标；
- frozen model JSON（仅在通过时）；
- 脚本与每个 JSON/parquet 的 SHA256；
- 中文 diagnostic 与 decision-log 结论。
