# `mk7-v8` 回测复现阻塞诊断

日期：2026-07-12  
对象：外部文件 `/Users/ZK/Downloads/mk7-v8-spec.md`  
结论：`reproduction blocked / not promoted / not live-ready`

## 结论

当前不能对 `mk7-v8` 给出可信的独立回测结果。六币 `1h`、HYPE `15m/1m` OHLCV 与 Binance funding 基础数据可读，但 MII 与 K2FQ 所需的外部序列不完整；同时规格遗漏了若干会直接改变交易路径的定义。

规格第 1.4 节明确规定：启用的数据源整体缺失时必须硬失败，不能静默退化成另一策略。因此不能把缺失的 CVD、主动流、premium 或大户持仓比当作 `0`、全部 fail-open，或直接复述规格声称的收益数字。

规格中的以下数字目前全部视为**待独立验证的来源声明**，不是本仓库回测结果：

- 主窗口 `37,662.136815x / MDD -16.858990% / 601 trades`；
- 完整曲线 `9,328,938.861620x / MDD -18.898046% / 743 trades`；
- `raw_signal_sha256` 与 `selected_scaled_trade_sha256`。

## 已核对的数据

通过现有研究 loader 实际读取：

- TRX/SOL/ETH/BNB `1h`：各 `17,520` 根；BTC `1h`：`17,520` 根；
- HYPE `1h`：`9,545` 根，`2025-05-30T10:00:00Z` 至 `2026-07-02T02:00:00Z`；
- HYPE `15m`：`38,765` 根，`2025-05-30T10:30:00Z` 至 `2026-07-08T05:30:00Z`；
- HYPE `1m`：`584,414` 根，`2025-05-30T10:30:00Z` 至 `2026-07-10T06:43:00Z`；
- 六币离散 Binance funding 历史可读。

标准 HYPE `15m/1m` OHLCV 只有 OHLCV、quote volume、trade count、VWAP 等字段；没有规格所需的分规模 CVD、双所净流/总流或 `taker_buy` 字段。仓库中也没有 `mk7-v8` 对应的冻结交易文件、原始信号文件或可执行复现脚本。

## 硬阻塞

### 1. MII 的“双所”没有身份

规格只写“最近 96 根 15m 的双所净主动流/总主动成交量”，没有给出两个交易所、市场类型、symbol 映射、数据源或成交方向口径。不同交易所组合会改变每笔 MII 仓位，进而改变双槽选择与整条权益曲线。

### 2. CVD 与失衡公式不完整

规格给出了中单 `2k–20k USDT`、大单 `>=20k USDT` 的桶边界，但没有定义：

- trade notional 使用成交价乘数量还是交易所 quote quantity；
- 主动买卖方向如何判定；
- `mid_imb`、`big_imb` 的分子和分母；
- 10 根窗口是先逐 bar 求比再聚合，还是先聚合流量再求比；
- 边界值 `2k/20k`、缺 bar、重复成交与跨 bar 成交的处理。

这些字段直接决定“空头拒绝”和 `1.3x` credit 加成，不能猜测。

### 3. K2FQ 外部门缺少可复现数据合同

规格要求 HYPE `15m premium close` 与 `5m top_lsr_pos`，但没有给出：

- premium 的精确定义、symbol 与历史下载端点；
- `top_lsr_pos` 对应的交易所接口字段；
- 历史归档来源和数据质量验收；
- 同 timestamp 重复值、缺口和发布延迟处理。

当前标准 loader 未提供这两条序列。按规格，整条序列为空必须硬失败。

### 4. 哈希不可复算

规格提供了两个 SHA256 验收值，但没有冻结被哈希对象的：

- 字段顺序、行顺序与列名；
- timestamp 文本格式；
- float 精度、舍入与 `NaN` 表达；
- CSV/JSON/二进制编码、换行和是否包含 header。

即使交易经济含义一致，也无法按字节复算验收哈希。

### 5. 1m blowoff 条件疑似笔误

“量峰量/中位量不低于 `0`”对正常非负成交量恒成立，无法构成过滤门。规格还没有定义 150 根窗口内“量峰分钟”的并列裁决和中位量为零时的处理。需要确认阈值是否确为 `0`。

