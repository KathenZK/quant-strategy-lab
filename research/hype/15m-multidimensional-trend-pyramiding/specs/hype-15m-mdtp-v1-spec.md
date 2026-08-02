# HYPE-15M-MDTP-V1 冻结研究规格

## 身份与状态

- Strategy：`HYPE-15M-Multidimensional-Trend-Pyramiding-V1`
- Alias：`HYPE-15M-MDTP-V1`
- 状态：`explore / NO-GO / not promoted / not live-ready`
- 目的：检验多维趋势丈量与顺势加减仓能否在公平成本、滚动时间顺序和相邻参数下真实改善 V35。

## 数据与时间层级

- Binance USD-M `HYPE/USDT:USDT` perpetual `15m` OHLCV + funding。
- `1h`、`4h` 均由 `15m` 以 `label=left, closed=left` 聚合。
- 高周期特征计算后 `shift(1)`，再 forward-fill 到 `15m`；当前未完成高周期 K 不可见。
- `15m` K0 收盘生成目标，K1 open 调仓；禁止同一收盘价成交。

## 趋势分数

每个周期分别构建并等权：

1. 三个周期的对数收益 / 实现波动率 / `sqrt(h)`；
2. Signed Kaufman ER；
3. 前置 Donchian 区间位置；
4. 方向成交量失衡；
5. signed relative volume。

所有原始分量使用仅含历史的滚动 mean/std 标准化，clip 到 `[-3,3]` 后映射到 `[-1,1]`。full 版本用 `SignedER × (1 - JumpConcentration)` 替代普通 SignedER，并在 jump concentration 过高时禁止加仓。

窗口：

| 层级 | Momentum | ER | Donchian | Volume | Rolling scale |
| --- | --- | ---: | ---: | ---: | ---: |
| `1h` | `8/24/72` | `24` | `72` | `24` | `720` |
| `4h` | `2/6/18` | `18` | `18` | `18` | `180` |

## 方向、阶段与仓位

- `4h score >= 0.18`：只做多；`<= -0.18`：只做空；中间空仓。
- 对齐方向后的 `1h score`：
  - `>=0.10`：萌芽，fraction `0.25`；
  - `>=0.24`：确认，fraction `0.60`；
  - `>=0.38`：成熟，fraction `1.00`。
- 缩量回调后同向 reclaim 且 score 仍确认，可进入 mature fraction。
- `allocation = fraction × clip(0.90 / annualized RV96_15m, 0, 2.5)`。
- 调仓差小于 `0.10` allocation 不成交。
- 初始开仓可执行；后续只有浮盈时允许增加 allocation。
- `abs(price - EMA96_1h) / ATR24_1h > 2.5` 或 jump concentration `>0.55` 时禁止加仓。

## 退出

- ATR trailing：`4 × ATR96_15m`；收盘后更新，下一根生效，只向盈利方向移动。
- 开盘穿越 stop 时按更差 open；否则按 stop。
- `1h` 48 根慢速 Donchian 反向突破。
- `4h` regime 变为空档或反向。
- 对齐后的 `1h score < 0.06`。
- 不设固定止盈；V1 不设固定 timeout。

## 成本

- gross：无 fee、无 slippage、无 funding。
- fee-only：`0.001`/fill。
- fee+slippage：`0.001 + 0.0004`/fill。
- net：`0.001 + 0.0004`/fill + 实际 Binance funding。
- V35 canonical 另用其历史 `0.00085` 合并成本 + funding，仅用于复现；公平主对照采用标准成本。

## 对照与验证

- 对照：V35 canonical、V35 standard-cost、price-only、price+volume、full。
- 消融：no-jump、no-extension、no-recovery-add、no-score-decay、no-staging。
- 滚动历史伪 OOS：180 天初始上下文，60 天不重叠 test fold，参数固定。
- 稳定性：regime、confirm、ATR trail 邻近网格 + 全窗口 `0.8x/1.0x/1.2x`。
- 标签诊断：未来 24h return/MFE/MAE 仅在回测完成后生成，不进入策略。

