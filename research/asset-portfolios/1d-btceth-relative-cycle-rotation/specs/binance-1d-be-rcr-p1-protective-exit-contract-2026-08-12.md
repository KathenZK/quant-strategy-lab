# BIN-1D-BE-RCR P1 Protective-Exit 冻结合同（2026-08-12）

## 1. 因果问题与固定 controls

P0 的共同周期/相对轮动已证明可达到 `21.2605x`，但 growth/risk 前沿 ordered MDD 分别为 `-69.6600%/-30.7607%`。P1 只回答：独立的保护退出与再武装状态能否降低方向翻转尾部，同时保留 `>=20x` 收益。

两个 exact controls 冻结如下，不再搜索原信号参数：

1. growth control：`(regime_h=40, relative_h=40, vol_h=28, deadzone=0, switch_margin=0.25, confirm_days=3)`；
2. risk control：`(regime_h=90, relative_h=60, vol_h=56, deadzone=1.0, switch_margin=0.25, confirm_days=2)`。

P1 不是风险缩放：持仓仍为固定数量、入场 `1x`、同一时点唯一仓位；不得调低 notional、vol target、drawdown target 或事后加杠杆。

## 2. 数据、区间与成本

完全继承 [P0 合同](binance-1d-be-rcr-p0-contract-2026-08-12.md) 的冻结 hashes、development `[2019-12-24,2025-08-07)`、researcher-exposed audit、prospective、`0.001/fill` fee、base `4bps/fill`、stress `8bps/fill`、actual funding 与 next-open 语义。P1 只读 development；未满足全部门禁不得揭示 audit。

## 3. 保护状态机

### 3.1 固定 ATR stop

- `ATR14` 为闭合日线 true range 的 14 日简单均值。
- 在日开盘入场时只使用前一闭合日 `ATR14`；stop 以未滑点 open mark 为锚：long `open-k*ATR14`，short `open+k*ATR14`，持仓期间固定不移动。
- 小时开盘跳过 stop 时按该小时 open 加不利滑点成交；否则小时 high/low 首次触及按 stop mark 加不利滑点成交。
- 同小时顺序固定为：日开盘状态切换 → gap stop → 该小时 funding → intrahour stop → 小时极值/close 记账。

### 3.2 快速 EMA 失效退出

- 对当前资产，long 在闭合日 `close<EMA(n)`、short 在 `close>EMA(n)` 时发出保护退出；下一日开盘执行。
- 若同一开盘 base target 已改变，优先按 base target 正常换仓，不记保护退出。
- 额外一日延迟压力测试同时延迟 base target 和 EMA exit；intrahour stop 不延迟。

### 3.3 再武装

保护退出后记录 `banned_state`：

- `state_change`：base target 至少出现一次不同状态后才清除；不同状态可当期开盘进入。
- `cooldown_K`：不同 base target 可立即进入；相同 banned state 只有经过 `K` 个完整 UTC 开盘后才可再入。
- 正常 base 换仓、flat 与终点平仓不产生 ban。

## 4. 冻结搜索空间

每个 control 全笛卡尔积后排除 `stop=0 && ema=0`，总计 `184` 个配置：

- `stop_atr ∈ {0,1.5,2.0,2.5,3.0,4.0}`；
- `fast_ema ∈ {0,5,10,20}`；
- `rearm ∈ {state_change,cooldown_3,cooldown_7,cooldown_14}`；
- `anchor ∈ {growth,risk}`。

先重放两个无保护 controls，并要求 equity 与 P0 ordered 结果分别精确对齐（容差 `1e-12`）。随后对 `184/184` 配置做 development ordered `1h` base 重放。

## 5. 硬门禁与排序

完全沿用 P0 第 5 节：base `>=20x/MDD<=20%`；stress `>=16x/MDD<=22%`；延迟 log-growth retention `>=70%`、`>=8x/MDD<=25%`；完整年与 rolling 365d 正收益比例均 `>=70%`；BTC/ETH participation、long/short、交易数与最大单笔正向 log-growth 集中度全部通过。

只有 base 两项先通过者才计算 stress/delay。完全同 trade path 去重后，唯一候选排序为：ordered MDD 降序、stress retention 降序、base equity 降序、交易数升序、参数字典序。

任一门禁失败即 `HARD-GATE-FAILED / explore / not promoted / not live-ready`；audit/prospective 保持封存，不登记版本。P1 失败后不得扩 stop/EMA 参数救援；必须停止该保护子机制并重新做因果归因。
