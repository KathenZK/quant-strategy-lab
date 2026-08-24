# BIN-1D-MA7-TFML P0E/P1E Fresh-Universe Expansion 合同

## 1. 修订原因与不可变边界

- Family：`Binance-1D-MA7-Taker-Flow-Meta-Label`
- Alias：`BIN-1D-MA7-TFML`
- 状态：`explore / diagnostic-only / not promoted / not live-ready`
- 前序证据：[五资产 P1 失败诊断](../diagnostics/binance-1d-ma7-tfml-p1-development-2026-08-10.md)

五资产 P1 的 Full 经济性、收益排序、stress 与 4/5 资产为正，但只在 `7/20` folds 为正、bootstrap `75.80%`、相对 control 增量 `60.88%`；TRX 显著反向。禁止按 outer 结果删除 TRX、只留 BTC/ETH/BNB/SOL 或直接声称 HYPE 类似某个盈利资产。

本合同在读取八个扩展资产 maturity outcome、生成扩展 flow features 或训练扩展模型前冻结。它只检验一个问题：**增加完全未见的资产多样性后，原封不动的 taker-flow expected-utility 机制能否在 fresh held assets 上稳定泛化。**

不变项：

- V6-style raw cross、maturity、entry、exit、费用、`8bps/fill` 主滑点、funding、`0.25x`；
- continuous target `z_8bps`；
- 47 price + 23 flow features 的定义；
- `StandardScaler + Ridge`、alpha/threshold/route grid；
- nested expanding-time、purge/embargo、inner eligibility/ranking；
- full/control/flow-only 三路线和 common-OOF delta；
- HYPE 全锁。

## 2. Universe 与 Fresh Holdout

Legacy training assets：

```text
BTC / ETH / BNB / SOL / TRX
```

Fresh evaluation assets：

```text
XRP / DOGE / ADA / LINK / LTC / DOT / AVAX / UNI
```

八个 fresh assets 在 outcome 未读取时，按以下 source-only 条件一次性固定：

1. Binance USD-M USDT perpetual；
2. canonical monthly native `5m` kline 最晚从 `2020-09` 开始；
3. 连续列包至 `2025-05`；
4. source listing 共 `491` 个 ZIP、`169,255,752 bytes（161.42 MiB）`；
5. 不含 HYPE，不按后续 event 数、收益、相关性或模型结果删资产。

全量 listing 中共有 77 个 symbol 满足长历史条件；本轮不是宣称八个资产覆盖全集，而是在 outcome 未读时冻结的计算预算 basket：XRP/DOGE/ADA/LINK/LTC 提供长期高流动性支付、PoW 与 oracle 暴露，DOT/AVAX/UNI 增加 2020 年上线的 L1/DeFi 异质性。这个人为 basket 是研究限制，必须报告；P1E 后不得用结果从其余 69 个 eligible symbols 补挑赢家。

P1E 的 outer held assets **只允许八个 fresh assets**。五个 legacy assets 可以进入训练，但它们的既有或重算 OOF 不计入 P1E gate。每个 fresh fold 的训练可使用其余 12 个资产，held asset 的任何 row 均不得进入 train/inner。

## 3. 数据、重算与身份

- Cutoff：所有 source/event 严格 `<2025-05-31T00:00:00Z`。
- Price：Binance direct USD-M `1h` OHLCV，并聚合完整 UTC `1d`。
- Funding：Binance funding history；mark 使用 endpoint mark 或同小时 mark-price kline open，沿用 shared kernel 口径。
- Flow：Binance Vision USD-M monthly native `5m` klines。
- 每个 ZIP/响应与 feature 均保留 source identity、质量报告与 SHA256。
- HYPE requests/files/rows/features/train/evaluation：全部为零。

为避免把五资产市场横截面特征与十三资产特征混用，13 个资产的 maturity events 必须从 source 重新构建：

- root/maturity/outcome/local price features 不变；
- price market features 改为 leave-target-out 的同期可用 peers；
- flow market features同样 leave-target-out；
- 不允许把旧五资产 panel 与新八资产 panel 简单拼接；
- 新 panel 产生独立 event identity，不能冒充 LMML 原 `1,448` identity。

## 4. Flow Event Admission

