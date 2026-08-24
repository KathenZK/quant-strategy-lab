# HYPE-1D-MA7-ABT-V7.1 Runner Strict Parity

## 结论

`PASS`。`quant-runner` 的 20 笔输出与 V7/V7.1 canonical 20 笔逐字段一致：

- side；
- entry / exit timestamp；
- entry / exit reference price；
- bars held；
- exit reason；
- raw net PnL；
- raw net return。

`full_trade_matches=20`，mismatch `0`。这只解除实现对拍 blocker，不改变 `registered / not promoted / not live-ready`，也不授权 dry-run 或 live 启用。

## 来源与窗口

- Runner repo：`/Users/ZK/OpenCode/quant-runner`
- Runner kind：`hype_1d_ma7_abt`
- Runner config：`configs/dryrun.toml` 中 disabled `hype-1d-ma7-abt-v7-1-dry-run`
- Canonical source：[`hype_1d_ma7_abt_v7_short_cooldown3_2026-08-11.json`](../artifacts/hype_1d_ma7_abt_v7_short_cooldown3_2026-08-11.json)
- Canonical SHA256：`d7fbcdcb911c0fb7bda9cfdb08f6717b6d0b016be8b8ede380702f5eed28e324`
- Runner fixture：`crates/quant-runner/src/runner/strategies/hype_1d_ma7_abt/replay.rs::EXPECTED_TRADES`
- Runner evidence：[`hype_1d_ma7_abt_v7_1_runner_strict_parity_2026-08-12.json`](../artifacts/hype_1d_ma7_abt_v7_1_runner_strict_parity_2026-08-12.json)
- Observation window：`2025-05-31T00:00:00Z` inclusive → `2026-08-06T00:00:00Z` exclusive
- Data snapshot：432 closed `1d` bars、10,368 closed `1h` bars、2,591 Binance funding events
- Command：`DINGTALK_WEBHOOK_URL=https://example.com cargo run -q -p quant-runner -- replay-dry-run --config configs/dryrun.toml --name hype-1d-ma7-abt-v7-1-dry-run --limit 500 --start-ts 2025-05-31T00:00:00Z --end-ts 2026-08-06T00:00:00Z`

## 逐笔对账

下表每一行均为 `expected == actual`。`ID` 是稳定的 canonical trade index。

| ID | Side | Entry timestamp / price | Exit timestamp / price | Bars | Exit reason | Net PnL | Net return |
| ---: | --- | --- | --- | ---: | --- | ---: | ---: |
| 01 | long | `2025-06-10T00:00Z` / `38.848` | `2025-06-13T00:00Z` / `40.52` | 3 | `long_mfe_fraction_trail_exit` | `0.03774949053177923` | `3.774949053177923%` |
| 02 | long | `2025-06-28T00:00Z` / `36.623` | `2025-07-06T00:00Z` / `39.137` | 8 | `long_mfe_fraction_trail_exit` | `0.06494387336239638` | `6.258145530778991%` |
| 03 | long | `2025-07-10T00:00Z` / `40.671` | `2025-07-16T00:00Z` / `47.865` | 6 | `long_mfe_fraction_trail_exit` | `0.1884341855330962` | `17.088538999422154%` |
| 04 | short | `2025-07-18T00:00Z` / `45.589` | `2025-08-03T00:00Z` / `36.898` | 16 | `short_rsi_take_profit` | `0.24827394979673767` | `19.22923493553126%` |
| 05 | long | `2025-08-27T00:00Z` / `48.796` | `2025-09-14T00:00Z` / `54.457` | 18 | `long_mfe_fraction_trail_exit` | `0.16067586850583915` | `10.437554373360913%` |
| 06 | long | `2025-09-18T00:00Z` / `57.767` | `2025-09-20T18:00Z` / `54.67535714285714` | 2 | `protective_stop` | `-0.1015628316296735` | `-5.974012333644119%` |
| 07 | short | `2025-09-20T18:00Z` / `54.653` | `2025-10-01T00:00Z` / `45.221` | 11 | `ma7_slope_exit` | `0.2811903586153308` | `17.590728908936826%` |
| 08 | short | `2025-10-15T00:00Z` / `39.393` | `2025-10-19T00:00Z` / `36.862` | 4 | `ma7_slope_exit` | `0.11510436706588911` | `6.123533932878877%` |
| 09 | long | `2025-10-24T00:00Z` / `40.199` | `2025-11-01T00:00Z` / `43.684` | 8 | `long_mfe_fraction_trail_exit` | `0.1652257286995369` | `8.282783314931463%` |
| 10 | short | `2025-11-03T00:00Z` / `42.443` | `2025-11-11T00:00Z` / `41.444` | 8 | `ma7_slope_exit` | `0.049790032068715906` | `2.3050567369573116%` |
| 11 | short | `2025-11-21T00:00Z` / `37.542` | `2025-11-23T00:00Z` / `29.977` | 2 | `short_rsi_take_profit` | `0.4398774467388824` | `19.905532892887656%` |
| 12 | short | `2025-12-06T00:00Z` / `30.965` | `2025-12-19T00:00Z` / `22.459` | 13 | `short_rsi_take_profit` | `0.7275790054716991` | `27.45889449493779%` |
| 13 | short | `2025-12-24T00:00Z` / `23.956` | `2025-12-25T00:00Z` / `25.156` | 1 | `ma7_slope_exit` | `-0.17799604595538998` | `-5.270394170152104%` |
| 14 | long | `2026-01-27T00:00Z` / `24.93` | `2026-01-30T01:00Z` / `30.112071428571426` | 3 | `protective_stop` | `0.6549772904487083` | `20.472611932389828%` |
| 15 | long | `2026-03-01T00:00Z` / `31.204` | `2026-03-21T00:00Z` / `39.528` | 20 | `long_mfe_fraction_trail_exit` | `1.0084417396015573` | `26.1643228045664%` |
| 16 | short | `2026-03-23T00:00Z` / `38.342` | `2026-03-29T00:00Z` / `39.462` | 6 | `ma7_slope_exit` | `-0.15114009170085296` | `-3.1081488291072934%` |
| 17 | long | `2026-05-15T00:00Z` / `44.125` | `2026-05-28T00:00Z` / `57.747` | 13 | `long_mfe_fraction_trail_exit` | `1.4456002209447956` | `30.68195843874095%` |
| 18 | short | `2026-06-05T00:00Z` / `64.439` | `2026-06-14T00:00Z` / `60.682` | 9 | `ma7_slope_exit` | `0.34491494517040255` | `5.601847087814993%` |
| 19 | long | `2026-07-03T00:00Z` / `66.926` | `2026-07-08T00:00Z` / `69.187` | 5 | `long_mfe_fraction_trail_exit` | `0.19249513434313403` | `2.9605164525931427%` |
| 20 | short | `2026-07-12T00:00Z` / `66.743` | `2026-08-01T00:00Z` / `52.559` | 20 | `max_hold` | `1.4159350695605015` | `21.150485876430625%` |

