# Binance 1D MA7 P2-C Long Pullback Episode 归因合同

## 1. 研究问题

P2-B development-only 全参数 OAT 显示：只把 V1 long `entry_mode` 从 `reclaim` 改为 `pullback_reclaim`，BTC/ETH 终值从 `1.2235x / 2.2988x` 提高到 `6.3164x / 6.0161x`，但 MDD 仍为 `-52.80% / -56.76%`。

本轮不继续调参，只回答：新增 long episode 为什么同时提高收益并保留巨大回撤？风险来自入场过密、趋势末端重入、入场后立即逆行、已有浮盈回吐、还是原 slope/hysteresis exit 过慢？

## 2. 冻结身份

- Family：`Binance-1D-MA7-Asset-Specific-Search`
- Campaign：`P2-C long-pullback episode attribution`
- 状态：`explore / not promoted / not live-ready`
- Baseline：已登记 V1 exact shared 参数
- 唯一 probe：long 仅改 `entry_mode: reclaim -> pullback_reclaim`；其它 long 字段、完整 short、成本、funding、仓位和执行时序不变
- 证据角色：development-only causal diagnostic，不是候选版本，不登记 V2

## 3. 数据与隔离

- 使用 P2 冻结的 BTC/ETH P0 直接 `1h`、UTC 日线和实际 funding/mark 快照；
- 只运行 `2019-12-24 00:00 UTC` 至 `2025-08-07 00:00 UTC` exclusive；
- 禁止读取或输出 `2025-08-07` 之后的 researcher-exposed audit 绩效；
- 禁止读取 prospective；
- attribution 输出不得用于在同轮选择阈值。

## 4. 固定比较

每个资产运行四条路径：

1. V1 combined；
2. probe combined；
3. V1 long-only；
4. probe long-only。

逐笔归因以 long-only 为主，避免 short 仓位占用和反向路径改变混淆 long episode；combined 只检查账户级交互。

## 5. 固定逐笔字段

每笔 probe long 必须输出：

- entry/exit timestamp、price、成本后 return、bars held、exit reason；
- 是否与 V1 long-only 有相同 entry timestamp；
- entry 前一次 probe exit 至本次 entry 的 flat gap；
- signal close 相对 SMA7 的 ATR 距离；
- SMA7 五日斜率 / ATR7；
- signal 时连续收盘在 SMA7 上方的 trend age；
- 持仓小时路径 MFE、MAE、MFE/MAE 的 ATR7 倍数；
- 从最大有利价到实际 exit 的 giveback；
- calendar year 与连续亏损 cluster id。

## 6. 固定汇总

- `native-entry` 与 `added-entry` 分组：数量、胜率、mean/median return、PF、MFE/MAE/giveback 分位数；
- exit reason 分组；
- trend-age bucket：`1-2d / 3-5d / 6-10d / >10d`；
- flat-gap bucket：`0-2d / 3-5d / 6-10d / >10d / first`；
- calendar year；
- 连续亏损 cluster：起止、笔数、复合 return、最大单笔亏损、entry/exit 原因。

## 7. 后续机制准入

本轮不以收益最高的事后阈值生成候选。只有满足下列任一跨资产因果模式，才允许在新的 P2-D 合同中冻结少量机制臂：

1. 两资产 added-entry 的大亏损都集中在短 flat gap / 高 trend age：允许测试 episode re-entry budget；
2. 两资产多数大亏损在入场后先出现显著 MAE、很少出现正 MFE：允许测试初始 ATR hard stop；
3. 两资产亏损交易多数先出现足够 MFE 后大幅 giveback：允许测试盈利后保护；
4. 两资产主要损失由 slope exit 持有过久产生：允许测试独立结构破坏 exit。

如果 BTC、ETH 的失败模式不一致，禁止强行共享同一阈值；应裁决 shared-parameter substrate 不支持该机制，或另立分资产家族。

## 8. 交付与裁决

- 机器 JSON、逐笔 CSV、loss-cluster CSV；
- 中文 diagnostic，明确支持/不支持的机制假设；
- 本轮不生成 HTML、不打开 audit、不登记版本、不推进 runner。

