# Binance 1D MA7 P2-H Finite Hourly Entry Confirmation 归因合同

## 1. 研究问题

P2-F/P2-G 已把共享 frontier 的主要风险定位为入场后前 `48h` 的方向错误；slow/vol/lifecycle、成交活跃度与 funding 均未形成跨资产稳定解释。P2-H 引入 materially new price-path entry mechanism：daily MA7 signal 保持不变，但不再无条件在原 next-open 成交，而是在有限 `1h` pending 窗内等待当时可知的方向确认。

本轮只做 trigger-order attribution，不运行完整 PnL、不改 exit/cooldown、不读取 audit/prospective。只有某个确认结构同时覆盖 BTC/ETH，才另立状态机合同。

## 2. 冻结样本

- 输入：[P2-G entry dataset](../artifacts/binance_1d_ma7_p2g_entry_information_2026-08-12_entries.csv)；
- pair-weighted 与 unique `(asset, side, entry_ts, stratum)` 两口径不变；
- original entry、original exit、`EARLY_TAIL<=-8%` 标签全部冻结；
- 每次确认从 original entry timestamp 开始，最迟在 `entry+24h` 前产生 candidate fill；超时即丢弃该次 signal，不延长、不跨 episode armed。

## 3. 三个固定确认结构

所有条件只在完整 `1h` close 后成立，并在下一根真实 `1h` open candidate fill：

1. `H1_POSITIVE_CLOSE`：第一根满足 `side × (hour_close - original_entry_price) > 0` 的小时；
2. `H2_POSITIVE_CLOSE`：连续两根完整小时 close 均位于 original entry price 的盈利侧；
3. `PDX_PRIOR_DAY_EXTREME`：hour close 突破 signal 可见最后完整 UTC 日的 high（long）或 low（short）。

不得加入 ATR buffer、成交量、funding、RSI、不同 long/short 阈值或结果后新增确认臂。若确认小时是 pending 窗最后一小时、下一根 open 已达到/超过 `entry+24h`，视为未确认。

## 4. 时序标签

对每笔 original entry 按 direct `1h` 顺序记录：

- `tail_hit_ts`：实际持仓内首次达到 `-8%` adverse 的小时；若 protective stop/early exit 先到，用实际 exit fill复核；
- `confirm_close_ts` 与 `candidate_fill_ts`；
- `TAIL_REJECTED`：original 是 EARLY_TAIL，且没有在 tail hit 之前产生 candidate fill；
- `NONTAIL_RETAINED`：original 不是 EARLY_TAIL，且在 `24h` 内、original exit 前产生 candidate fill；
- `WINNER_RETAINED`：original 最终 `net_return>0` 且 candidate fill有效；
- candidate delay、candidate fill相对 original fill的方向性滑点；
- 只作诊断的 candidate-to-original-exit gross return；它不替代完整 ledger 回测。

同一小时若既可能 tail hit 又可能确认，固定按保守 `adverse first` 处理，视为 tail 先发生；不得利用未知 OHLC 顺序把它算作成功确认。

## 5. 机制升级门

每个 arm 分别在 pair-weighted 与 unique-entry 口径计算 BTC/ETH asset overall，并按 side/stratum披露。允许进入完整 PnL 状态机必须同时满足：

1. 两资产 `TAIL_REJECTED>=60%`；
2. 两资产 `NONTAIL_RETAINED>=70%`；
3. 两资产 `WINNER_RETAINED>=75%`；
4. 两统计口径均过前三门；
5. 两资产 valid candidate 的 median delay `<=12h`；
6. calendar year 中至少 `70%` 年份同时满足 tail rejection `>=50%` 与 non-tail retention `>=60%`；年份 tail 样本 `<5` 时只披露、不进入分母。

若多个 arm 通过，先选两资产×双口径最弱 `TAIL_REJECTED` 最高者；并列再比较最弱 `WINNER_RETAINED`、最短 median delay，最终固定唯一机制。若无 arm 通过，关闭当前 finite hourly confirmation 线，不调 `24h` expiry、不加 ATR buffer、不混合多个 FAIL arm。

## 6. 后续 PnL 边界

归因 PASS 只授权实现，不是候选。完整 PnL 合同必须：

- exact P2-E control 与唯一确认机制 OAT；
- 正确处理 pending、原 signal失效、持仓占用、exit、stop、funding、cooldown 与 terminal flatten；
- shared BTC/ETH 参数、closed-hour/next-hour-open、真实 ordered `1h` MDD、约 `1x`；
- development 两资产各 `>=20x / MDD<=20%`；
- stress/delay/calendar/rolling 通过后才允许一次性打开 researcher-exposed audit。

P2-H 状态固定为 `explore / not promoted / not live-ready`，不得登记 V2。
