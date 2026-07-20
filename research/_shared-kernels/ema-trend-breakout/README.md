# EMA Trend-Breakout Kernel

跨标的 EMA 趋势突破共享研究内核。`v1` 抽取自 `HYPE-EMA-Trend-Breakout` 的 V35/V39.2/V40 实现，但不包含标的、交易所、数据路径或产物路径，因此可由 HYPE、BTC 等消费方传入各自 OHLCV、funding、配置与成本口径。

## 冻结版本

| Version | 文件 | SHA256 | 说明 |
| --- | --- | --- | --- |
| `v1` | [v1/engine.py](v1/engine.py) | `4ce1923e5ef3e5d6f43d22304266f18155ba51da3628b63e8b8a749947101e32` | EMA96/384、ADX/DI、volume surge、ATR672、上一根完整 1h 特征、K0/K1/K2、cooldown、stop-first bracket、gap-open、ADX delayed exit、MFE 关闭指标退出、timeout、funding、成本、metrics 与标准分片。 |
| `v2` | [v2/engine.py](v2/engine.py) | `36e5d10c0d281701c46446344dd50af7a7589ec03285be3289e82362e1c2917a` | 在运行时校验并复用冻结 `v1` 指标/信号合同；新增独立 `fixed` allocation 模式、保留 `atr_risk` sizing，并为显式 fee/slippage 增加独立压力倍数。默认参数与 `v1` HYPE parity 完全一致。 |

`v1` 与 `v2` 自各自 SHA 登记后冻结。任何逻辑、默认值、注释或格式修改都会改变 SHA；修复或扩展必须新建 `v3/`，重新完成 parity，并在本表登记新 SHA。`v2` 会在 import 时验证其依赖的 `v1` SHA，消费方仍须 pin `v2` 路径与本表 SHA256。

## 仓位模式

- `sizing_mode="atr_risk"`：保留 V35/V39.2 原始 sizing，按方向使用 `long_target_atr_pct` / `short_target_atr_pct`，再受 `max_allocation` 限制。
- `sizing_mode="fixed"`：直接使用 `fixed_allocation`；搜索所需等权口径应显式设置 `fixed_allocation=1.0`，不读取 ATR target，也不允许通过调 target 间接近似固定仓位。
- `allocation_for_entry()` 是两种仓位模式的统一审计入口。固定 allocation 不得超过 `max_allocation`，否则配置校验失败。

## 执行与成本模式

- 默认 `execution_mode="gap_open"`：stop 被开盘价穿越时按更差的 open 成交；同 bar TP/SL 冲突采用 stop-first。
- `execution_mode="legacy_exact"`：仅用于复现历史 HYPE canonical，保留 stop gap 按旧 stop 价成交的旧口径。
- `cost_mode="legacy_cost"`：每个 fill 按已成交 allocation 扣除单一合并成本，HYPE V40 parity 使用 `trade_cost_rate=0.00085`。
- `cost_mode="explicit"`：每个 fill 分开扣除 `fee_per_fill × fee_multiplier`，并把成交价按 `adverse_slippage_per_fill × slippage_multiplier` 向不利方向移动；BTC/Binance 基线可传 `0.001` fee 与 `0.0004` adverse slippage，压力测试可独立设置例如 fee `2x`、slippage `3x`。
- `explicit_cost_stress()` 返回基准值、倍数与有效值，供搜索结果和报告写入实际成本口径。压力倍数不作用于 `legacy_cost`，避免改变 HYPE 历史合并成本语义。

## 消费方与接入状态

- `HYPE-EMA-Trend-Breakout-V39.2/V40`：已由 [parity 测试](../../../tests/test_ema_trend_breakout_kernel.py) 动态加载当前 HYPE 脚本，在同一配置与本地 HYPE 数据上验证 `v2` 默认 `atr_risk + legacy_cost + legacy_exact` 的信号、交易签名和逐根 equity 差异均为 `0`。现有 HYPE 历史脚本仍保留原路径，尚未改为 SHA pin 消费本内核。
- BTC 等跨标的消费方：使用 symbol-neutral API 与 `explicit` 成本模式；在各自家族脚本接入并完成数据质量和 parity/acceptance 验证前，不视为已消费。

## 公共接口

- 配置与版本身份：`V35Config`、`SignalFlags`、`v39_2_config()`、`v40_config()`。
- 特征与信号：`build_features()`、`build_signals()`。
- 仓位与成本：`allocation_for_entry()`、`effective_fee_per_fill()`、`effective_slippage_per_fill()`、`explicit_cost_stress()`。
- 回测与结果：`run_backtest()`、`RunResult`、`metrics_from_series()`、`slice_metrics()`。
- 迁移验证：`trade_signatures()`、`parity_report()`。

内核只接收内存中的 market/funding 数据，不负责下载、数据湖路径、标的元数据或产物落盘。消费方必须先完成其市场的数据质量门禁，并负责保存报告和 artifacts。
