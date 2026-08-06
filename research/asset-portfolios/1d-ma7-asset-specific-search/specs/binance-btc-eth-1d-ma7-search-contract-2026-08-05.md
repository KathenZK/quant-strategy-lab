# Binance BTC/ETH 日线 MA7 分资产参数搜索合同

## 研究问题

在固定 `SMA7/ATR7` 核心与同一可执行状态机的前提下，分别为 `BTCUSDT`、`ETHUSDT` 搜索多空参数，并额外选择一组 BTC/ETH 共享参数，判断：

1. HYPE V1 直迁失败后，分资产参数能得到怎样的历史收益；
2. 收益能否在未参与选择的时间后段、成本、延迟和日界相位下保留；
3. 是否存在一组同时适用于 BTC/ETH 的参数。

本次 BTC/ETH 历史此前已被迁移诊断查看；任何时间后段都只能称 `researcher-exposed holdout`，不是 clean OOS。

## 市场与数据

- Binance USD-M `BTCUSDT`、`ETHUSDT` perpetual，UTC `1d`。
- accepted normalized `1h` 从 `2024-07-31 00:00 UTC` 开始；每日必须由正好 `24` 根 closed 小时 K 聚合。
- 主日界 `00:00 UTC`；相位审计 `12:00 UTC`。
- `SMA7` 为 7 个日收盘简单平均，`ATR7` 为 7 日 true range 简单平均。
- raw/normalized、时间连续性、重复、关键空值、OHLC、VWAP 与 funding 质量必须通过现有数据合同。

## 时间切分

- Development：数据起点至 `2026-02-01 00:00 UTC` exclusive。
- Researcher-exposed holdout：`2026-02-01 00:00 UTC` 至 terminal open。
- 参数生成、单边 shortlist、稳定性评分、组合配对和共享参数选择只读取 development。
- Holdout 只在候选固定后计算一次，但因其历史已经被其他报告查看，不宣称 OOS。

## 搜索空间

- 固定 MA 长度为 `7`，不搜索 EMA 或其他周期。
- 多头 entry mode：`regime / reclaim / pullback_reclaim / breakout`。
- 空头另允许 `open_regime`。
- 每个方向以固定 seed `20260805` 抽样 `20,000` 个唯一配置。
- 参数覆盖 MA 斜率回看与阈值、确认日数、ATR 入场带、pullback/breakout 回看、退出确认与迟滞、斜率退出、hard stop、trailing stop、max-hold 和 cooldown。
- 每个资产每方向保留 `120` 个 development 候选，前 `20 × 20` 配对。
- 共享路线先按 BTC/ETH 最差侧 stage-1 与稳定性联合评分，再取 `20 × 20` 配对。

## 选择目标

- Development 同时检查全段、前半段、后半段和最近 `90d`。
- 评分包含 `8 bps/fill` 压力与额外延迟一天。
- 分资产候选只按该资产 development 选择。
- 共享候选优先最大化 BTC/ETH 两侧的最差稳健分数，不使用 holdout 排名或二次挑选。

## 成交与成本

- 单仓、非加仓；每次入场按成交后权益建立约 `1x`，持仓期间数量固定。
- 收盘信号最早下一日 open 成交。
- stop 使用真实 `1h` 路径；小时 open 已穿越 stop 时按该 open，否则按 stop 价，再计不利滑点。
- 手续费 `0.001/fill`，基准不利滑点 `4 bps/fill`，压力 `8 bps/fill`。
- funding 按真实 Binance timestamp/rate，仅在实际持仓区间结算。

## 固定输出与限制

- 分资产候选、BTC/ETH 共享候选；
- development、researcher-exposed holdout、full；
- combined、long-only、short-only；
- `8 bps`、额外延迟一天、`0h/12h` 相位；
- 最近 `1d/7d/1m/3m/6m/1y` 与滚动 `180d`；
- buy-and-hold、逐笔与完整权益路径。

即使找到高历史收益，也不得登记或 promotion；本次任务只回答历史开发上能找到什么，以及这些收益在未参与选择的检查中如何衰减。
