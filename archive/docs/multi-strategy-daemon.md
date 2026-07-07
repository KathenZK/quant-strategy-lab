# Multi-Strategy Daemon 架构备忘

Created: 2026-06-28

## 背景

当前每个 Python runner 独立常驻时，会重复加载 Python 解释器、`pandas`、`numpy`、`ccxt`、K 线拉取、指标计算、状态恢复和 SQLite 账本逻辑。即使单个策略很轻，一个常驻进程也常见占用 `120-180MB` RSS。

当候选策略数量增加时，不能按“一个策略一个 systemd 服务”的方式线性扩展：

```text
50 个独立 runner ~= 50 * 120-180MB = 6-9GB RSS
```

这对当前 `1.6GB RAM` 的阿里云机器不可行。后续如果 dry-run / paper 候选明显增多，应优先考虑把多个策略合并到一个 Python 进程中。

## 核心想法

把重复底座共享掉：

```text
当前模式：
策略A runner: Python + pandas/numpy/ccxt + 拉K线 + 指标 + 状态 + DB
策略B runner: Python + pandas/numpy/ccxt + 拉K线 + 指标 + 状态 + DB
策略C runner: Python + pandas/numpy/ccxt + 拉K线 + 指标 + 状态 + DB

合并模式：
一个 strategy-daemon:
 共享 Python 解释器
 共享 pandas/numpy/ccxt
 共享 Binance K线拉取
 共享公共指标缓存
 共享调度循环
 每个策略只保留自己的参数、状态、信号、虚拟订单和统计
```

如果 `50` 个策略都基于同一个交易所、同一个 symbol、同一个 timeframe 和类似指标，合并后是真有机会在小机器上跑起来的。

粗略估算：

```text
底座：150-250MB
共享 K线 + 指标：几十 MB 内
50 个轻量策略配置/状态/信号：几十 MB 到一两百 MB
总内存：约 300-600MB，有机会在 1.6GB 机器上运行
```

如果是 `100` 个同 symbol/timeframe 的轻量参数变体，也可能技术上可跑，但更容易遇到 SQLite 写入、日志、调度延迟和策略管理复杂度问题。不要把 `100` 个真钱 live runner 作为目标。

## 适用条件

适合合并：

- 同一交易所，例如 Binance。
- 同一 symbol，例如 `HYPE/USDT:USDT`。
- 同一 timeframe，例如 `5m`。
- 共用同一批 K 线和指标：EMA、ATR、ret、htf_spread 等。
- 大量策略只是参数变体或过滤器变体。
- 主要用途是 dry-run、paper audit、候选观察和信号打分。

不适合简单合并：

- 跨很多币种。
- 跨很多 timeframe。
- 每个策略需要不同交易所账户状态。
- 每个策略都要独立真实下单、撤单、恢复。
- 每根 K 都写大量逐策略明细日志。

## 推荐模块划分

```text
MarketDataService
 每 5m 拉一次 Binance HYPE K线
 去重、连续性检查、闭合 K 判断
 计算公共指标并缓存 feature frame

StrategyEngine
 从配置加载 N 个策略
 每个策略消费同一个 feature frame
 输出 signal candidates
 不直接下单

PaperExecutionEngine
 对每个策略做虚拟 TP/SL/timeout 成交
 记录 virtual orders、virtual trades、MAE/MFE、原因
 用 strategy_id 区分

Portfolio / Risk Router
 统一处理账户级约束
 例如同一账户同一时间最多几笔仓位
 处理策略优先级、互斥组、资金分配

LiveExecutionEngine
 只服务少量精选策略
 负责真实订单、撤单、恢复、账本对账
 不建议让 50 个候选同时真钱下单

Storage
 event_log(strategy_id, event_type, payload_json)
 signal_log(strategy_id, signal_ts, side, accepted, reject_reason)
 virtual_trade_ledger(strategy_id, ...)
 live_trade_ledger(strategy_id, ...)
```

## 运行形态

建议分成两类服务：

```text
multi-strategy-dry-run-daemon
 跑 20/50/100 个候选
 只记录虚拟信号、虚拟成交和评分
 可用 systemd timer 或常驻 daemon

single/few-strategy-live-runner
 只跑 1-3 个精选策略
 负责真钱订单
 保持状态机和事故面尽量简单
```

这样可以同时观察很多策略，但真钱通道不被候选策略复杂度污染。

## 内存与性能策略

优先做：

- 同 symbol/timeframe 只拉一次 K 线。
- 公共指标只算一次。
- 策略配置用 dataclass / dict，不为每个策略复制 DataFrame。
- 每根 K 只保留必要窗口，不长期保存巨大中间表。
- SQLite 批量写入，避免每个策略每根 K 多次 commit。
- 日志默认记录汇总，详细逐策略调试日志按需打开。

谨慎做：

- 每个策略保存完整 feature frame 副本。
- 每个策略独立 ccxt client。
- 每个策略独立 SQLite DB。
- 每根 K 对每个策略写大 JSON payload。

## 50 个策略的可行性判断

在当前小机器上，`50` 个策略有可能可行，但前提是：

- 这些策略共享 `HYPE/USDT:USDT` `5m` 数据。
- 大部分指标相同。
- dry-run / paper 为主。
- 单次调度能在远小于 `5m` 的时间内完成，最好低于 `10-30s`。
- 服务常驻 RSS 控制在约 `300-600MB`。

如果策略跨 symbol/timeframe，或者都要真钱下单，则应升级机器或拆成多个服务。

## 何时启动这项改造

触发条件：

- 阿里云内存 available 长期低于 `300MB`。
- 需要同时观察超过 `5-10` 个 Python runner。
- systemd 常驻服务数量继续增长。
- 出现 OOM、进程被杀、或重启时内存尖峰明显。
- 候选策略主要是同一数据源的参数变体。

在触发前，可以先用两种轻量措施：

1. 给小机器加 `2-4GB` swapfile，作为 OOM 保险。
2. 对纯 dry-run 策略改成 systemd timer，每 `5m` 跑一次 `run-once` 后退出，平时不占常驻内存。

## 分阶段落地建议

第一阶段：只做 paper daemon。

- 不碰真钱下单。
- 读取一个 YAML/JSON 策略列表。
- 共享 HYPE 5m 数据和指标。
- 每根闭合 K 对所有策略打信号。
- 写 `signal_log` 和 `virtual_trade_ledger`。

第二阶段：加候选排名。

- 统计最近 N 笔、最近 N 天、月度、OOS 样式指标。
- 输出候选健康度。
- 对坏掉的策略自动标记 inactive，但不删除历史。

第三阶段：接入 live router。

- 只允许少数被批准的 strategy_id 进入真钱执行。
- live router 统一处理账户级风控和互斥。
- dry-run daemon 继续观察大量候选。

## 风险

- 单进程合并后，一个 bug 可能影响多个 paper 策略，所以要隔离异常：单个策略报错只标记该策略失败，不能让 daemon 崩溃。
- SQLite 写入量可能成为瓶颈，必须批量写入并控制 payload 大小。
- 真钱执行不要和大量候选的实验逻辑混在一起；live runner 应保持小而明确。
- 如果未来跨多个 symbol/timeframe，应按数据源分片，例如 `hype-5m-daemon`、`hype-15m-daemon`，不要无边界塞进一个进程。

## 当前结论

短期继续用独立 runner 或 systemd timer 即可。等候选数量增加、内存压力变大，优先实现一个 `multi-strategy-dry-run-daemon`，用于观察几十个同源候选；真钱 live 仍保留独立小服务，只跑少数精选策略。
