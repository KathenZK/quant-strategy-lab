# HYPE-1D-Pyramiding-Trend 搜索契约（2026-07-22）

## 身份与目标

- Family：`HYPE-1D-Pyramiding-Trend`（`HYPE-1D-PT`），与 `HYPE-1D-MHEF`、15m/1h 家族完全独立。
- 市场：Binance USD-M `HYPEUSDT` perpetual；信号周期为 UTC `1d`。
- 最大杠杆：`3.0x`；初始 `1.0x`，仅在已有浮盈且价格继续顺趋势跨过 ATR 台阶后，允许两次各 `1.0x` 加仓。
- 硬目标：年化权益倍数 `>=20.0x`、按完整 campaign 计算的净胜率 `>=80%`、保守日内最大回撤不超过 `20%`。
- 证据下限：prefit 至少 `8` 个已平 campaign，锁定 OOS 至少 `3` 个；不足时即使表面比例达标，也不视为可信命中。

## 数据与冻结边界

- 原始输入：标准数据湖中已审计的 Binance `HYPEUSDT` perpetual `1h` raw/normalized K 线与历史 funding。
- 日线：只聚合恰好包含 24 根已收盘小时 K 的 UTC 自然日。
- 当前完整日线范围：`2025-05-31 00:00 UTC` 至 `2026-07-21 00:00 UTC`；以 `2026-07-22 00:00 UTC` open 作为终点估值/执行价。
- 锁定 OOS：`2026-04-23 00:00 UTC` 至 `2026-07-22 00:00 UTC`，固定为最后 90 天。
- prefit terminal：`2026-04-22 00:00 UTC`；与 OOS 之间保留 1 天 embargo。参数搜索和候选排序不得读取锁定 OOS 收益、胜负或回撤。

## 成本、时序与风险口径

- 信号只使用已收盘的日 K；`t` 日收盘形成信号，基础回测在 `t+1` 日 open 以市价等价成交。
- 每次增减仓按成交名义收取手续费 `0.001` 与不利滑点 `4 bps`；压力测试使用 `8 bps` 滑点。
- funding 按实际时间戳累计到上一持仓；调仓前先结算持仓期间的价格变化和 funding。
- 胜率按从首次建仓到完全平仓的 campaign 计算；两次浮盈加仓是同一 campaign 内的 fill，不拆成额外“胜单”。
- 回撤采用保守日内界：同一日按对持仓最不利的 high/low 顺序计算潜在峰谷，并计入手续费、滑点和 funding。
- 额外审计 `K+2` 执行延迟；基础口径通过但压力口径失败时，不得称为 live-ready。

## 搜索空间

- 机制族：Donchian breakout、Keltner breakout、time-series momentum、EMA cross。
- 可选过滤与出场：EMA trend/slope、ADX、ATR 波动上限、Donchian exit、ATR trailing、profit lock、EMA exit、max hold、cooldown。
- 方向：双向、long-only、short-only均可搜索；方向本身属于冻结参数，不能在 OOS 揭示后改写。
- 搜索使用固定 seed；保留 prefit 多目标 frontier，不用单一收益分数提前剪掉高胜率或低回撤候选。

## 决策规则

只有 frozen prefit shortlist 中的同一配置，在 prefit、锁定 OOS flat-start 和 full 三个窗口都同时满足三项硬目标、交易数证据下限及实际发生过浮盈加仓，才记为本轮有效命中。否则结论保持 `explore / not promoted / not live-ready`。
