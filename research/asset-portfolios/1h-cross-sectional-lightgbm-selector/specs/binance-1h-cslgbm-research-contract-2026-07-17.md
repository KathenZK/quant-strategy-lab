# BIN-1H-CSLGBM 冻结研究契约（2026-07-17）

## 身份与目标

- Family：`Binance-1H-Cross-Sectional-LightGBM-Selector`（`BIN-1H-CSLGBM`）。
- 市场：Binance USD-M、USDT perpetual、`1h`。
- 状态：`explore / not promoted / not live-ready`；当前没有登记版本。
- 目标：验证多币种横截面 LightGBM 是否能在真实成本、动态币池和冻结 OOS 下稳定战胜简单规则/线性基线；找不到全门槛候选时如实记录失败，不降低标准。

## 数据契约

- 研究起点：`2020-01-01 00:00 UTC`；数据终点以最后一个完整 UTC 月为准。
- 来源优先级：Binance Vision 月/日归档作为历史主源，Binance REST API 只补当前尾部和做重叠对拍；所有修复写回标准数据湖。
- 必需数据：contract metadata / inventory、OHLCV、quote volume、trade count、taker buy volume/quote、mark price、funding。
- 可选数据：OI、basis、liquidation、long-short ratio；覆盖不足时只保留可用性报告，不准用 0 冒充缺失历史。
- 数据硬检查：UTC、closed bar、连续性、重复键、OHLC 合法、关键空值、source、raw/normalized 对齐、归档 checksum、API/归档重叠一致性。
- 历史上市/下架合约必须保留；不得只按当前 `TRADING` 列表回填历史。

## Point-in-time 动态币池

- 基础候选：该小时存在已闭合 1h K 线的历史 USDT perpetual；不使用未来下架时间判断当时是否可交易。
- 冷启动：上市不足 `30d` 的合约不可交易，但数据保留供后续研究。
- 连续性：过去 `30d` 闭合 1h K 线覆盖率至少 `99%`。
- 流动性：只使用 K0 前已完成数据计算过去 `7d` 平均日 quote volume；主试验取当时 Top 100 且平均日 quote volume `>= 10,000,000 USDT`。
- 稳健性：另测 Top 50 / Top 150 和 `5m/20m USDT` 日均成交额门槛，但不得用锁定 OOS 选择主口径。
- stablecoin、指数、交割合约、非 USDT quote 和无法确认 perpetual 身份的目录排除，并保留排除原因。

## 特征与标签

- 因子数不固定；从约 `60–150` 个候选起步，按目标扩展，不把数量本身当成果。
- 类别：趋势、动量、反转、波动率、量价、taker flow、funding、mark/index basis、BTC/ETH 相对强弱、市场广度、横截面 rank/z-score、上市年龄与流动性状态。
- K0 收盘特征只使用 K0 及以前的数据；横截面标准化只使用同一 K0 当时的可交易集合。
- 标签：K1 open 入场后的未来 `4h/12h/24h` 净收益、同期市场中性相对收益和横截面 rank；扣除双边手续费、滑点和持仓 funding。
- purge / embargo 至少覆盖所用最长 `24h` 标签和重叠持仓影响。

## 模型与基线

- LightGBM regression、binary classification、`LGBMRanker` 均须测试。
- 基线：横截面动量、均值反转、等权篮子/市场中性篮子、线性/逻辑回归。
- 不允许随机切分。采用 expanding / rolling walk-forward；模型、特征和阈值只根据 train/validation 决定。
- 比较 long-only Top N、long-short Top/Bottom N、全局单仓最高置信机会。

## 冻结 OOS

- 锁定窗口：`2026-04-01 00:00 <= ts < 2026-07-01 00:00 UTC`。
- 在所有因子、模型、标签、组合和阈值冻结前，不读取该窗口的预测绩效、交易结果或分片结论。
- OOS 只揭示一次；失败后不得回到同一窗口继续选参。后续修改需要新 future OOS。

## 成本和执行

- 基准每次成交：手续费 `0.001` + `4 bps` 不利滑点；round trip 基础成本为 `28 bps`，另计 funding。
- 压力：总手续费/滑点成本 `1.5x`；另做成交延迟、流动性收紧、缺 bar、拒单和跳空审计。
- K0 close 生成排名，K1 open 执行；持仓切换必须先平后开并计两组成交成本。

## 最终硬门槛

- 冻结 OOS 年化收益 `>=100%`。
- 最大回撤 `<=20%`；胜率 `>=55%`；Sharpe `>=1.5`；Profit Factor `>=1.30`。
- OOS 完成交易 `>=100`；正收益月份 `>=60%`。
- `1.5x` 成本下仍为正收益且最大回撤 `<=25%`。
- 单币利润贡献 `<=25%`；单月利润贡献 `<=35%`。
- 多数 walk-forward 窗口为正，且 LightGBM 必须稳定战胜简单规则/线性基线。

## 交付

- 数据质量报告、历史合约清单、动态币池、因子和数据集 manifest。
- 模型文件、预测排名、阈值、逐笔交易、组合净值、walk-forward 和冻结 OOS。
- 成本/流动性/种子/窗口/regime/集中度压力测试。
- `GO` 或研究失败结论、可由其他 AI 在无仓库上下文下复现的完整规格。
