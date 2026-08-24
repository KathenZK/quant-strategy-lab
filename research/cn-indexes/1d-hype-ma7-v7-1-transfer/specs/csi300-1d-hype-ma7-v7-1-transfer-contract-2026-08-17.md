# CSI300-1D-HYPE-MA7-V7.1 零调参迁移合同

## 身份与目标

- Target family：`CSI300-1D-HYPE-MA7-V7.1-Transfer`
- Source version：`HYPE-1D-MA7-Asymmetric-Body-Trend-V7.1`
- Target：沪深 300 价格指数 `000300`，Asia/Shanghai regular-session `1d`
- 研究窗：`2022-08-17` 至 `2026-08-17`，最近四年；研究窗前保留 120 个日历日 warmup
- 状态：`explore / not promoted / not live-ready`
- 任务：固定参数零调参迁移，只回答价格指数路径上是否保留绝对与超额收益；不选参、不登记版本、不推进 runner

## 数据合同

- 主来源：东方财富历史 K 线，`secid=1.000300`、`klt=101`、`fqt=0`
- 原生字段：session date、OHLC、volume、amount、amplitude、change、turnover
- 市场身份：`exchange=sse`、`market_type=equity`、`symbol=000300`、`timeframe=1d`、`source=eastmoney_kline_api`
- 次来源：Yahoo `000300.SS`，只交叉核验，不参与回测
- 必查：代码/名称、数值空值、重复 session/timestamp、OHLC 合法性、单调时间、来源 SHA256
- 数据状态：`raw_unaccepted`。交易所日历、`is_closed`、`trade_count` 与 `vwap` provenance 未完成，不得写入 normalized 或支持 promotion。

## 固定指标与参数

- `SMA7[t] = mean(close[t-6:t])`
- `TR[t] = max(high-low, abs(high-prev_close), abs(low-prev_close))`
- `ATR7[t] = mean(TR[t-6:t])`
- `RSI6`：Wilder RMA，首个 6 期 gain/loss 简单均值初始化

| Leg | Entry | Exit / protection | Max hold | Cooldown |
| --- | --- | --- | ---: | ---: |
| Long | 前收 `<=SMA7`，当收 `>SMA7`；`SMA7[t]-SMA7[t-1] >= 0.02*ATR7` | 收盘 `<SMA7-0.75ATR7`；close watermark trailing `1.5ATR7`；OAPP `0.5ATR` 激活、10% giveback 连续 2 日且盈利 `>0.28%` | 90 sessions | 2 sessions |
| Short | 前收 `>=SMA7`，当收 `<SMA7-0.10ATR7`；两日 MA 下降 `>=0.02*ATR7` | 收盘 `>SMA7+0.75ATR7`；MA 一日斜率不再下降；hard stop `1.5*entry ATR7`；close watermark trailing `4ATR7`；RSI6 `<20` 连续 2 日且盈利 `>0.28%` | 20 sessions | 3 sessions |

- 仓位：固定目标 `1x` 账户权益，单仓、非加仓。
- OAPP/short RSI 优先于 MA boundary、short slope、max hold。
- long protective stop 后，若执行价低于上一完整 session 的 SMA7，按同参考价立即反手 short。
- 只有“纯 OAPP 且无同时 boundary/max-hold”的盈利 long exit 才建立 `PEHC_294` shadow；最长 8 sessions，shadow stop 触发后下一 session open 复核并开 short。

## 日 K 执行适配

V7.1 原版需要真实 `1h` 保护序列。本合同只有日 K，因此冻结以下诊断适配，不把它称为 exact parity：

1. 收盘信号最早下一交易 session open 成交。
2. 已激活 stop 若开盘穿越，按 open 成交；否则日 low/high 触碰时按 stop。
3. long 入场当日没有初始 hard stop；首个持仓 session 收盘后才按 close watermark 建立 trailing stop。
4. 日 OHLC 无法恢复触碰时刻和 high/low 先后；forced short 的盘中执行与 PEHC opportunity 都是近似。
5. 日线 soft exit 与隔夜 stop 同在下一 open 时，先处理 gap-through stop。
6. 基准延迟压力把所有收盘型 entry/soft-exit 再延后一 session；保护止损不延后。

## 成本与基准

- 主结果：零费用、零滑点，只作不可交易价格指数路径诊断。
- 压力：每 fill `10 bps` 不利摩擦；没有 Binance 默认成本。
- 基准：同窗口沪深 300 价格指数 buy-and-hold，分别使用零成本和 `10 bps/fill` 同成本口径。
- 未建模：ETF 申赎/分红、A 股 T+1 与涨跌停、IF 保证金/基差/移仓、short 借券、税费与真实盘口。

## 必报结果

- full：收益、日 OHLC/close MDD、Sharpe、交易数、胜率、PF、exposure、long/short 交易数
- controls：`10 bps/fill`、额外一 session 延迟、long-only、short-only、buy-and-hold 与超额
- 最近分片：`1d/7d/1m/3m/6m/1y`，锚定数据集末日，仅作 audit
- 年度 cold-flat 切片
- 数据质量、Yahoo 交叉核验、raw data-lake 写入清单

## 裁决

只有零成本与成本压力下都维持正超额，且最近一年不亏损，才允许写 `TRANSFER_PASS_DIAGNOSTIC_ONLY`；否则写 `TRANSFER_FAIL`。无论结果如何，本合同都不登记版本、不构成 promotion 或 live-ready 证据。

## 证据入口

- [家族主账](../csi300-1d-hm7-xfer-core-ledger.md)
- [复现脚本](../scripts/research_csi300_1d_hype_ma7_v7_1_transfer.py)
- [机器结果](../artifacts/csi300_1d_hype_ma7_v7_1_transfer_2026-08-17.json)
