# BIN-1D-BE-CBCT P0 冻结合同（2026-08-12）

## 1. 机制身份与去重

候选资产必须收盘突破自身 Donchian channel，且另一资产 EMA breadth 同向，才建立单一趋势仓位。退出使用短 Donchian channel 与日频更新、次日生效、按真实 `1h` 路径触发的 chandelier stop。

该 family 不是现有固定 20/10 same-close Turtle 扩参：cross-asset breadth、单仓竞争、next-open、actual funding 与 real `1h` stop 均为冻结身份。

## 2. 数据与 OOS

复用冻结 BTC/ETH perp `1h` 与 funding/mark hashes；development `[2019-12-24,2025-08-07)`，researcher-exposed audit `[2025-08-07,2026-08-10)`。prospective 首个 eligible closed day `>=2026-08-13`、首次执行 `>=2026-08-14 00:00`。

数据 helper 固定为 `search_binance_1d_be_rcr_p0.py` SHA256 `8fe4f043a3fdffb6aa74ec0860d51d13ec8539442fe28641233e30c8567c8d29`；只使用装载、哈希、UTC 聚合与 funding。

## 3. 信号、竞争与执行

- 闭合日 `t`，candidate long：`close[t] > max(high[t-entry_n:t])`；short：`close[t] < min(low[t-entry_n:t])`，channel 不含 `t`。
- candidate 与 peer 均须 long 时 `close>EMA(breadth_ema)`、short 时 `close<EMA`；EMA 含 `t`，使用 `adjust=False`，达到完整 span 后才有效。
- 同日多个候选时，以突破 channel 的 ATR14 标准化距离绝对值最大者胜出；完全相同则 BTC 优先。信号需连续 `confirm_days` 保持同一 `asset×side`。
- 下一 UTC 日 open 以成交前 equity 约 `1x` 建仓；持仓时忽略新 entry signals，数量固定。
- channel exit：long `close < prior exit_n-day low`，short `close > prior exit_n-day high`，下一日 open 退出。
- `ATR14` 为 true range 的 14 日简单均值。chandelier：每日闭合后，long 更新为 `max(high since entry)-trail_atr*ATR14`，short 为 `min(low since entry)+trail_atr*ATR14`；入场日无 active level，首次 level 由入场日收盘生成并从下一日 `00:00` 生效，只可向盈利方向移动。
- active stop 小时 gap 穿越按该小时 open 不利成交，否则首次 high/low 触及按 stop mark 不利成交；同小时顺序：日开盘订单 → funding → stop → conservative high/low/close 记账。
- 退出后等待 `cooldown_days` 个完整 UTC 开盘；`max_hold_days=120` 时达龄下一开盘退出，0 表示关闭。终点强平。
- fee `0.001/fill`；base/stress slippage `4/8bps`；actual funding。

## 4. 冻结 `2,808` 配置

- `entry_n ∈ {20,40,60,90}`；`exit_n ∈ {5,10,20,40}` 且 `exit_n<entry_n`（13 组）；
- `breadth_ema ∈ {20,50,100}`；`trail_atr ∈ {2,3,4,5}`；
- `confirm_days ∈ {1,2,3}`；`cooldown_days ∈ {0,3,7}`；
- `max_hold_days ∈ {0,120}`。

全部直接做 ordered `1h` ledger。结果前不得增删。

## 5. Development 门禁

base `>=20x/MDD<=20%`；stress `>=16x/MDD<=22%`；所有 daily orders 额外延迟一日且 stop level 仍因果生效时，log-growth retention `>=70%`、`>=8x/MDD<=25%`；完整年与 rolling 365d 正收益比例均 `>=70%`；closed trades `>=20`，BTC/ETH、long/short 各 `>=5`；最大单笔正 log-growth 占比 `<=30%`；channel/stop/funding/fee/cooldown/restart state 可对账。

同路径去重后按 MDD、stress retention、equity、交易数、参数字典序确定唯一候选。失败即 `HARD-GATE-FAILED / explore / not promoted / not live-ready`；audit/prospective 不揭示，不登记版本，不以 leverage/vol target 救援。