每个 local/peer 继续要求 `entry_ts-5m` 结尾的连续 `4,320` 根 causal bars，禁止插值、nearest、round、API 补洞或 missingness feature。

- target local 不合格即删除；
- 13-asset panel 的 flow market aggregate 至少要求 `8/12` peers 合格；
- 任何 market value 只由 target 之外 peers 计算；
- source gap 原样记录，gapful cache 不是 accepted evidence。

## 5. P0E 容量门

Fresh assets 必须全部满足：

1. raw maturity events 合计 `>=1,600`；
2. 每个 fresh asset raw events `>=180`；
3. flow-accepted fresh events合计 `>=1,500`；
4. 每个 fresh asset accepted `>=170`；
5. fresh usable rate `>=90%`；
6. fresh long/short 各 `>=650`；
7. accepted local 4,320 bars 完整且 peers `>=8`；
8. source identity/schema/field constraints 通过；
9. HYPE `0/0/0`。

任一失败即停止 P1E。Legacy rows 不可补足 fresh 容量门。

## 6. Frozen Features、Model 与 Policy

完全沿用 [原 P0/P1 合同](binance-1d-ma7-tfml-p0-p1-contract-2026-08-10.md)：

- `price_utility_control`：47 price features；
- `flow_only`：`is_short + maturity_age_days + 23` flow features；
- `price_plus_flow`：70 features；
- target：`z_8bps`；
- alpha：`{1,10,100,300,1000}`；
- threshold：`{0,0.0005,0.0010,0.0015}`；
- route：`combined / long_only / short_only`；
- permutation：20 repeats。

禁止新增 asset id、one-hot、asset-specific intercept、按资产 alpha/threshold、树模型或新 flow feature。扩展的目的就是检验原机制，不是借新数据重开搜索空间。

## 7. Nested Fresh-Asset OOF

- Outer：八个 fresh held assets × 后 60% 时间四块，共 `32` folds。
- Train：其余 12 个资产，`exit_ts < test_start-5d`；held asset 全历史排除。
- Test：只含 held fresh asset 的对应时间块。
- Inner：outer train 内 `50% initial + 3 expanding blocks`，同样 purge。
- Inner eligibility/ranking 与原合同逐字同口径。
- `NO_SELECTION` 保持为零 utility，不得按 outer outcome 补选。
- 三条模型路线共享相同 accepted panel、folds、target。

## 8. P1E Hard Gate

只在八个 fresh assets 的 OOF 上计算：

1. P0E 通过；
2. Full selected `>=160`，每个 fresh asset `>=15`，覆盖至少 `24` 个 asset×90d blocks；combined 被选择时 long/short 各 `>=50`；
3. `z_8bps` mean `>0`、PF `>=1.15`；
4. 至少 `6/8` fresh assets mean 正；
5. 至少 `24/32` outer folds mean 正；
6. predicted utility / `z_8bps` Spearman `>0.03`，至少 `6/8` fresh assets为正；
7. fresh `asset×90d` bootstrap `P(mean>0)>=0.90`；
8. common fresh OOF、未选 utility=0 的 full-control `P(Δutility>0)>=0.90`；
9. 至少两个 flow features 在 `>=24` fresh folds 的 permutation median `>0`；
10. `z_4bps`、funding-off、lag1 mean `>0`、PF `>=1.05`，lag 可执行率 `>=75%`；
11. 至少 `5/8` fresh assets 相对 all-matured OOF 同时提高 compound 并降低 MDD，每资产 selected `>=15`。

近 `1d/7d/1m/3m/6m/1y`、choice frequency、threshold `±0.0005`、资产/方向/fold/90d block 强制报告但不参与选择。

## 9. 后续边界

- P0E/P1E 失败：保持 `HARD-GATE-FAILED`，不保存模型、不运行 P2、不读取 HYPE；同一 target/model 的 outcome-driven universe/threshold 修补停止。
- P1E 通过：只允许先冻结 13 资产 post-cutoff P2 合同；P2 通过前 HYPE 仍锁定。
- 即使 P2 通过，HYPE 也只能在另立 exposed-target transfer 合同并冻结模型后读取；任何 transfer 失败不能反向修改本合同。
