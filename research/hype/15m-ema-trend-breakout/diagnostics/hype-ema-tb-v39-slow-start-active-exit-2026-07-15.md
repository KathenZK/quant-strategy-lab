# HYPE-EMA-TB-V39 慢启动交易主动退出回测

日期：2026-07-15

## 结论

按 V39 的完整参数和信号定义复测：

> 持仓 `6–8h` 且历史 `MFE<1.5ATR`，下一根 15m K 开盘主动退出。

结果与 V35 一致，而且资金保留率更差：**不能加入 V39，也不应修改当前包含 V39 趋势腿的组合 dry-run。**

- V39 base：`+8789.36% / -23.46% / Sharpe4.62 / 胜率78.70%`。
- `6h + MFE<1.5ATR`：`+5324.46% / -23.46% / 4.24 / 72.57%`，最终资金仅保留 `61.02%`。
- `8h + MFE<1.5ATR`：`+6574.67% / -23.88% / 4.38 / 75.45%`，最终资金保留 `75.09%`。
- 6h/8h 规则分别触发 `13 / 9` 笔；与 V35 一样，6h 误杀 5 笔最终 TP5，8h 误杀 2 笔。
- 加入同向 entry-signal episode reset 仍只有 `61.49% / 68.44%` 资金保留率，没有解决问题。
- 最窄 `6h + MFE<1ATR` 也只保留 `94.16%`；10h/12h 版本仅触发 2/1 笔，收益仍低于 base，且没有风险改善。

本轮不修改 V39 研究定义，不修改 `HYPE-15M-TB-MII-ENS-V2` dry-run 配置，不登记新版本。

## Dry-run 身份边界

当前实际 dry-run 的完整策略身份是：

- `HYPE-15M-Trend-Breakout-Multi-Indicator-Ensemble-V2`；
- 组合定义：`HYPE-EMA-TB-V39 + HYPE-15M-MII-V1.4`；
- 单账户 `single_v39_priority_k1`；
- V39 是优先趋势腿，MII V1.4 是次级反转腿。

独立母版本 `HYPE-EMA-TB-V39` 在 EMA-TB 家族主账中仍是 `registered / not promoted / not live-ready`；它不是独立 dry-run 服务。用户所说“V39 已在 dry-run”在运行层面成立，准确表述是“V39 正作为组合 V2 的趋势腿参与 production dry-run”。

如果改变 V39 腿规则，实际是在改变组合 V2 的交易状态机和已通过 replay parity 的 runner 路径，必须新建组合版本或明确登记配置变更，重新执行组合回放、preempt 路径、runner parity 和 dry-run 对账。由于本轮单腿回测已显著失败，没有理由把规则注入组合层。

组合状态依据：

- [HYPE-15M-TB-MII-ENS README](../../15m-trend-breakout-multi-indicator-ensemble/README.md)
- [HYPE-15M-TB-MII-ENS Core Ledger](../../15m-trend-breakout-multi-indicator-ensemble/hype-15m-tb-mii-ens-core-ledger.md)

## 数据与执行口径

- Exchange：Binance。
- Market：USD-M perpetual。
- Symbol：`HYPE/USDT:USDT`。
- Timeframe：`15m`。
- 数据源：Binance public API。
- UTC 范围：`2025-05-30 10:30` 至 `2026-07-15 03:15`。
- 已闭合 K 线：`39,428` 根；缺口 `0`、重复 `0`、关键空值 `0`、无效 OHLC `0`。
- Funding：Binance funding，按 15m 时间轴对齐。
- 成本：V39 canonical `0.00085`/fill，包含手续费与 `4 bps` adverse slippage；另计 funding。
- V39 参数差异：V35 基础上 `long_vol_min=0.35`、`short_target_atr_pct=0.022`，移除空头 1h EMA 确认。
- 入场：K0 close 信号，跳过 K1，K2 open 入场。
- 原始退出：固定 entry ATR `5ATR TP / 7ATR SL`，`ADX<22 delayed3`；`MFE>=1.5ATR` 后关闭指标退出。
- 主动退出：已完成 K 收盘后检查持仓时间和历史 MFE，下一根 K open 成交。
- Reset 版本：主动退出后禁止同向重入，直到 delayed V39 entry signal 首次变为 false。
- 引擎校验：关闭规则后与 canonical V39 逐笔交易和指标完全一致，parity `PASS`。
- 选择披露：规则来自 V35 的同日 post-hoc 条件统计，迁移到 V39 仍属于 post-hoc transfer diagnostic。

## 核心结果

