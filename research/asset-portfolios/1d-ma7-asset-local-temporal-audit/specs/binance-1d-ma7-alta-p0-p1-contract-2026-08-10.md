# BIN-1D-MA7-ALTA P0/P1 未见时间窗合同

## 1. 目标与冻结边界

- Family：`Binance-1D-MA7-Asset-Local-Temporal-Audit`
- Alias：`BIN-1D-MA7-ALTA`
- 状态：`explore / diagnostic-only / not promoted / not live-ready`
- 研究问题：在关闭 pooled historical maturity-selection 后，同一可执行 maturity event substrate 在全新 post-cutoff 时间窗上是否仍有无条件经济性；若有，一个不搜参的 asset-local policy 是否优于 `take_all`。
- 本合同在读取 `2025-05-31` 后 event outcome 前冻结。

禁止：

1. HYPE requests/files/rows/features/train/evaluation；
2. 第三组历史资产 holdout；
3. cross-asset pooled 模型、inner grid、揭示后改 policy；
4. 使用 QUML/TFML outer outcome 选择资产、方向、alpha、quantile 或 threshold；
5. 以 executable-only `z_lag1` 均值过门。

## 2. Universe 与时间窗

固定 21 资产，不新增、不删除：

```text
BTC ETH BNB SOL TRX XRP DOGE ADA LINK LTC DOT AVAX UNI
BCH ETC XLM ATOM VET NEAR AAVE FIL
```

- Train：listing 起至 `T0=2025-05-31T00:00:00Z`，严格以 `exit_ts < T0` 入模。
- Test：`T0 <= signal_ts < T1`。
- `T1=2026-08-01T00:00:00Z` exclusive。
- Purge：train/test 边界前 `5d`；任何 outcome 穿过 `T0` 的事件不入训练。

## 3. 数据与 P0

- Price：Binance 官方 USD-M `1h` OHLCV；完整 UTC `1d` 必须由 24 根精确聚合。
- Funding：官方 funding rate；同小时 mark-price kline open。
- Post-cutoff source：Binance Vision monthly archive；若月包内部小时缺失，只允许用同一官方 daily archive 精确补洞。
- 每个 ZIP 必须核验 listing identity、size、ETag/MD5、CRC、SHA256；不插值、不 forward-fill、不用 trade price 替 mark。
- Pre-`T0` inputs 必须复用已审计 SHA；post-`T0` 与 pre-`T0` 在同一 feature contract 下拼接。
- Event：LMML/V6-style soft MA7 cross、最多五日 asymmetric maturity、下一日 open 入场、日线 MA7 recross 或最多五日退出。
- Features：QUML 的 47 个 price/root/hourly/funding/leave-target-out market features；无 flow/basis/OI、无 asset id。
- Cost：fee `0.001/fill`、主 slippage `8bps/fill`、`0.25x`、实际 funding；保留 `z_4bps`、funding-off、lag1 审计。
- HYPE source/path/name/row 扫描计数必须全部为零。

P0 必须全部满足：

1. 21 资产 post-cutoff `1h` 到 `T1` 无缺口；
2. 完整 UTC `1d` 重建差异为零；
3. funding nominal gap `<=8h`，mark 全部可解；
4. test eligible events 合计 `>=200`；
5. 每资产 test eligible events `>=8`；
6. long/short 各 `>=75`；
7. 47 features 与四种 outcome 可审计；
8. event identity 与 input SHA 冻结；
9. HYPE `0/0/0`。

任一失败即停止 P1。

## 4. 两个且仅两个 Policy

### A. `take_all`

- Test 窗内全部合格 maturity events；
- 不训练、不打分、不筛选；
- 这是 substrate 无条件经济性的第一主门。

### B. `local_q80_ridge1000`

每个资产独立：

1. 只用该资产 `exit_ts < T0-5d` 的 train events；
2. `StandardScaler + Ridge(alpha=1000)`；
3. target=`z_8bps`，features 为冻结 47 项；
4. threshold 为该资产 train predictions 的 `0.80` quantile；
5. route=`combined`；
6. Test prediction `>=threshold` 才选择。

不得增加第三 policy，不得调 `alpha/q/route`，不得 pool 资产。

## 5. P1 Hard Gate

### 5.1 `take_all` 第一主门

必须全部满足：

1. P0 通过；
2. test selected `>=200`，每资产 `>=8`，long/short 各 `>=75`；
3. `z_8bps` mean `>0`、PF `>=1.10`；
4. 至少 `12/21` 资产 mean 正；
5. 至少 `12/21` 资产相对零仓位 compound 正；
6. asset×90d cluster bootstrap `P(mean>0)>=0.90`；
7. `z_4bps`、funding-off mean `>0`、PF `>=1.05`；
8. 最近 `1d/7d/1m/3m/6m/1y` 仅作审计，不参与选择；
9. HYPE lock。

`take_all` 任一硬门失败，即关闭该 maturity substrate 的后窗无条件 edge，Policy B
只能作为失败对照，不能救援。

### 5.2 Asset-local 模型增量门

仅当 `take_all` 全过时才讨论模型价值；B 还必须满足：

1. selected `>=100`，至少 `15` 个资产各 `>=5`；
2. `z_8bps` mean `>0`、PF `>=1.10`；
3. 至少 `12/21` 资产 mean 正；
4. asset×90d bootstrap `P(mean>0)>=0.90`；
5. common test events、未选 utility=`0` 的 `P(u_B-u_A>0)>=0.90`；
6. `z_4bps`、funding-off mean `>0`、PF `>=1.05`。

## 6. `z_lag1` 报告规则

- 必须同时报告 all-selected、lag-executable 与 missing-lag 三组；
- common executable events 上直接比较 `z_lag1-z_8bps`；
- 未执行 lag 的事件在 portfolio utility 比较中按 `0`，不能只删掉它们；
- `z_lag1` 不参与 policy、门槛或结论选择。

## 7. Terminal Rule

- P0 失败：`HARD-GATE-FAILED`，不读 test outcome。
- `take_all` 失败：`HARD-GATE-FAILED`，关闭同一 maturity event 定义上的 selector/threshold/model 搜索。
- A 过、B 不优：保留 substrate 观察结论，关闭 price-only asset-local selector。
- A/B 都过：也不自动读取或解锁 HYPE；只能先冻结独立复制或资本解耦 sleeve 合同。
- outcome 揭示后改时间窗、资产、policy 或门槛，实验作废。
