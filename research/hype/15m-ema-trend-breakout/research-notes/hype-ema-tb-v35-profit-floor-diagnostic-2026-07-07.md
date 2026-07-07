# HYPE-EMA-TB-V35 浮盈保护线诊断

日期：2026-07-07

## 结论

不建议把本次分阶段 `profit floor` 直接合入线上 `HYPE-EMA-Trend-Breakout-V35` 主策略。

这组保护线确实能处理“接近 5ATR 止盈后回吐”的近期局部问题；在 Binance API 补充窗口里，最近 `7d` 收益从 `+9.94%` 小幅升到 `+11.00%`，最近 `1m` 从 `+23.40%` 升到 `+29.94%`。但全样本结构被明显破坏：收益从 `+8360.80%` 降到 `+898.31%`，Sharpe 从 `4.75` 降到 `3.18`，最大回撤从 `-23.46%` 加深到 `-26.72%`，交易数从 `108` 增到 `213`。

主要原因不是保护线本身不能止回吐，而是它与 V35 的 `cooldown_bars=0` 和“趋势单必须吃到 5ATR 才有复利优势”的结构冲突。保护线把大量成熟趋势单提前截断为 `0~2.5ATR` 出场，然后信号仍成立时又很快重进，导致 `profit_floor` 退出达到 `142` 次、交易成本约翻倍。

## 测试口径

- 市场：Binance USD-M Futures `HYPEUSDT` perpetual。
- 周期：`15m`。
- 主策略：`HYPE-EMA-Trend-Breakout-V35`，K0 close 信号、K2 open 入场、entry ATR 取 K1、TP/SL 用 15m high/low、indicator/timeout 下一根 open 退出。
- 成本：沿用 V35 canonical override，单边 `0.00085`（taker fee + 4 bps slippage）。
- Funding：Binance public API funding history，对齐 15m；缺失填 `0`。
- 分片：`1d/7d/1m/3m/6m/1y/full`，均锚定数据末端。
- Profit floor：收盘后根据已确认 MFE 上调保护线，下一根 K 开始生效；若下一根 open 已穿越保护线，则按 open 成交，避免 stale stop fill。

## 数据质量

标准数据湖复现窗口到 `2026-06-26 04:00 UTC`：

- normalized OHLCV `37,607` 行，`2025-05-30 10:30 UTC` 至 `2026-06-26 04:00 UTC`。
- `15m` 连续缺口 `0`，重复 timestamp `0`，关键字段空值 `0`，OHLC 异常 `0`。
- raw vs normalized 的 `open/high/low/close/volume/quote_volume/trade_count/vwap` 完全一致。

为覆盖用户截图对应的 7 月实时场景，补充拉取 Binance public API：

- API OHLCV `38,676` 行，`2025-05-30 10:30 UTC` 至 `2026-07-07 07:15 UTC`。
- `15m` 连续缺口 `0`，重复 timestamp `0`，关键字段空值 `0`，OHLC 异常 `0`。
- API 补充口径是 public raw source，不做 data lake raw/normalized 对比。

## 核心结果

Binance API 补充窗口：

| 版本 | Full 收益 | Max DD | Sharpe | 交易数 | 胜率 | 退出结构 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| V35 base | `+8360.80%` | `-23.46%` | `4.75` | `108` | `78.70%` | TP `83` / SL `15` / indicator `10` |
| V35 + profit floor | `+898.31%` | `-26.72%` | `3.18` | `213` | `76.06%` | floor `142` / TP `36` / indicator `26` / SL `9` |

最近分片：

| 窗口 | V35 base | V35 + profit floor | 判断 |
| --- | ---: | ---: | --- |
| `1d` | `-1.23%` | `-1.23%` | 无改善 |
| `7d` | `+9.94%` | `+11.00%` | 小幅改善 |
| `1m` | `+23.40%` | `+29.94%` | 小幅改善 |
| `3m` | `+187.65%` | `+67.20%` | 明显劣化 |
| `6m` | `+1766.64%` | `+548.31%` | 明显劣化 |
| `1y` | `+9516.21%` | `+886.11%` | 明显劣化 |

## 对当前问题的解释

用户截图中的问题是：单笔最高接近 `4.86 ATR`，但因为 V35 在 `mfe_atr >= 1.5` 后永久关闭 ADX 指标退出，ADX 变弱不会触发退出，利润可能回吐。

本次测试证明：把这个局部问题简单交给通用分段 `profit floor`，会在近期样本里减少部分回吐，但历史上会把 V35 最重要的收益来源砍掉。V35 的收益高度依赖少数趋势单完整打到 `5ATR`；保护线在 `3ATR/4ATR` 后过早把仓位平掉，并且 `cooldown=0` 使策略很快重进，形成高频小盈利/小亏损序列，成本和路径依赖显著上升。

因此，这个方案不适合作为 V35 主策略替换。更值得继续测的是更窄的补丁，例如只在 `mfe_atr >= 4.5` 且价格从 MFE 回撤超过某个 ATR 比例时启用保护，或 profit floor 退出后设置同向重进冷却/必须等待信号 reset；这些都应作为新诊断分支，而不是直接改线上 V35。

## 保留证据

- Data lake 复现：`../artifacts/hype_ema_tb_v35_profit_floor_data_lake_2026-07-07.json`
- Data lake trades：`../artifacts/hype_ema_tb_v35_profit_floor_data_lake_2026-07-07_trades.csv`
- API 补充回测：`../artifacts/hype_ema_tb_v35_profit_floor_binance_api_2026-07-07.json`
- API trades：`../artifacts/hype_ema_tb_v35_profit_floor_binance_api_2026-07-07_trades.csv`
- API 输入 OHLCV：`../artifacts/hype_ema_tb_v35_profit_floor_binance_api_ohlcv_2026-07-07.csv`
- API 输入 funding：`../artifacts/hype_ema_tb_v35_profit_floor_binance_api_funding_2026-07-07.csv`
- 复现脚本：`../scripts/research_hype_ema_tb_v35_profit_floor.py`