### 6. MII 交易状态仍有路径歧义

规格没有明确 MII 原始候选之间是否先执行独立单仓去重；`375` 是过滤后信号数还是已经完成 MII 内部持仓阻塞后的交易数也不明确。另有 gap-open 顺序写成“max-hold、SL gap、TP gap和giveup”，与一般 bar 的“SL、giveup、TP”顺序不同，需要确认这是有意规则。

## 数据完整性核验（2026-07-12/13）

对 [`data/cache/mk7_v8_binance/`](../../../../data/cache/mk7_v8_binance/) 全量核验（报告：[`integrity_report.json`](../../../../data/cache/mk7_v8_binance/logs/integrity_report.json)）：

| 检查项 | 结果 |
| --- | --- |
| aggTrades 398 天 zip 覆盖与 zip 完整性 | PASS |
| 15m CVD/flow 连续、非负、恒等式 | PASS |
| premiumIndex 15m 连续有限 | PASS |
| HYPE/BTC `1m/15m` + taker_buy 连续与 OHLC | PASS |
| `top_lsr` Binance Vision 日归档 | PASS（`399/399` 天） |
| `top_lsr` 全窗 `>=2025-05-30` | PASS（`114,517` 行；16 个孤立 5m 缺点记 warning） |

六币候选探针（规格参数 + 引擎补特征）：`TRX/HYPE/ETH/BTC/BNB` 合并计数精确对齐 `44/74/89/54/62`；`SOL` 为 `82` vs 规格 `79`（+3）。`top_lsr` 早段按规格 fail-open 继续回测，并在结果中标注偏差。

## 2026-07-12 币安单所补数结果

用户确认只使用币安单所后，已下载可用序列到 [`data/cache/mk7_v8_binance/`](../../../../data/cache/mk7_v8_binance/)，合计约 `2.8GB`。脚本：[`download_mk7_v8_binance_missing_data.py`](../scripts/download_mk7_v8_binance_missing_data.py)。

| 序列 | 状态 | 体积 | 覆盖 |
| --- | --- | ---: | --- |
| HYPE aggTrades 日 zip | 已下 `398/398` 天 | `2.77GB` | `2025-05-30` 至 `2026-07-01` |
| 15m CVD/flow 特征 | 已由 aggTrades 聚合 | `4.9MB` | `2025-05-30` 至 `2026-07-01` |
| premiumIndex 15m | 已下 | `2.1MB` | `2025-05-30` 至 `2026-07-02` |
| HYPE/BTC klines + taker_buy | 已下 | `~38MB` | 主窗齐全 |
| `top_lsr_pos` 5m | Binance Vision `daily/metrics`，`sum_toptrader_long_short_ratio` | `~9.6MB` | `2025-05-30 10:35` 至 `2026-07-02 02:55` |

2026-07-13 修正：此前“Vision 无对应归档”的判断错误。REST 接口确实只保留约 30 天，但 Binance Vision 的 USD-M `daily/metrics/HYPEUSDT/` 提供完整 5m 历史；归档字段 `sum_toptrader_long_short_ratio` 与 REST `topLongShortPositionRatio.longShortRatio` 在 2026-06-30 的 289 个重叠点最大绝对差仅 `0.00005`（REST 四位小数舍入）。全窗 LSR blocker 已关闭；其余语义歧义（MII 内部去重、giveup/gap 顺序、哈希序列化、1m blowoff 阈值疑似笔误）仍在。

## 继续复现所需输入

1. MII 内部持仓去重、giveup/gap 顺序的明确答案；
2. 两个 SHA256 的规范化序列化合同；最好再提供首末各若干笔交易锚点；
3. 确认 1m blowoff “量峰量/中位量不低于 0”是否笔误；
4. SOL 与 K2FQ 的冻结逐笔清单，用于定位剩余 `+3 / +1` 原始候选偏差。

补齐后应先通过原始候选计数，再核对逐笔 `asset/leg/side/entry_ts/exit_ts/exposure/equity_ret`，最后才计算账户权益、近期切片和门禁结果。
