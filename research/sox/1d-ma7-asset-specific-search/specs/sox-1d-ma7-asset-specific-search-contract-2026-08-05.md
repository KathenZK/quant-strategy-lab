# SOX 日线 MA7 共享参数控制与分资产搜索合同

## 研究顺序

1. 先把 BTC/ETH 共享 MA7 参数原样应用于 Yahoo `^SOX` 全历史。
2. 只有共享 combined 净收益不为正时，才触发 SOX 专属参数搜索。
3. 搜索固定 `SMA7/ATR7`，不搜索 MA 长度或 EMA。

## 标的与限制

- 序列：Yahoo Finance `^SOX`，PHLX Semiconductor price index。
- 周期：America/New_York regular-session 日线。
- 指数不可直接下单；用户未指定 ETF、期货或期权代理。
- 主结果为零手续费、零滑点、零借券和零融资的价格路径诊断；另给每 fill `10 bps` 示意摩擦。
- 只有 session OHLC；stop 可处理 open gap 和日内触碰，但无法恢复 high/low 先后。
- 原始 Yahoo 证据 SHA256：`402440c9129f65f828074089386d52c06d0c76ada67528af7a1ac96a0d5a5e4e`。

## 时间角色

- Backward audit：`1994-05-04` 至 `2009` 年末，不参与选择。
- Development：`2010-01-04` 至 `2021-01-04` exclusive。
- Researcher-exposed holdout：`2021-01-04` 至 `2026-08-04` terminal session，不参与本次选择。
- Full：完整可用历史。

SOX 历史已在此前迁移报告中查看；backward 与 holdout 都不是 clean OOS。

## 搜索空间与选择

- 固定 seed `20260805`，每方向抽样 `8,000` 个唯一配置。
- Long entry mode：`regime / reclaim / pullback_reclaim / breakout`；short 另允许 `open_regime`。
- 搜索 MA7 斜率回看与阈值、确认 session、ATR 入场带、pullback/breakout 回看、退出确认与迟滞、斜率退出、hard stop、trailing、max-hold 和 cooldown。
- 每方向保留 `120` 个 development 稳健候选，前 `20 × 20` 配对。
- Development 评分同时考虑全段、前后半段、最近 90 sessions、`10 bps/fill` 示意摩擦和额外延迟一 session。
- 固定输出 development-selected combined、long-only、short-only；不按 backward、holdout、full 或近期结果二次挑选。

## 执行

- 收盘信号下一 regular session open 成交。
- 单仓、约 `1x`、非加仓，持仓期间数量固定。
- 日 open 跳空穿越 stop 时按 open；session 内 high/low 触发时按 stop。
- `^SOX` 结果不得直接解释为可执行策略收益。

## 审计

- 四个时间角色的 base、`10 bps/fill`、额外延迟一 session 与 buy-and-hold；
- 逐年窗口、滚动三年、最近 `1d/7d/1m/3m/6m/1y`；
- 完整逐笔和权益路径；
- 正绝对收益只回答用户的搜索问题；无超额、holdout 失败或不可交易限制仍阻止登记和 promotion。
