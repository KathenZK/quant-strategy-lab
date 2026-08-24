# BIN-1D-BE-LRMR P0 冻结合同（2026-08-12）

## 1. 研究问题与身份

测试 BTC/ETH log price ratio 的日频均值回归，能否在初始总毛杠杆 `1x`、真实双腿成本/funding 下达到 development `>=20x` 且 conservative ordered `1h` MDD `<=20%`。

family 为 `Binance-1D-BTCETH-Log-Ratio-Mean-Reversion`（`BIN-1D-BE-LRMR`）。它不是 MA7 V2、RCR V1 或已有 Turtle/EWMAC/TSMOM 的重命名。

## 2. 数据与封存

完全复用已冻结、blocker 为 0 的 BTC/ETH perp `1h` 与 funding/mark 快照及 P0 hashes：

- BTC hourly/funding：`3e18066005c9747c040c2686e0b535769f293911e660ad8f923d81b0e2bee1cb` / `83e4043d905274dd11d3f7874605cbe05bfea927d80853dd96959d1effd45aca`；
- ETH hourly/funding：`29a5c7ba22831240629d48899b34c7cbfe9f411c139f7dd5220979958a416561` / `f16a71928dad18e930db63bfe70d1d949ce79f7061b83717de9c2b50ea7cdb54`。
- 只读数据装载/哈希/UTC 聚合 helper 固定为 `search_binance_1d_be_rcr_p0.py` SHA256 `8fe4f043a3fdffb6aa74ec0860d51d13ec8539442fe28641233e30c8567c8d29`；不得调用其 RCR 信号或结论。

development `[2019-12-24,2025-08-07)`；researcher-exposed audit `[2025-08-07,2026-08-10)`；prospective 信号日 `>=2026-08-13`、首次执行 `>=2026-08-14`。搜索、排序、消融只可使用 development。

## 3. 信号、仓位与执行

- 闭合日 `t`：`ratio[t]=log(BTC_close[t]/ETH_close[t])`；用含 `t` 的过去 `lookback` 日样本均值和样本标准差计算 `z[t]`。
- flat 且 `z>=entry_z`：下一日开盘 short BTC、long ETH；`z<=-entry_z`：long BTC、short ETH。
- 每腿 entry notional 为成交前组合 equity 的 `0.5x`；两腿数量持有期固定，不逐日 beta hedge、再平衡或缩放。
- 持仓后，`abs(z)<=exit_z` 或 z 穿越 0：下一日开盘双腿平仓。
- 若 `stop_z>0` 且 `abs(z)>=stop_z` 并比前一日更远离 0：下一日开盘止损；`max_hold_days>0` 达龄也于下一开盘退出。
- 退出后等待 `cooldown_days` 个完整 UTC 开盘；终点强制双腿平仓。
- 每腿每 fill fee `0.001`；base/stress slippage `0.0004/0.0008`。long 扣、short 加真实 funding；双腿按各自数量和 mark 独立记账。

## 4. 冻结有限搜索

- `lookback ∈ {20,30,45,60,90,120,180}`；
- `entry_z ∈ {1.0,1.5,2.0,2.5,3.0}`；
- `exit_z ∈ {0,0.25,0.5,0.75,1.0}`，仅保留 `exit_z<entry_z`；
- `stop_z ∈ {0,3.0,4.0,5.0}`，非零时仅保留 `stop_z>entry_z`；
- `max_hold_days ∈ {0,3,7,14,30,60}`；
- `cooldown_days ∈ {0,1,3,7}`。

过滤后固定为 `15,288` 个合法配置，必须全部执行；结果出现前不得增删。先做日线 close path 筛选，所有 `equity>=20x && daily MDD<=20%` 配置必须做 conservative ordered `1h` 重放。

## 5. Conservative ordered `1h` MDD

每小时按：开盘双腿成交 → funding events → 对当前 pair 同时采用两腿最不利极值（long leg low、short leg high）计算保守 equity trough → close equity。该值是 1h OHLC 信息下不依赖未知分钟顺序的风险上界；不得用两腿有利极值或 close-only MDD 代替。

## 6. Development 门禁

唯一候选必须全部满足：

1. base equity `>=20x`、conservative ordered MDD `>=-20%`；
2. stress `>=16x/MDD>=-22%`；
3. 额外延迟一日 log-growth retention `>=70%`、equity `>=8x/MDD>=-25%`；
4. 完整年与 rolling 365d 正收益比例均 `>=70%`；
5. closed pairs `>=20`，long-BTC/short-ETH 与 short-BTC/long-ETH 各 `>=8`；
6. 最大单 pair 正向 log-growth 占总正向 log-growth `<=35%`；
7. 双腿 fills、费用、slippage、funding、cooldown 与终点平仓逐项对账。

同路径去重后按 ordered MDD、stress retention、base equity、交易数、参数字典序确定唯一候选。任一失败即 `HARD-GATE-FAILED / explore / not promoted / not live-ready`，audit/prospective 不揭示、不登记版本；禁止用 fixed leverage 或 vol target 救援。