## 汇总指标

- Equity multiple：`8.11035936775286`
- Net return：`711.035936775286%`
- Chronological 1h MDD：`-18.395542229660567%`
- Daily MDD：`-15.426995737690197%`
- Cost / initial equity：`16.72696722738397%`
- Funding / initial equity：`-1.3232555109724276%`
- Profit factor：`17.509233233044547`
- 8bps stress：`698.7499654030659%` / `-18.52798408021893%`

上述 headline 与冻结目标的比较容差为 `1e-9`，实际 delta 为 `0`。

## 执行字段说明

- Signal/bar timestamp：自然 entry/日线 exit 只读取前一完整 UTC 日；保护与 PEHC 读取闭合 `1h`。逐笔 fixture 冻结 execution timestamp，因 canonical trade schema 未单列 signal timestamp，报告不伪造额外字段。
- Quantity/notional：canonical trade fixture 未导出逐笔 quantity/notional；chronological accounting 按当时 equity、old quantity、target side、price、cost rate、`1x` leverage 迭代求 target quantity。该路径已通过每笔 PnL 与 headline cost/equity 双重对拍。
- Fees：`0.001` × filled notional / fill。
- Slippage：主结果每 fill 不利 `4bps`；stress 每 fill 不利 `8bps`。
- Funding：按 Binance 原始 funding timestamp/rate，在持仓事件顺序中结算。
- Order ID：离线 replay 不提交订单，因此无 exchange order ID；稳定事件 ID 使用表中 canonical trade index `01`–`20`。
- Actual live fills：本报告没有真实订单、DB 或线上日志，不可替代后续 online open/close reconciliation。

## Runtime 合同修正

- side-specific cooldown 改为 canonical global flat-day cooldown；
- 删除持仓中普通 opposite reclaim 的 `Replace` 反手；
- long entry 不再虚构 `1.5 ATR` hard stop，首个日线 trail 前保持 strategy-managed；
- dry-run protection touch 改用 closed `1h` mark candle；
- long protective stop 后 forced short 只使用上一完整日 SMA7 资格；
- OAPP/short RSI profit exit 优先；native 内部按 MA boundary、short slope、max hold；
- PEHC 只在无同时 native exit 的纯 long OAPP 退出后建立 shadow；
- PEHC 使用 `1h` shadow stop、单次消费、opportunity check 与 next-UTC-open recheck；
- accounting 使用 canonical chronological event order，并单独复算 raw trade PnL。

## 2026-08-13 runtime 修补（不改变 20 笔 parity）

canonical 20 笔仍以独立 `replay.rs` Engine 为准，本条只记录 runtime Driver/kernel 合同修补：

- dry-run TouchOnly 原因 `stop` 与 live `stop_market` 都点亮多头保护止损后的 forced short；
- `1h` 保护序列或 mark 缺失时 fail-closed，禁止回退日线 OHLC；漏掉的已闭合 `1h` 按 `last_protection_poll_ts` 顺序补检；无 cursor 时只检查最新一根；
- `pending_forced_short` / `pehc_pending_due_ts` 在 `Opened` 前保留；拒绝 forced short 立即 Hold 并写入多头冷却；
- 持仓中日线软出场不再因 `1h` 失败而硬中断；
- PEHC 到下一 UTC 00:00 后发 `Immediate`，不是 1d `NextOpen`。

## 剩余门禁

- 不发布、不部署、不启用 dry-run/live；
- `enabled_allowed=false`、`approval_level=none`；
- 仍需 clean prospective、dry-run observer、真实开平仓/资金费/费用对账、tiny-live 资金边界和独立 launch decision；
- 任何启用或发布仍需用户明确批准。
