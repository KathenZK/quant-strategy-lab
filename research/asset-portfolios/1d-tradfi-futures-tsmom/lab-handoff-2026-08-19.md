# TSMOM 研究在 Lab 仓库的事实源清单

> 核验日期：2026-08-19。唯一事实源为
> `/Users/ZK/OpenCode/quant-strategy-lab`。`Documents/.../outputs` 仅是便于打开的交付副本，
> 不参与复跑、版本判断或后续迭代。

## 1. 研究家族

### 黄金单资产

- 家族：`research/gold/1d-multi-speed-tsmom/`
- 冻结规则：月末 `sign(1M/3M/12M return)`，信号作用于下一期，EWMA COM=60，
  单资产目标波动率 10%。
- 原始快照：`data/raw/ohlcv/exchange=comex/market_type=futures/timeframe=1d/`
  - `source=github_stooq_commodities_snapshot`：9,154 个日分区，1985-10-01 至 2021-12-24；
  - `source=yahoo_chart_snapshot`：1,667 个日分区，2020-01-02 至 2026-08-18。
- 代码、契约、诊断、图表、逐日/月末路径和 SHA256 清单均在家族目录内。

### 四类传统期货组合

- 家族：`research/asset-portfolios/1d-tradfi-futures-tsmom/`
- 研究面：24 个 Yahoo 连续期货、30 个 ETF/FX 长期代理，以及 AQR 作者原始/更新因子。
- 原始期货快照：
  `data/raw/ohlcv/*/market_type=futures/timeframe=1d/source=yahoo_chart_futures_snapshot/`，
  共 40,021 个日分区。
- AQR 原始工作簿、抽取 CSV、本地重建路径、指标与 SHA256 清单在 `artifacts/`。
- 论文原式：`12M sign × 40% / sigma`，所有当月有效市场等权，信号持有下一月。

## 2. 仓库内入口

- 黄金基线与近期段：`research/gold/1d-multi-speed-tsmom/README.md`
- 传统期货组合：`research/asset-portfolios/1d-tradfi-futures-tsmom/README.md`
- 论文原式报告：
  `research/asset-portfolios/1d-tradfi-futures-tsmom/diagnostics/`
  `tf-1d-fut-tsmom-paper-exact-p1-2026-08-19.md`
- 论文原式冻结契约：
  `research/asset-portfolios/1d-tradfi-futures-tsmom/specs/`
  `tf-1d-fut-tsmom-paper-exact-p1-contract-2026-08-19.md`
- 原始数据湖：`data/raw/ohlcv/`；该目录按仓库约定不进入 Git。

## 3. 外部交付副本核验

已对 `Documents/.../outputs` 的 16 个 TSMOM 交付文件逐个计算 SHA256：

- 4 个黄金报告/HTML 与 `research/gold/1d-multi-speed-tsmom/` 内文件完全一致；
- 12 个多资产、代理及论文复刻文件与
  `research/asset-portfolios/1d-tradfi-futures-tsmom/` 内文件完全一致；
- 因此没有只存在于外部目录、需要反向迁移的研究文件。

外部副本暂不删除，以免破坏已经打开的本地链接；后续一律从 Lab 路径继续。

## 4. 完整性与复现

五份已冻结 SHA256 清单已于 2026-08-19 全量复核通过：黄金基线、黄金近期扩展、24
期货 P0、30 代理长期验证、论文原式 P1。复跑命令由各诊断报告和脚本 README 冻结。

关键入口：

- 黄金脚本：`research/gold/1d-multi-speed-tsmom/scripts/`
- 多资产脚本：`research/asset-portfolios/1d-tradfi-futures-tsmom/scripts/`
- 黄金校验清单：`research/gold/1d-multi-speed-tsmom/artifacts/*checksums.sha256`
- 多资产校验清单：
  `research/asset-portfolios/1d-tradfi-futures-tsmom/artifacts/*checksums.sha256`

## 5. 当前边界

数据与产物已经进入 Lab 的统一目录结构，但家族目前仍是 Git 未跟踪变更，尚未提交。
Yahoo/Stooq 连续合约缺少逐合约换月与结算价证据，因此研究结论维持
`diagnostic-only / not promoted / not live-ready`。
