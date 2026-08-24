# Cross-Sectional Alpha Pipeline Gap Matrix

状态：`已有` / `部分已有` / `缺失` / `需要重构`。优先级：`P0` 阻断首个可信 baseline，`P1` 阻断成本/中性化/ML 完整研究，`P2` 阻断微观结构与 shadow。

| Domain | 状态 | 可复用证据 | 主要缺口 | 最小行动 | Priority |
| --- | --- | --- | --- | --- | --- |
| Data lake identity/layout | 已有 | [`DataLakeLayout`](../../../src/strategy_lab/data/lake.py)、[`DatasetKind`](../../../src/strategy_lab/data/models.py) | 非 OHLCV 数据集的 availability/effective time 不统一 | 增加 `available_ts`/effective interval contract | P0 |
| Trusted OHLCV | 已有 | `load_trusted_ohlcv()`、`audit_ohlcv_frame()`、raw-normalized parity | trusted loader 为单 symbol 调用；全市场 panel audit 未封装 | `load_trusted_panel_ohlcv()` + per-symbol/per-ts summary | P0 |
| Instrument master | 缺失 | `InstrumentId` 与静态 `ASSET_METADATA` schema | listing/delist/status/tick/step/min notional/contract/alias 无有效期 | 新建 versioned PIT instrument snapshot + alias table | P0 |
| Symbol mapping | 缺失 | 家族脚本的字符串转换 | rename、venue alias、contract identity 不可审计 | canonical `instrument_id` + effective mappings | P0 |
| Binance all-market history | 部分已有 | normalized `15m` 约 5,664 万行/791 symbols；funding/mark archives | 全市场 `1h` OHLCV 已清理；月档之后只有少数主力 | 从 `15m` 因果聚合；冻结全市场 data cutoff | P0 |
| Hyperliquid all-market history | 缺失 | 单标的 OHLCV/funding | 无全市场 metadata/OHLCV/funding/depth 历史 | Phase 2 独立同步与质量合同 | P1 |
| PIT universe | 需要重构 | CSLGBM/MHCSML `age/coverage/ADV/TopN`；MCSM 月频 eligibility | family hard-code、manual exclusions、无 manifest API | `UniverseProvider` + membership artifact/reason codes | P0 |
| Retrospective universe boundary | 缺失 | 文档中已有 survivorship 认知 | 无 mode/watermark enforcement | 两种 `universe_mode`，biased mode 强制标记 | P0 |
| Per-symbol feature engine | 已有 | `FactorRegistry`、`multi_asset_1h_registry`、future perturbation tests | feature 数量偏多，部分依赖字段覆盖不稳定 | 冻结 30–80 baseline manifest | P0 |
| Cross-sectional transforms | 部分已有 | 家族 DuckDB `cs_rank_*`、breadth/dispersion | 无 winsor/z-score API；transform fit universe 未记录 | `CrossSectionalTransformer` + breadth/null gates | P0 |
| RelativeStrengthFactor | 需要重构 | [`cross_sectional.py`](../../../src/strategy_lab/data/factors/cross_sectional.py) | `cross_sectional=True` 与整列 `pct_change()` 在 panel 上有 cross-talk 风险 | 分开 time-series relative return 与 per-ts cross-section | P0 |
| Feature store | 需要重构 | version/source hash、identity partitions、manifests | 整段 frame 写到 max-date 分区；无 input dataset hashes/universe/transform chain | panel store + partition manifest + immutable dataset ID | P0 |
| Labels | 需要重构 | MHCSML multi-horizon long/short/tail；公式单测 | 绑定 archived family；缺标准 residual/rank label API | 提炼 `MultiHorizonLabeler` 到 shared kernel | P0 |
| Dataset isolation | 部分已有 | physical development matrix、label/feature manifests | family-specific、无统一 schema/version | `DatasetBuilder` + feature/label physical separation | P0 |
| Purged walk-forward | 需要重构 | nested expanding 7 folds、48h purge、inner validation | hard-coded folds/models/tasks | reusable splitter + overlap audit | P0 |
| Linear models | 部分已有 | Ridge/logistic in family scripts | 无 common adapter；Lasso/ElasticNet 未统一 | sklearn adapter baseline | P0 |
| LightGBM | 部分已有 | regression/classification/ranker/quantile、多 seed | 绑定 scripts，模型 manifest schema 不统一 | common model adapter；baseline 通过后启用 | P1 |
| XGBoost | 缺失 | 无依赖/实现 | 增加依赖会扩搜索面 | Phase 2 按需作为树模型 control | P1 |
| Neural model | 缺失 | 无依赖/实现 | 容易增加 trial 与 leakage 风险 | Phase 2/3 仅小 MLP control | P2 |
| IC/RankIC | 部分已有 | global Spearman、mean RankIC、positive share | 无 ICIR、有效样本修正、统一 artifact | `AlphaDiagnostics` 基础模块 | P0 |
| Quantile/monotonicity/decay | 部分已有 | HYPE 单资产 quintile、MHCSML 多 horizon | 非通用、非严格横截面 | per-ts quantiles + frozen-score decay | P0 |
| Stability/regime/breadth | 部分已有 | family slices、breadth factors、fold summaries | 无统一 regime taxonomy/report | diagnostics report schema | P1 |
| Feature/alpha correlation | 部分已有 | HYPE factor Spearman prune、MHCSML ablation | 无 alpha score/position/PnL correlation library | correlation/cluster/leave-one-out artifacts | P1 |
| PnL attribution | 部分已有 | 月频 MCSM price/funding/fee/slippage attribution | 无统一 order/position ledger | shared attribution ledger | P1 |
| Dollar neutral | 缺失为平台接口 | 部分 family long-short 等权 | 无 constraint report | weight projection + tolerance tests | P0 |
| BTC/market beta neutral | 缺失 | 只有 relative-to-BTC features/labels | 无 rolling beta/exposure constraint | past-only beta estimator + residual label + report | P1 |
| Sector/theme neutral | 缺失 | 无 PIT taxonomy | taxonomy 不稳定，易误杀 alpha | Phase 2 optional arm，不作 Phase 1 hard default | P1 |
| Size/liquidity/vol controls | 部分已有 | ADV filters、vol scaling in other families | 无统一 exposure layer；market cap/float 缺失 | cap/report first，residualization controlled arm | P1 |
| Simple portfolios | 需要重构 | Top-N、threshold、equal-weight、allow-cash allocator | family-bound schemas | common score-to-weight constructors | P0 |
| Optimizer | 缺失 | 无 covariance/turnover-penalty optimizer | 过早优化会扩大试验空间 | Phase 2 only after simple baseline | P1 |
| Fee/funding | 已有基础 | fixed fee/slippage + actual funding、correct linear returns | venue/symbol/time-varying fee tier 缺失 | cost breakdown schema；保持 conservative taker baseline | P0 |
| Spread/top-of-book | 缺失数据 | TICKER schema 仅 bid/ask | 无历史 snapshots、staleness contract | Phase 2 采集 Binance/HL top-of-book | P1 |
| Impact/orderbook depth | 缺失 | Amihud 仅 feature proxy | 无 L2/depth/impact calibration | Phase 3 event replay | P2 |
| Exchange filters | 缺失 | specs 偶有文字要求 | tick/step/min notional 无数据与 rounding engine | instrument master + order normalization tests | P1 |
| Capacity curve | 缺失 | ADV 可作 proxy | 无 capital grid/impact/constraint binding report | Phase 1 proxy；Phase 2/3 calibrated curve | P0/P1 |
| Intrabar execution | 部分已有 | 15m/1m family replays、next-open rules | 无 CS batch order replay | Phase 1 15m replay；Phase 3 orderbook | P1 |
| Experiment registry | 缺失 | 只有 `runs.sqlite` path；family JSON manifests | 无表、API、immutable receipts、trial parentage | append-only SQLite + JSON receipt | P0 |
| Trial accounting | 部分已有 | 若干 scripts 写 `trial_count` | 无跨 run 全局累计 | registry 强制 declared/actual trial count | P0 |
| DSR/PSR | 部分已有 | Keltner family one-off implementation | 非共享、未与 registry trial count 绑定 | 提炼 statistics module | P1 |
| PBO/FDR | 缺失 | 无实现 | 大规模 alpha mining 无校正 | Phase 2 PBO/CSCV + BH-FDR | P1 |
| Alpha library | 缺失 | factor registry 不是 alpha registry | 无 score/OOF/exposure/cost/capacity identity | alpha manifest + status catalog | P1 |
| Alpha ensemble | 缺失 | MHCSML 多 seed/model utility 是局部先例 | 无跨 alpha corr/marginal contribution | simple equal/IC-weight/ridge stacking | P1 |
| Prospective OOS governance | 部分已有且强 | MHCSML freeze/blind chain/one-time reveal | family-specific，旧产物已删除 | registry 驱动的新 baseline freeze | P1 |

## 关键复用规则

1. 复用 `src/strategy_lab/data` 的稳定数据内核，不复制 warehouse/quality 逻辑。
2. 从已归档 CSLGBM/MHCSML **提炼算法与测试思想**，不恢复它们的版本身份、模型、绩效或 OOS。
3. 旧 MHCSML 当前直接 import 旧 CSLGBM script；新共享内核不得依赖已归档 family path。
4. 现有 CTA/HYPE family engines 保持不动；cross-sectional shared kernel 采用新 versioned 目录。
5. Phase 1 只实现 baseline 需要的接口，不先造通用 DAG、optimizer 或神经网络平台。