| 规则 | Full 收益 | 资金保留率 | MaxDD | Sharpe | 胜率 | 主动退出 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| V39 base | +8789.36% | 100.00% | -23.46% | 4.62 | 78.70% | 0 |
| `6h + MFE<1.0` | +8270.59% | 94.16% | -23.46% | 4.58 | 77.27% | 5 |
| **`6h + MFE<1.5`** | **+5324.46%** | **61.02%** | **-23.46%** | **4.24** | **72.57%** | **13** |
| `8h + MFE<1.0` | +6856.99% | 78.26% | -23.88% | 4.41 | 77.06% | 4 |
| **`8h + MFE<1.5`** | **+6574.67%** | **75.09%** | **-23.88%** | **4.38** | **75.45%** | **9** |
| `10h + MFE<1.5` | +8534.88% | 97.14% | -23.46% | 4.60 | 78.70% | 2 |
| `12h + MFE<1.5` | +8595.66% | 97.82% | -23.46% | 4.60 | 78.70% | 1 |
| `6h + MFE<1.5 + reset` | +5366.36% | 61.49% | -23.46% | 4.25 | 72.97% | 13 |
| `8h + MFE<1.5 + reset` | +5983.51% | 68.44% | -23.88% | 4.30 | 75.23% | 9 |

## 最近分片

| 窗口 | V39 收益 / MaxDD | 6h 规则 | 8h 规则 |
| --- | ---: | ---: | ---: |
| 1d | -16.26% / -16.26% | -16.26% / -16.26% | -16.26% / -16.26% |
| 7d | -11.72% / -17.21% | -11.72% / -17.21% | -11.72% / -17.21% |
| 1m | +8.94% / -21.85% | +10.02% / -21.08% | +6.11% / -23.88% |
| 3m | +136.72% / -21.90% | +137.11% / -21.90% | +121.70% / -23.88% |
| 6m | +1683.83% / -22.58% | +1303.73% / -22.61% | +1580.40% / -23.88% |
| 1y | +8177.20% / -23.08% | +5026.22% / -23.08% | +6115.61% / -23.88% |

6h 版本最近 1m/3m 的轻微改善不能抵消 6m、1y 和 full 的巨大损失；8h 版本近期和长期均更差。

## 路径解释

6h 触发的 13 笔在原 V39 中：

- 5 笔最终 TP5；
- 7 笔 indicator exit；
- 1 笔 SL7。

代表性误杀：

- 2025-09-22 空单：6h 主动退出 `-4.70%`，原 V39 TP5 `+9.03%`；
- 2025-10-25 多单：`-4.48%`，原 V39 TP5 `+9.84%`；
- 2025-12-03 多单：`-1.86%`，原 V39 TP5 `+9.52%`；
- 2026-03-01 多单：`-0.83%`，原 V39 TP5 `+9.41%`；
- 2026-03-16 多单：`-2.90%`，原 V39 TP5 `+9.69%`。

唯一明显改善的原 SL7 交易仍是 2026-04-07 多单：`-9.66% -> -1.85%`。一次止损减损无法抵消五笔延迟 TP5 被改造成亏损。

最新 `4.83ATR -> SL7` 空单不会触发本规则，因为它在 6h 之前已经超过 `1.5ATR`；因此慢启动规则也不处理用户最初关心的 high-MFE giveback。

## 判断

1. V39 的入场过滤和空头 sizing 变化没有改变结论：慢启动固定时钟仍会截断延迟赢家。
2. Reset 版本失败，说明问题不是立即同向重入，而是主动退出条件本身缺乏判别力。
3. 当前 V2 dry-run 已完成组合 replay parity；不应为了一个单腿显著失败的 post-hoc 规则破坏已验证路径。
4. 保持 V39 与组合 V2 dry-run 当前规则，继续收集 runner-tracking，而不是修改退出状态机。

## 证据

- 复现脚本：[research_hype_ema_tb_v39_slow_start_exit.py](../scripts/research_hype_ema_tb_v39_slow_start_exit.py)
- 汇总 JSON：[hype_ema_tb_v39_slow_start_exit_2026-07-15.json](../artifacts/hype_ema_tb_v39_slow_start_exit_2026-07-15.json)
- 逐笔交易：[hype_ema_tb_v39_slow_start_exit_2026-07-15_trades.csv](../artifacts/hype_ema_tb_v39_slow_start_exit_2026-07-15_trades.csv)
- 权益曲线：[hype_ema_tb_v39_slow_start_exit_2026-07-15_equity.csv](../artifacts/hype_ema_tb_v39_slow_start_exit_2026-07-15_equity.csv)
