# BIN-1D-BE-DHCT P0 冻结合同

## 1. 身份与假设

- Family：`Binance-1D-BTCETH-Dual-Horizon-Campaign-Trend`
- Short id：`BIN-1D-BE-DHCT`
- 假设：BTC/ETH 同时处于慢周期上行或下行状态时，快周期突破更可能属于可持续 campaign；共同状态未确认或转 neutral 时不应新开仓，并应退出已有仓位。
- 与 CBCT 的边界：CBCT 用同日 peer EMA breadth 过滤每次突破；DHCT 维护有确认、迟滞和 neutral 的跨日 campaign state，state 是 entry admission 与 exit invalidation 的共同来源。

## 2. 数据治理

- 复用已审计 BTC/ETH 直接 `1h`、actual funding/mark 与 P0 frame hashes。
- development `[2019-12-24,2025-08-07)`；researcher-exposed audit `[2025-08-07,2026-08-10)` sealed。
- prospective 首个 eligible closed day `>=2026-08-13`，首次 next-open `>=2026-08-14 00:00 UTC`。
- 所有搜索、排名、继续/停止只使用 development；只有唯一候选通过全部开发门才允许一次性打开 audit。

## 3. 慢周期 campaign state

对 BTC、ETH 各计算 `EMA(regime_ema)`，`adjust=False`、完整 span 后有效：

- raw long：两资产均 `close>EMA`，且各自 `EMA[t]>EMA[t-slope_days]`；
- raw short：两资产均 `close<EMA`，且各自 `EMA[t]<EMA[t-slope_days]`；
- 其余为 raw neutral。

state 初始 neutral。raw 与当前 state 不同时，只有连续 `regime_confirm` 个完整日相同，次日才更新为 long/short/neutral；中途变化则 streak 重置。state 使用当日收盘形成，只能影响下一 open。

## 4. 快周期 entry 与单仓竞争

- 只在 active long/short state 内寻找同方向突破；long 为候选资产 `close > prior breakout_n-day high`，short 为 `close < prior breakout_n-day low`。
- 以突破距离除 `ATR14` 排序；两资产同日均候选时选 score 较高者，完全相同固定 BTC 优先。
- closed-day signal，下一 UTC 日 open 建立固定约 `1x` 数量；持仓期不 resize、不加仓。
- 平仓后至少等待 `cooldown_days` 才可消费新 signal；无 pending 追单。

## 5. Exit 与风险

- campaign state 在完整日收盘后变为 neutral 或反向时，当前仓位下一日 open 退出；同日不直接反手。
- 真实 `1h` chandelier 固定 `5×ATR14`：入场日收盘形成首个 level，次日 `00:00` 起生效，只向盈利方向移动；gap 按小时 open，否则按 stop mark，不利滑点。
- 固定 profit protection 来自 CBCT P1 development evidence：entry `ATR14`，MFE activation `1ATR`、giveback `35%`、连续 `2d` close 确认、次日 open 退出。
- 同一日收盘优先级：profit protection → campaign invalidation；小时 stop 更早执行。
- profit protection 参数在 P0 不搜索；它不是 clean OOS 结论，也不允许事后修改。

## 6. 冻结参数面

- `regime_ema ∈ {100,200,300}`；
- `slope_days ∈ {20,60}`；
- `regime_confirm ∈ {1,3}`；
- `breakout_n ∈ {20,40,60}`；
- `cooldown_days ∈ {0,3,7}`；
- 共 `3×2×2×3×3 = 108` 个配置。

## 7. 成本、回撤与门禁

- fee `0.001/fill`；base/stress slippage `4/8bps/fill`；actual funding按真实事件时点计入。
- ordered MDD 使用直接 `1h` 顺序；小时内保守 `favorable → adverse → close`，不得用日线 high/low 猜顺序。
- hard target：base `>=20x/MDD<=20%`。
- 通过 base 后还须：stress `>=16x/MDD<=22%`；`+1d` daily-order delay 的 log-growth retention `>=70%`、`>=8x/MDD<=25%`；完整年/rolling 365d 正收益比例均 `>=70%`；closed trades `>=20`，BTC/ETH、long/short各`>=5`；最大单笔正 log-growth 占比 `<=30%`。
- 同路径去重后按 MDD、stress retention、equity、交易数和参数字典序选唯一候选。
- `0` 个通过即 `HARD-GATE-FAILED`并关闭 family；不扩 EMA/slope/breakout/cooldown，不改 profit protection，不用 leverage/vol target。

## 8. 固定交付

- state transition、entry selection、next-open invalidation 与 profit-protection 单元测试；
- `108` 路搜索 JSON/CSV、frontier attribution、完整交易路径 HTML；
- 中文诊断、core ledger、decision log 与两级索引；
- audit/prospective reveal 必须保持 `false`，除非 development 全门通过。
