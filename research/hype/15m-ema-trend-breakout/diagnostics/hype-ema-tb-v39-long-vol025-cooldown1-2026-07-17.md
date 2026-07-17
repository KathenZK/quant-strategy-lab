# HYPE-EMA-TB-V39 多头量能对齐 V35 与 cooldown1 交互诊断

日期：2026-07-17  
状态：V39.2 supporting evidence / registered / not promoted / not live-ready

## 结论

将 V39 多头量能门槛从 `0.35` 放宽到 V35 的 `0.25` 后：

1. **只放宽量能、不加冷却：略差于当前 V39。**
   - 当前 V39：`+8430.39% / -27.26% / Sharpe 4.57 / 109 笔 / 胜率 77.98%`。
   - `long_vol_min=0.25`：`+8018.42% / -27.26% / Sharpe 4.51 / 110 笔 / 胜率 77.27%`。
   - 最终资金保留 `95.17%`，没有回撤改善。
2. **放宽量能并加入 cooldown1：能修复当前 V39 + cooldown1 的路径失败，并在 full 上超过当前 V39。**
   - `long_vol_min=0.25 + cooldown1`：`+8922.26% / -24.61% / Sharpe 4.66 / 108 笔 / 胜率 79.63%`。
   - 相对当前 V39，最终资金为 `105.77%`，MaxDD 改善 `2.65pp`，Sharpe 提高 `0.09`，胜率提高 `1.65pp`。

但组合最近 `3m/6m` 收益均低于当前 V39，且 cooldown1 在相邻参数上没有稳健平台。用户随后指定将该联合状态机登记为 `HYPE-EMA-TB-V39.2`；登记只冻结研究身份，不覆盖 V39，不更新 live spec 或 runner。

## 数据与口径

- Exchange / market：Binance USD-M perpetual。
- Symbol / timeframe：`HYPEUSDT` / `15m`。
- Closed-bar 数据范围：`2025-05-30 10:30 UTC` 至 `2026-07-16 15:30 UTC`，`39,573` 根。
- 数据质量：无缺口、无重复时间戳、无关键空值、OHLC 合法；raw/normalized 对齐且无差异。
- 成本：每次 fill 合计 `0.00085`（手续费与 adverse slippage），另计 Binance funding。
- 唯一量能变更：`long_vol_min 0.35 -> 0.25`；保留 V39 的 `short_target_atr_pct=0.022` 与 `short_use_h1_ema=False`。
- Cooldown1：平仓发生在 `E`，禁止 `E+1` 开仓，最早允许 `E+2 open` 开仓。
- 其余 V39 规则不变：K0/K1/K2 时序、`5ATR TP / 7ATR SL`、`ADX22 delayed3`、`MFE>=1.5ATR` 后禁用指标退出、`384` 根 timeout、`3.0x` allocation cap。
- 当前 V39 base 与放宽量能 base 均分别通过 canonical parity，最大逐 K 权益差异为 `0`。

## 四路对照

| 变体 | Full 收益 | MaxDD | Sharpe | 交易数 | 胜率 | 当前 V39 最终资金比 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 当前 V39 | `+8430.39%` | `-27.26%` | `4.57` | `109` | `77.98%` | `100.00%` |
| 当前 V39 + cooldown1 | `+5549.98%` | `-32.59%` | `4.23` | `107` | `76.64%` | `66.23%` |
| V39 + `long_vol_min=0.25` | `+8018.42%` | `-27.26%` | `4.51` | `110` | `77.27%` | `95.17%` |
| V39 + `long_vol_min=0.25` + cooldown1 | **`+8922.26%`** | **`-24.61%`** | **`4.66`** | `108` | **`79.63%`** | **`105.77%`** |

组合相对当前 V39 将 stop loss 从 `15` 笔降至 `14` 笔，take profit 从 `83` 笔变为 `82` 笔，平均单笔收益从 `4.75%` 提高到 `4.83%`。

## 最近分片

| 窗口 | 当前 V39 收益 / MaxDD / 平仓数 | `vol025 + cooldown1` |
| --- | ---: | ---: |
| `1d` | `+0.12% / -2.88% / 1` | `+0.12% / -2.88% / 1` |
| `7d` | `-15.28% / -22.94% / 2` | `-15.28% / -22.94% / 2` |
| `1m` | `-16.51% / -23.96% / 6` | `-13.39% / -23.40% / 6` |
| `3m` | `+120.52% / -27.26% / 34` | `+96.81% / -24.61% / 30` |
| `6m` | `+1482.11% / -27.26% / 67` | `+1249.11% / -24.61% / 65` |
| `1y` | `+7842.96% / -27.26% / 103` | `+8455.56% / -24.61% / 101` |

组合改善 full、1y、1m 和各自回撤，但最近 `3m/6m` 收益分别少 `23.71pp / 233.00pp`。这不是所有窗口一致占优的替代版本。

## 交互原因

当前 V39 + cooldown1 的失败不是 cooldown 本身独立造成，而是 cooldown 与更严格多头量能门槛共同决定了下一次可入场 bar：

- `2026-05-24`：严格量能 + cooldown1 延至 `10:15 UTC` 入场并 stop loss `-14.16%`；量能对齐 V35 后可在 `10:00 UTC` 入场，最终 indicator exit `+0.55%`。
- `2026-06-15`：严格量能 + cooldown1 延至 `11:15 UTC`，最终 indicator exit `-5.30%`；放宽后可在 `11:00 UTC` 入场并 take profit `+9.64%`。

量能放宽单独并不提升 V39，但它改变 cooldown1 后的可执行再入场位置，避免了两次严重路径翻转。因此该结果必须视为**联合状态机候选**，不能拆解成“量能门槛越低越好”或“cooldown1 普遍有效”。

## 决定

1. 当前 V39 参数保持不变。
2. `long_vol_min=0.25 + cooldown1` 已按用户指定登记为 `HYPE-EMA-TB-V39.2`，状态为 `registered / not promoted / not live-ready`；冻结规格见 [hype-trend-strategy-v39-2-spec.md](../specs/hype-trend-strategy-v39-2-spec.md)。
3. 若继续推进，必须等待新增 OOS 交易，并做 entry phase、跨所迁移及 live-executable 对拍。当前结果不能用于修改 runner。

## 产物

- 复现脚本：[research_hype_ema_tb_v39_long_vol025_cooldown1.py](../scripts/research_hype_ema_tb_v39_long_vol025_cooldown1.py)
- 汇总 JSON：[hype_ema_tb_v39_long_vol025_cooldown1_2026-07-17.json](../artifacts/hype_ema_tb_v39_long_vol025_cooldown1_2026-07-17.json)
- 逐笔交易：[hype_ema_tb_v39_long_vol025_cooldown1_2026-07-17_trades.csv](../artifacts/hype_ema_tb_v39_long_vol025_cooldown1_2026-07-17_trades.csv)
- 权益曲线：[hype_ema_tb_v39_long_vol025_cooldown1_2026-07-17_equity.csv](../artifacts/hype_ema_tb_v39_long_vol025_cooldown1_2026-07-17_equity.csv)
