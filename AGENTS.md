# AI Agent 仓库规则

本仓库是 data-first 的量化策略研究档案。研究对象可以覆盖加密货币、美股、A 股、港股、大宗商品等多个市场；HYPE 只是当前较早展开的一条研究线。

`.cursor/rules/` 是硬性工作约束；本文件补充仓库入口、策略命名和 active code 边界。若同一事项重复出现，以更具体、更严格的表述为准。

当需要基于某个资产或策略家族作结论、修改研究文档或运行相关脚本前，必须先打开：

1. `research/README.md`
2. 对应资产或主题目录的 `README.md`，例如 `research/hype/README.md`、`research/mu/README.md`
3. 对应策略家族或研究主题的 `README.md`

不要根据 `V13`、`V21`、`V35`、`V36` 这类裸版本号判断策略身份。版本号只有放在具体资产、市场、周期和策略家族里才有意义。

标准 family name 使用展开写法，优先包含资产、周期和机制；短 id 只作为历史别名。新研究、README 和 decision log 优先使用完整 family name；旧报告里已经存在的短 id 不需要机械重写，但引用时应补充完整名称。

所有新增或更新的长期研究文档默认使用中文，除非用户明确要求其他语言。这个规则包括 `decision-log.md`、README、策略主账、diagnostics、ablations、live specs、research notes、实验结论和交接文档；策略名、版本号、参数、路径、指标名和状态术语可以保留英文原文。

## 当前 HYPE 命名口径

HYPE 是当前已有历史材料最多的研究线，引用时特别注意不要把不同 family 的同名版本号串起来：

- `HYPE-Candle-Count-Reversal`（历史别名：`HYPE-CC`）：HYPE K 线数量反转家族。
- `HYPE-EMA-Crossover`（历史别名：`HYPE-EMA-X`）：HYPE EMA 金叉/死叉家族，包括 V14 时代研究。
- `HYPE-1M-EMA-Crossover`（历史别名：`HYPE-1M-EMA-X`）：Binance HYPEUSDT `1m` EMA 金叉/死叉家族。
- `HYPE-EMA-Trend-Breakout`（历史别名：`HYPE-EMA-TB`）：HYPE EMA 趋势突破家族。
- `HYPE-5M-Pullback-Trail`（历史别名：`HYPE-5M-PBTR`）：Binance HYPE `5m` 回踩/恢复入场 + ATR trailing-stop 家族。
- `MU-HYPE-Transfer`（历史别名：`MU-HYPE-XFER`）：基于 HYPE trend kernel 的 MU 迁移研究。

## Active 代码规则

- Active package code 只限于可复用、有稳定接口的最小数据湖内核、数据归一化、数据质量检查、特征构建和因子计算。
- 交易所抓取、补洞、研究搜索和一次性研究导出脚本不再放进 `src/strategy_lab/` 或 `src/strategy_lab/data/`，必须放在对应 `research/.../scripts/`，并记录数据来源与质量校验。
- `archive/code/platform/` 只保留少量被长期研究文档引用的历史策略源码快照；它不是 active 平台，也不是可运行平台。
- 当前一次性研究脚本必须放在对应 research topic 或 family 的 `scripts/` 目录。
- 已不再定义 active research line 的历史一次性研究脚本放在 `archive/scripts/research/`。
- 除非用户明确要求考古历史实现，否则不要把 archive 里的代码当作当前事实来源。

## 术语口径

- `candidate`、`live`、`paper-live`、`dry-run`、`handoff` 或“交接版本”都属于 promotion 状态；进入这些状态前必须完成 live-executable 审计。
- `active research line` 指当前仍在 `research/` 下维护、会继续复现或更新结论的研究方向；不再维护的一次性历史脚本应归入 `archive/scripts/research/`。
- `current one-off research script` 指只服务某个研究问题的复现、搜索、审计、导出脚本；它可以保留在对应研究目录，但不应提升为 active package code。

## 硬规则索引

以下细则由 `.cursor/rules/` 维护，不在本文件重复展开：

- `data-quality-first.mdc`：数据来源、字段口径、缺口/重复/空值、raw/normalized 对齐和 data-quality blocker。
- `live-executable-strategy-research.mdc`：订单时序、成交假设、stop/lockout 审计和 promotion 前置条件。
- `research-report-storage.mdc`：新研究目录、Markdown 结论、脚本和 artifacts 的存放位置，以及 Canvas/legacy-canvas 边界。

