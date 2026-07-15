# BIN-15M-AS6S V6 mark执行引擎桥接审计（2026-07-15）

本审计把trade OHLC同时作为保护触发源，用于分离“执行状态机分辨率变化”与“mark/trade价格源差异”。

| 路线 | 原hard pass | 桥接hard pass | full交易变化 | full年化变化 | full回撤变化 | 当前3m收益变化 |
|---|---|---|---:|---:|---:|---:|
| `nonpreemptive` | `True` | `True` | -1 | +0.013x | -0.02% | -0.05% |
| `strong_breakout_preemptive` | `True` | `True` | -1 | +0.163x | -0.02% | -0.05% |

桥接差异属于从研究K线状态机迁移到可执行保护状态机的真实模型变化，不应通过强行逐笔相等来隐藏。

结构化结果：[`binance_as6s_v6_mark_engine_bridge_2026-07-15.json`](../artifacts/binance_as6s_v6_mark_engine_bridge_2026-07-15.json)。
