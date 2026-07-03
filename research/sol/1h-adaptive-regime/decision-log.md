# SOL-1H-Adaptive-Regime Decision Log

## 2026-07-03：建立独立 SOL 1h 家族并锁定最近三个月 OOS

- 新建 `SOL-1H-Adaptive-Regime`，不继承 BTC/HYPE 版本身份。
- 数据固定为 Binance USD-M Futures `SOLUSDT` perpetual 最近两年全部闭合 `1h` K。
- 最近三个月固定为 locked OOS；参数生成、搜索、排序和 ensemble 选择仅允许使用此前的 train/validation。
- 目标保持原始硬门槛：年化权益倍率 `>=10.0x`、胜率 `>=50%`、最大回撤严格小于 `20%`。
- 采用下一根 open 成交、即时保护 bracket、stop-first、跳空按 open、闭合 K 更新 trailing 的可实盘时序。
- 成本固定为 `0.001` fee/fill、`4 bps` adverse slippage/fill，并计入真实历史资金费。
- 在 locked OOS 和 live-executable 审计完成前，状态保持 `diagnostic / not promoted / not live-ready`。
- 在揭示第一轮 OOS 结果前预先固定第二轮精调规则：只从第一轮 prefit CSV 的 train/validation 字段选择 Pareto seed，随机变异 `1-5` 个参数字段；第二轮选择仍不使用 OOS。
