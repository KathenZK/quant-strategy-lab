# HYPE-EMA-TB-V39 平仓后冷却 1 根诊断

日期：2026-07-17  
状态：diagnostic only / not registered / not promoted / not live-ready

## 结论

**V35 上样本内表现最好的 cooldown1 不能迁移到 V39。**

- V39 base：`+8430.39% / -27.26% / Sharpe 4.57 / 109 笔 / 胜率 77.98%`。
- V39 + cooldown1：`+5549.98% / -32.59% / Sharpe 4.23 / 107 笔 / 胜率 76.64%`。
- 最终资金只保留 base 的 `66.23%`，最大回撤恶化 `5.33pp`，Sharpe 下降 `0.34`，胜率下降 `1.34pp`。

决定：不修改 V39、不登记新版本、不加入当前 V39 live spec 或任何 runner 配置。

## 数据与口径

- Exchange / market：Binance USD-M perpetual。
- Symbol / timeframe：`HYPEUSDT` / `15m`。
- Closed-bar 数据范围：`2025-05-30 10:30 UTC` 至 `2026-07-16 15:30 UTC`，`39,573` 根。
- 数据质量：无缺口、无重复时间戳、无关键空值、OHLC 合法；raw/normalized 对齐且无差异。
- 成本：每次 fill 合计 `0.00085`（手续费与 adverse slippage），另计 Binance funding。
- Cooldown1：平仓发生在 `E`，禁止 `E+1` 开仓，最早允许 `E+2 open` 开仓。
- V39 其余规则不变：相对 V35 使用 `long_vol_min=0.35`、`short_target_atr_pct=0.022`，移除空头 1h EMA 确认；保留 K0/K1/K2 时序、`5ATR TP / 7ATR SL`、`ADX22 delayed3`、`MFE>=1.5ATR` 后禁用指标退出、`384` 根 timeout 与 `3.0x` allocation cap。
- 自定义 V39 base 与 canonical V39 最大逐 K 权益差异为 `0`。

当前延长窗口已包含 `2026-07-08` 后新增行情，因此 V39 base 为 `+8430.39% / -27.26%`；登记 V39 时截至 `2026-07-08 05:30 UTC` 的冻结观察值仍是 `+9969.45% / -23.46%`，两者不是同一数据截止点。

## 标准分片

| 窗口 | V39 base 收益 / MaxDD / 平仓数 | V39 + cooldown1 |
| --- | ---: | ---: |
| `1d` | `+0.12% / -2.88% / 1` | `+0.12% / -2.88% / 1` |
| `7d` | `-15.28% / -22.94% / 2` | `-15.28% / -22.94% / 2` |
| `1m` | `-16.51% / -23.96% / 6` | `-13.39% / -23.40% / 6` |
| `3m` | `+120.52% / -27.26% / 34` | `+45.12% / -24.61% / 30` |
| `6m` | `+1482.11% / -27.26% / 67` | `+745.55% / -32.59% / 65` |
| `1y` | `+7842.96% / -27.26% / 103` | `+5259.99% / -32.59% / 101` |

Cooldown1 对最近 `1m` 有轻微表面改善，但从 `3m` 起显著损失收益，`6m/full` 回撤反而更深，不能按近期单一窗口选择。

## 为什么 V35 与 V39 结果相反

Cooldown1 会把平仓后仍成立的入场推迟至少 15 分钟；V39 更严格的多头量能门槛会继续改变延迟后的可入场 bar，因此它并非把 V35 cooldown1 的同一批交易简单换成 V39 仓位：

- 两条 V39 路径仅有 `73` 笔相同 entry timestamp + direction 的交易；这些共同交易逐笔收益一致。
- 其余为 base-only `36` 笔、cooldown1-only `34` 笔，说明冷却触发后形成了明显持仓占用和再入场分叉。
- `2026-05-24`：V39 base 在 `10:00 UTC` 入场，最终以 indicator exit 小赚约 `+0.55%`；cooldown1 延至 `10:15 UTC` 后，最终 stop loss `-14.16%`。
- `2026-06-15`：V39 base `10:45 UTC` 入场并 take profit `+9.70%`；cooldown1 在 V39 量能过滤与冷却共同作用下延至 `11:15 UTC`，最终 indicator exit `-5.30%`。

这些路径翻转抵消了 `2025-11-21` 延迟空单从 stop loss 转为 take profit 的正贡献。V35 的 cooldown1 优势本来就是孤立参数尖峰，迁移到 V39 后失败，进一步证明它不是通用风控规律。

## 产物

- 复现脚本：[research_hype_ema_tb_v39_cooldown1.py](../scripts/research_hype_ema_tb_v39_cooldown1.py)
- 汇总 JSON：[hype_ema_tb_v39_cooldown1_2026-07-17.json](../artifacts/hype_ema_tb_v39_cooldown1_2026-07-17.json)
- 逐笔交易：[hype_ema_tb_v39_cooldown1_2026-07-17_trades.csv](../artifacts/hype_ema_tb_v39_cooldown1_2026-07-17_trades.csv)
- 权益曲线：[hype_ema_tb_v39_cooldown1_2026-07-17_equity.csv](../artifacts/hype_ema_tb_v39_cooldown1_2026-07-17_equity.csv)
