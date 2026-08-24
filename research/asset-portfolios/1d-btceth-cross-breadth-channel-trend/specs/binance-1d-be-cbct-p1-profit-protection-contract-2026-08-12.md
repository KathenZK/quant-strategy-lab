# BIN-1D-BE-CBCT P1 浮盈保护冻结合同

## 1. 身份与研究问题

- Family：`Binance-1D-BTCETH-Cross-Breadth-Channel-Trend`
- Campaign：`P1 profit-protection OAT`，不是版本登记。
- Exact control：P0 growth frontier：`entry20 / exit10 / EMA50 / trail5ATR / confirm2 / cooldown7 / maxhold120`。
- 研究问题：在不改变 entry、cross breadth、chandelier、channel、cooldown 与仓位的前提下，仅加入“已有浮盈后的 MFE fraction giveback”，能否显著降低 ordered `1h` MDD并保留主要 log-growth。

P0 已证明 tighter chandelier 会把 MDD降至 `-27.88%`，但终值仅 `1.66x`；P1 不继续搜索 chandelier 参数，而是检验与 HYPE OAPP 方法同类、但参数和结论独立生成的 profit protection。

## 2. 数据与封存

- 复用 P0 同一冻结直接 `1h`、实际 funding/mark、frame hash 与 development `[2019-12-24,2025-08-07)`。
- researcher-exposed audit `[2025-08-07,2026-08-10)` 与 prospective 保持 sealed。
- 所有参数、优先级、soft-continue 与停止规则在读取 P1 结果前固定。

## 3. Exact control 与唯一改动

Exact control 完全沿用 P0：闭合日线信号、next-open、单一固定约 `1x` 仓位、真实 `1h` stop、`0.001/fill + 4bps/fill + actual funding`。

P1 只增加以下状态：

1. 每笔交易从 entry fill 起累计 favorable extreme；long 取截至当日的最高价，short 取最低价。
2. 使用入场日 `ATR14` 固定归一化。只有 MFE 达到 `activation_atr × entry_ATR14` 后保护才 armed。
3. armed 后，long threshold 为 `entry_fill + (1-giveback)×MFE`；short 为 `entry_fill - (1-giveback)×MFE`。
4. 每个完整 UTC 日收盘检查；连续 `confirm_days` 个收盘越过 threshold 才产生退出信号，下一 UTC 日 open 成交。
5. 当日未满足时 streak 清零；threshold 随 favorable extreme 单向推进。
6. 入场日可以累计 MFE并在收盘形成信号，但不得 intraday 触发；最早退出为入场次日 open。
7. 日收盘同时满足 profit protection 与 channel/timeout 时，退出成交相同，但 reason 优先记为 `profit_protection`；真实小时 stop 在日内优先。
8. profit protection 退出后完全沿用 control 的 `7d` cooldown；本轮不加入 shadow、handoff、pending 或快速 re-entry。

## 4. 冻结参数面

- `activation_atr ∈ {1.0, 2.0, 3.0}`；
- `giveback ∈ {0.20, 0.35, 0.50}`；
- `confirm_days ∈ {1, 2}`；
- 共 `18` 个 P1 配置，加 exact control 共 `19` 条评估路径；同路径去重只用于报告，不减少已冻结执行数。

## 5. 成交与回撤顺序

- 每小时：日开盘 pending order → funding → active chandelier stop → conservative `high → low → close` 账户路径；short 仍使用方向化 favorable/adverse 对应。
- profit protection 只在完整日收盘后生成 next-open pending exit，不使用当日未闭合信息。
- base `4bps/fill`；只对通过 base soft-continue 的唯一去重路径补跑 `8bps/fill` 与额外 `+1d` daily-order delay。

## 6. 门禁与停止规则

Hard target 不变：净终值 `>=20x` 且 ordered `1h` MDD `<=20%`，随后还须通过 P0 的 stress/delay/calendar/rolling/capacity/concentration 门。

P1 soft-continue 必须同时满足：

- base 净终值 `>=10x`；
- 相对 control 的 log-growth retention `>=85%`；
- ordered MDD `<=35%`，且相对 control 至少改善 `10pp`；
- closed trades `>=20`，BTC/ETH 与 long/short 各至少 `5`；
- 最大单笔正 log-growth 占比 `<=35%`；
- `8bps` 与 `+1d` delay 均为正，且不得出现 intraday bankruptcy。

若 `0` 个去重路径通过 soft-continue：P1 `HARD-GATE-FAILED`，关闭 CBCT family；不得继续搜索 giveback 邻域，不得加入 handoff/re-entry/RSI 组合救援。只有 profit protection 本身通过 soft-continue，才允许另行冻结 handoff continuity 合同。

## 7. 固定交付

- exact control parity、19 路 metrics、交易签名与 exit-reason attribution；
- growth/risk/soft frontier 的完整交易路径 HTML（若路径重复则明确去重）；
- 合同、脚本、测试、JSON/CSV、中文诊断、core ledger 与索引更新；
- audit/prospective reveal 字段必须保持 `false`。
