# GOLD-1D-Multi-Speed-TSMOM 文献基线契约（2026-08-18）

## 研究身份

- Family：`GOLD-1D-Multi-Speed-TSMOM`（`GOLD-1D-MS-TSMOM`）
- 状态：`explore / not promoted / not live-ready`
- 目标：零调参复现黄金单标的 `1M/3M/12M` TSMOM；不搜索、不登记版本。

## 数据合同

- 交易场所：COMEX；提供方代码：Stooq `GC.F`。
- 可获得快照：`raja-grewal/stooq-commodities` 的 `stooq_major.csv`，固定 commit
  `e4be293bde6a79cdf0d353bade1691d9717948d1`，数据范围 `1985-10-01` 至
  `2021-12-24`。仓库标注 MIT；底层 Stooq 数据再分发权利不作扩张解释。
- 日频输入只使用 `GC.F` 的 `Open/High/Low/Close/Volume/OpenInt`；42 个全空价格行
  在 raw ingest 时删除并计入审计，价格 OHLC 保持不改写。
- 只使用最后一个完整自然月，数据末端所在的不完整月不进入绩效。
- 数据写入统一 raw 湖：`exchange=comex/market_type=futures/timeframe=1d`。
- `quality_status=raw_unaccepted`：逐合约 roll mapping、价格调整、交易所日历、
  `is_closed`、`trade_count`、`vwap` provenance 未核验，且快照止于 2021 年，禁止
  trusted/promotion 或当前可交易性结论。
- 被拒绝数据候选：Yahoo `GC=F` 的 Kaggle v2 日线存在 `441` 行 O/H/L/C 区间不自洽，
  未进入主回测，也未被静默修补。

## Alpha 与时序

月末 `t` 使用当月最后一根可见日线收盘：

`S_h(t) = sign(P_t / P_(t-h) - 1)`，`h ∈ {1M, 3M, 12M}`。

四条分支分别为 `S_1M`、`S_3M`、`S_12M` 与
`Composite = (S_1M + S_3M + S_12M) / 3`。信号仅在月末更新；月末收益本身仍由
旧仓位承担，新目标仓位从下一交易日收益开始生效。

## Risk

- 日简单收益：`r_t = Close_t / Close_(t-1) - 1`。
- `v_t = (60/61) v_(t-1) + (1/61) r_(t-1)^2`；即 pandas `com=60`、
  `adjust=False`、`min_periods=60`，并先 `shift(1)`。
- `sigma_ann(t) = sqrt(252 × v_t)`。
- `position_t = forecast_t × 0.10 / sigma_ann(t)`；不加仓位上限。
- 单标的不做多资产协方差与组合层二次波动率目标。

## PnL 与成本

- 日毛收益：`position_(d-1 close) × (Close_d / Close_(d-1) - 1)`。
- 换手：新仓位开始生效日的 `abs(position_d - position_(d-1))`；首仓从 0 计。
- 同时输出 `0 bps` 与单边 `2 bps` 每单位换手版本；风险自由利率为 0。
- 连续合约价格所含 roll representation 由提供方决定；因无逐合约映射，换月成交成本
  和 roll return 均未独立核验或拆分。这是硬限制，不得用结果掩盖。

## 固定输出

- 四分支 × 两成本版本：CAGR、年化算术收益、年化波动、Sharpe、Sortino、最大回撤、
  Calmar、正收益月份比例、日胜率、年化换手、毛/净总收益与仓位统计。
- 全样本、分年份、分月、最近 `1d/7d/1m/3m/6m/1y` 审计切片。
- 自包含交互 HTML：完整价格、月末 forecast/position、净值、分年收益和 composite
  方向 episode 表；切片只作事后审计，不参与选择。
