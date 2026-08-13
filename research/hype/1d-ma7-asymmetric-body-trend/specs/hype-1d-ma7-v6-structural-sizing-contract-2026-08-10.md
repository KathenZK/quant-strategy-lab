# HYPE 1D MA7 V6：结构性入场与仓位管理预注册合同

## 目标与研究边界

在冻结的 exact V6（OAPP + `PEHC_294`）之上，只检验上一轮诊断提出的四类结构修复：弱多头信号先小仓试探、short 退出后的方向性冷却、弱空头信号只用小仓、ATR 高波动时降低仓位。目标是全历史收益更高且真实 1h 顺序 MDD 更小。

本轮使用已经完全暴露的 `[0,432)` 历史，因此属于 post-reveal diagnostic，不登记新版本、不晋升、不进入 dry-run。不得在看到结果后增加阈值或组合。

## 冻结对照

- `CTRL_EXACT_V6`：冻结 exact V6，所有新增模块关闭。
- exact V6 原有 natural entry、OAPP、short RSI6 止盈、PEHC handoff、止损、资金费与退出顺序全部保持不变。
- 新引擎的 control 必须与原 exact V6 在 metrics、trades、actions/path 上逐项一致，否则整轮 `BLOCKED`。

## 新增 RSI6 记忆信号

沿用已完成的因果定义：cross 当日之前的 5 个完整日中，long 至少 3 日 `RSI6 < 30`，随后日收盘从 `<= MA7` 穿到 `> MA7`；short 对称为至少 3 日 `RSI6 > 70`，随后从 `>= MA7` 穿到 `< MA7`。只有该信号通过而 exact V6 natural entry 未通过时，才称为 memory-only 弱信号。

## 四类结构模块

### 1. Long probe + confirmation

- memory-only long 以 `0.50x` 或 `0.25x` 入场；native exact-V6 long 仍按 `1.00x`。
- `P05_C2`：`0.50x`，最多等待 2 个新完成日；`P025_C3`：`0.25x`，最多等待 3 个新完成日。
- 确认条件沿用 exact-V6 long 趋势质量但不再要求 fresh cross：完成日 `close > MA7`，且 `(MA7[t]-MA7[t-1])/ATR7[t] > 0.02`。
- 每日开盘先执行原 V6 的退出判断；只有仍持有 probe 才检查确认。确认通过时在该开盘补到目标仓位；截至允许的最后一个完成日仍未确认，则同一开盘平仓，原因 `probe_confirmation_expired`，随后使用原 long cooldown。

### 2. Asymmetric cooldown

- short 仓位退出后的 5 日 cooldown 继续禁止新的 natural short。
- 若 cooldown 期间出现 exact-V6 native long 或上述 memory-only long，则允许 long 在下一日开盘覆盖冷却；native long 用正常仓位，memory-only long 仍遵守 probe 仓位。
- long 退出后的原 2 日 cooldown 不变；forced reversal 与 PEHC handoff 的优先级及语义不变。

### 3. Short probe

- memory-only short 只以 `0.50x` 或 `0.25x` 入场，并在整笔交易中保持该目标仓位，不确认放大。
- native exact-V6 short、forced reversal、PEHC handoff 仍使用正常目标仓位。

### 4. ATR volatility cap

- 对原本目标为 `1.00x` 的入场或 long probe 的确认加仓，使用当时已知 `ATR7/entry_price` 计算：`cap = max(0.50, min(1.00, 0.05 / (ATR7/price)))`。
- 实际目标仓位为 `min(原目标仓位, cap)`；因此不会把 `0.25x/0.50x` probe 反向放大。
- 固定 `5%` 仅作为一个预注册结构诊断，不搜索其他阈值。

## 冻结实验臂

1. `CTRL_EXACT_V6`
2. `A_LONG_P05_C2`
3. `A_LONG_P025_C3`
4. `A_ASYM_CD`
5. `A_SHORT_P05`
6. `A_SHORT_P025`
7. `A_VOL_CAP_5PCT`
8. `B_LONG_P05_C2_ASYM`
9. `B_LONG_P05_C2_ASYM_VOL`
10. `B_CONSERVATIVE_ALL`：long `0.50x/2d` + short `0.25x` + asymmetric cooldown + volatility cap。

不运行全笛卡尔积，不从结果中追加实验臂。

## 数据、成本与审计

- Binance USD-M `HYPEUSDT` perpetual；完整 1h 聚合 UTC 日线。
- 全历史 `[0,432)`，2025-05-31 至 2026-08-05；终止成交为 2026-08-06 00:00 UTC open。
- 单仓、目标杠杆不超过 `1x`；日线 close 信号最早下一 UTC 日 open 成交。
- 手续费 `0.001/fill`，base 不利滑点 `4bps/fill`，计实际 funding；压力为 `8bps/fill`。
- 主风险使用真实 1h 路径顺序 MDD；另跑 8 个 54 日 cold-flat blocks，以及最近 `1d/7d/1m/3m/6m/1y` 切片。
- 输出每个实验臂的逐笔差异、模块激活计数、仓位事件和完整交易路径证据。

## 判定

只有某一冻结实验臂同时满足以下条件，才可作为后续候选保留：

1. 全历史收益严格高于 exact V6；
2. 全历史真实 1h MDD 严格小于 exact V6；
3. `8bps/fill` 下不出现收益与 MDD 双劣；
4. 8 个 cold-flat blocks 汇总不出现收益与 worst-block MDD 双劣；
5. 改善至少由 5 个独立交易 episode 支撑，且单一 episode 对总收益改善的贡献不超过 35%。

否则结论为 `FAIL / diagnostic-only`，不得命名或登记为 V7。
