# AI Agent 仓库规则

本仓库是 data-first 的量化策略研究档案。研究对象可以覆盖加密货币、美股、A 股、港股、大宗商品等多个市场；HYPE 只是当前较早展开的一条研究线。线上执行在同级仓库 `/Users/ZK/OpenCode/quant-runner` 中进行。

`.cursor/rules/` 是硬性工作约束的唯一细则来源；本文件只补充仓库入口、命名口径、active code 边界和术语。不要把 `.cursor/rules/` 的细则复制进本文件、根 `README.md` 或 `research/README.md`；若同一事项重复出现，以更具体、更严格的表述为准。

## 必读入口

当需要基于某个资产或策略家族作结论、修改研究文档或运行相关脚本前，必须先打开：

1. `research/README.md`：家族路由表与阅读顺序。
2. 对应资产或主题目录的 `README.md`，例如 `research/hype/README.md`、`research/mu/README.md`。
3. 对应策略家族的 `README.md` 与 core ledger / 主账。

## 命名与版本口径

- 不要根据 `V13`、`V21`、`V35`、`V36` 这类裸版本号判断策略身份；版本号只在具体资产、市场、周期和策略家族里有意义。
- 标准 family name 使用展开写法，优先包含资产、周期和机制；短 id 只作为历史别名。家族清单与别名以 `research/README.md` 和各资产 README 的路由表为准，不在本文件重复维护。
- 当用户要求"登记为 Vx / 记录为 Vx / 冻结为 Vx / promote 为 Vx"时，必须更新对应家族 core ledger / 主账（细则见 `.cursor/rules/research-report-storage.mdc`）。只更新 canonical spec、research note、diagnostic 或 decision log 不算完成版本登记。
- 所有新增或更新的长期研究文档默认使用中文，除非用户明确要求其他语言；策略名、版本号、参数、路径、指标名和状态术语可以保留英文原文。

## 术语口径

- 策略状态词（`diagnostic baseline`、`paper-audit observation`、`forward-test required`、`candidate`、`dry-run`、`live` 等）的定义与状态机以 `research/strategy-status-glossary.md` 为唯一来源。
- `candidate`、`live`、`dry-run`、`handoff` 或"交接版本"都属于 promotion 状态；进入这些状态前必须完成 live-executable 审计。本仓库不定义额外的模拟盘阶段；模拟盘/仿真运行统一称为 `dry-run`，真实小额下单归入 `live` 并注明 notional 与风险上限。
- `active research line` 指当前仍在 `research/` 下维护、会继续复现或更新结论的研究方向；不再维护的一次性历史脚本应归入 `archive/scripts/research/`。
- `current one-off research script` 指只服务某个研究问题的复现、搜索、审计、导出脚本；它可以保留在对应研究目录，但不应提升为 active package code。

## Active 代码规则

- Active package code 只限于可复用、有稳定接口的最小数据湖内核、数据归一化、数据质量检查、特征构建和因子计算，放在 `src/strategy_lab/`。
- 交易所抓取、补洞、研究搜索和一次性研究导出脚本必须放在对应 `research/.../scripts/`，并记录数据来源与质量校验。
- 被多个资产或家族复用的研究引擎放在 `research/_shared-kernels/`，按冻结版本目录管理（细则见 `.cursor/rules/research-report-storage.mdc`）。
- `archive/code/platform/` 只保留少量被长期研究文档引用的历史策略源码快照；它不是 active 平台，也不是可运行平台。
- 除非用户明确要求考古历史实现，否则不要把 archive 里的代码当作当前事实来源。

## 硬规则索引

细则由 `.cursor/rules/` 维护，不在本文件展开：

- `data-quality-first.mdc`：数据来源、字段口径、缺口/重复/空值、raw/normalized 对齐和 data-quality blocker。
- `live-executable-strategy-research.mdc`：订单时序、成交假设、stop/lockout 审计和 promotion 前置条件。
- `backtest-slice-standard.mdc`：回测默认包含最近 `1d/7d/1m/3m/6m/1y` 分片，并说明分片是否参与选参。
- `backtest-execution-costs.mdc`：Binance 回测默认手续费 `0.001`、滑点 `4 bps`；其他市场需明确成本口径。
- `research-report-storage.mdc`：研究目录、core ledger、索引更新义务、共享内核、artifacts 存放和 Canvas 边界。
- `lab-runner-handoff.mdc`：向 `quant-runner` 交接的规格契约、双向同步和 `forward-tracking/` 回流要求。
