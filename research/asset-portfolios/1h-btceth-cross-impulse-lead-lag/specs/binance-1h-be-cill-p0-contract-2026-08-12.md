# BIN-1H-BE-CILL P0 冻结合同（2026-08-12）

## 1. 机制身份

在每个闭合 `1h`，若 BTC/ETH 中一币出现显著、且强于另一币的波动归一化冲击，则下一小时开盘交易另一币（follower）同方向 catch-up。family 为 `Binance-1H-BTCETH-Cross-Impulse-Lead-Lag`，不是 MA7/RCR/LRMR 版本。

## 2. 数据与封存

复用 blocker 为 0 的 Binance BTC/ETH perp `1h` 与 funding/mark frozen hashes；development `[2019-12-24,2025-08-07)`，researcher-exposed audit `[2025-08-07,2026-08-10)`。prospective 首个 eligible closed hour `>=2026-08-13 00:00`、首次执行 `>=01:00`。

数据 helper 固定为 `search_binance_1d_be_rcr_p0.py` SHA256 `8fe4f043a3fdffb6aa74ec0860d51d13ec8539442fe28641233e30c8567c8d29`，只使用装载、哈希与小时 union。

## 3. 信号与执行

- `r_i[t]=log(close_i[t]/close_i[t-1])`；`vol_i[t]` 为不含当前 `r[t]` 的过去 `vol_h` 小时样本标准差；`z_i=r_i/vol_i`。
- leader 为 `abs(z)` 较大资产；要求 `abs(z_leader)>=impulse_z` 且 `abs(z_leader)-abs(z_follower)>=gap_z`。
- `side=sign(r_leader)`；要求 `side*z_follower<=follower_cap_z`，避免 follower 已充分追随。
- flat 时触发后下一小时 open，以成交前 equity 的 `1x` 交易 follower；持仓数量固定。持仓时忽略新 impulse。
- `catchup_fraction>0` 时，若 `side*log(follower_close/entry_open_mark) >= catchup_fraction*abs(r_leader_at_signal)`，下一小时 open 退出。
- `stop_sigma>0` 时，若 `side*log(follower_close/entry_open_mark) <= -stop_sigma*vol_follower_at_signal*sqrt(max_hold_hours)`，下一小时 open 退出。
- 达 `max_hold_hours` 后下一小时 open 强制退出；退出后等待 `cooldown_hours` 个完整开盘。
- terminal 强制平仓；closed-hour signal、next-open 成交。fee `0.001/fill`，base/stress slippage `4/8bps`，真实 funding 逐事件计入。

## 4. 冻结 `2,160` 配置

- `vol_h ∈ {24,72,168}`；`impulse_z ∈ {2,3,4}`；
- `gap_z ∈ {0.5,1.0}`；`follower_cap_z ∈ {0.5,1.0}`；
- `catchup_fraction ∈ {0,0.5,1.0}`；
- `max_hold_hours ∈ {3,6,12,24,48}`；
- `stop_sigma ∈ {0,2.0}`；`cooldown_hours ∈ {0,6}`。

全配置直接按 ordered `1h` ledger 执行，不使用 daily-close 预筛。结果出现前不得增删参数。

## 5. Development 门禁

唯一候选必须全部满足：base `>=20x/MDD<=20%`；stress `>=16x/MDD<=22%`；所有 entry/exit orders 额外延迟一小时后的 log-growth retention `>=70%`、`>=8x/MDD<=25%`；完整年与 rolling 365d 正收益比例均 `>=70%`；closed trades `>=40`，BTC/ETH follower、long/short、BTC-lead/ETH-lead 各 `>=10`；最大单笔正 log-growth 占比 `<=25%`；费用/funding/restart 所需状态均可对账。

同路径去重后按 MDD、stress retention、equity、交易数、参数字典序确定唯一候选。任一失败即 `HARD-GATE-FAILED / explore / not promoted / not live-ready`；audit/prospective 不揭示、不登记版本，不做 leverage/vol-target 救援。
