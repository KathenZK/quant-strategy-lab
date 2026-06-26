# AI Agent 仓库规则

本仓库是 data-first 的策略研究档案，不是通用策略平台。

阅读任何 HYPE 策略材料前，必须先打开：

1. `research/README.md`
2. `research/hype/README.md`
3. 对应策略家族的 `README.md`

不要根据 `V13`、`V21`、`V35`、`V36` 这类裸版本号判断策略身份。
HYPE 版本号只有放在具体策略家族里才有意义。

标准 family name 使用展开写法；短 id 只作为历史别名：

- `HYPE-Candle-Count-Reversal`（历史别名：`HYPE-CC`）：HYPE K 线数量反转家族。
- `HYPE-EMA-Crossover`（历史别名：`HYPE-EMA-X`）：HYPE EMA 金叉/死叉家族，包括 V14 时代研究。
- `HYPE-1M-EMA-Crossover`（历史别名：`HYPE-1M-EMA-X`）：Binance HYPEUSDT `1m` EMA 金叉/死叉家族。
- `HYPE-EMA-Trend-Breakout`（历史别名：`HYPE-EMA-TB`）：HYPE EMA 趋势突破家族。
- `HYPE-5M-Pullback-Trail`（历史别名：`HYPE-5M-PBTR`）：Binance HYPE `5m` 回踩/恢复入场 + ATR trailing-stop 家族。
- `MU-HYPE-Transfer`（历史别名：`MU-HYPE-XFER`）：基于 HYPE trend kernel 的 MU 迁移研究。

新研究、README 和 decision log 优先使用完整 family name；旧报告里已经存在的短 id 不需要机械重写，但引用时应补充完整名称。

## Active 代码规则

- Active package code 只限于最小数据湖内核、数据归一化、数据质量检查、特征构建和因子计算。
- 交易所抓取、补洞、研究搜索和一次性导出脚本不再放进 `src/strategy_lab/data/`，必须放在对应 `research/.../scripts/` 或明确的研究维护目录，并记录数据来源与质量校验。
- `archive/code/platform/` 只保留少量被长期研究文档引用的历史策略源码快照；它不是 active 平台，也不是可运行平台。
- 当前一次性研究脚本必须放在对应 research topic 或 family 的 `scripts/` 目录。
- 已不再定义 active research line 的历史一次性研究脚本放在 `archive/scripts/research/`。
- 除非用户明确要求考古历史实现，否则不要把 archive 里的代码当作当前事实来源。

## 数据质量硬规则

- 数据质量是本仓库的第一优先级。任何策略研究、回测、candidate 讨论或结论都必须先确认数据来源、时间范围、周期、symbol、交易所、market type 和字段口径。
- 禁止编造、补猜或静默填充行情数据。缺口、重复、字段空值、raw/normalized 不一致、source 不明、`is_closed` 不可靠、OHLC 不合法、成交量/quote volume 异常时，必须先核实并记录，不得继续把结果包装成可信回测。
- 使用数据湖前至少检查：时间戳连续性、唯一键重复、raw 与 normalized 的 OHLCV/quote_volume/trade_count/vwap 对齐、关键字段空值、`source`、`is_closed`、UTC 时间、以及是否有未迁入标准数据湖的 cache/scratch 数据。
- 对 Binance/HYPE 等关键研究数据，发现缺口或异常时优先用交易所公共 API / Binance Vision / retained raw evidence 复核；不能核实时要明确降级为 data-quality blocker。
- 如果数据质量问题影响已有研究结论，必须在对应 `research/` 文档或 decision log 中记录影响范围和修复状态；不要用参数搜索掩盖数据问题。

## Live-Executable 研究规则

- 本仓库研究的是可以真实在线下单交易的策略，不是漂亮但无法交易的回测幻觉。
- 在审计订单时序和执行假设之前，不要把任何策略提升为 live、paper-live、dry-run、handoff 或 candidate 状态。
- 不可能成交、价格已经穿越后仍按旧 stop 价成交、lookahead stop 更新、不可用的 intrabar 决策、不可成交的订单假设，都必须视为硬失败。
- 如果策略使用 `min_hold_bars`、延迟退出、trailing stop、保护止损或锁仓期，讨论收益前必须先审计受保护区间和解锁行为。
- promotion write-up 必须覆盖手续费、滑点、stop placement 有效性、stop-market 行为、仓位、emergency stop 或 kill switch、重启恢复、缺失数据行为，以及 live runner 是否能复现状态机。
- 负面的 live-feasibility 发现必须立即写入 `research/`，并应下调候选状态，不要用更多参数搜索掩盖问题。
- 这条规则存在是因为本仓库已经多次犯过同类错误，包括早期 trend-strategy research，以及近期 `HYPE-5M-PBTR` V2.1A/V3.3/V4 的 lockout-stop 审计。Live feasibility 必须先于 performance storytelling。

## 新研究规则

- 优先使用 document-first 工作流。
- 启动新策略研究前，先查 `research/README.md` 和对应资产目录的 `README.md`，确认是否已有相同 family。
- 如果是新的时间片或新的策略机制，必须新建独立目录，命名为 `research/<asset>/<timeframe>-<strategy-family-slug>/`，例如 `research/hype/1m-ema-crossover/`、`research/hype/15m-ema-crossover/`、`research/hype/5m-pullback-trail/`。
- 不要因为指标相似就把新时间片研究塞进旧 family；例如 `1m` EMA crossover 不能放进 `15m-ema-crossover/`。
- 新 family 目录创建时至少包含 `README.md`、`decision-log.md`、`scripts/`、`artifacts/`；按需要再建 `diagnostics/`、`ablations/`、`live-specs/`、`research-notes/`。
- 探索产生的一次性脚本放在对应 `research/.../scripts/` 目录。
- 最终结论必须保存到对应 family 的 repository-tracked Markdown 文档中，位置在 `research/` 下。
- 需要保留的 JSON、CSV、HTML 和 trade-path 输出放在对应 `research/.../artifacts/` 目录；顶层 `reports/` 只用于 scratch 或 legacy local cache。
- 如果 Markdown 报告引用了某个生成文件，该文件就是 durable evidence，应放在同一 topic/family 的 `artifacts/` 目录，而不是顶层 `reports/`。
- 不要把 `reports/` 里的所有文件整批提升到 `artifacts/`；只迁移被引用或明确需要保留的证据，并把 Markdown 链接从 `reports/...` 改掉。
- 新研究报告默认使用中文，除非用户明确要求其他语言。
- 不要在 Cursor Canvas 文件或 Cursor 私有项目目录里创建研究报告、台账或长期分析。
- Canvas 只能在用户明确要求时作为临时可视化界面；如果 Canvas 产生了可持久化结论，完成前必须同步写回对应 `research/` Markdown 文件。
- `legacy-canvas/` 目录是迁移后冻结的历史证据。不要在那里创建新的策略研究；经过复核的发现应提升到 family 台账、`canonical-specs/`、`diagnostics/` 或 `decision-log.md`。
- 只有当代码是可复用的数据基础设施或窄口径数据集导出器时，才可以提升回 `src/strategy_lab/`。
