# Quant Strategy Lab

本仓库现在定位为“数据优先”的量化研究档案，而不是通用策略平台。

更重要的是：本仓库研究的是**线上可实盘执行的策略**，不是为了制造虚幻的回测假象。任何策略在进入 live、paper-live、dry-run、交接或候选状态前，都必须先证明它能被真实订单时序复现。

长期维护的核心资产是：

- `data/` 下的本地数据湖。
- `research/` 下的研究文档和策略家族台账。
- `src/strategy_lab/` 下较窄范围的数据、归一化、质量检查、特征和研究导出工具。

旧策略平台、工作流引擎、Dashboard、泛化回测层和早期规划文档已经归档到 `archive/`。

## 实盘可执行性是硬门槛

这是本项目的沉痛教训：如果回测依赖无法真实成交的假设，它不是“高收益候选”，而是失败诊断。

尤其要先审计：

- 进出场订单在实盘中是否能按同一时序发出和成交。
- 止损、移动止损、保护止损是否能在当时真实挂上，而不是在价格已经穿越后仍按旧 stop 价成交。
- `min_hold_bars`、锁仓期、延迟退出、trailing stop 是否隐藏了不可承受或不可复现的路径风险。
- 手续费、滑点、stop-market 滑点、订单失败、缺失 K 线、重启恢复、仓位和 emergency stop 是否已经进入验收口径。

之前趋势策略已经犯过“回测漂亮但不能实盘”的错误；近期 `HYPE-5M-PBTR-V2.1A/V3.3/V4` 又暴露了同类锁仓止损问题。以后任何不能通过 live-realistic 执行审计的策略，都必须明确降级为失败或待修复研究，不允许包装成可交接版本。

## 先读这些

- `AGENTS.md`：AI agent 在本仓库工作的规则。
- `research/STRATEGY_INDEX.md`：策略家族 id 和版本号防串线规则。
- `research/hype/AI_CONTEXT.md`：阅读 HYPE 研究材料前必须先看的上下文。
- `research/hype/README.md`：HYPE 研究入口。
- `research/README.md`：研究档案总入口。

## 当前结构

```text
data/
  raw/ normalized/ features/  # 本地数据湖核心层
  cache/ external/ reports/   # 本地缓存、外部数据和数据相关产物

research/
  README.md
  STRATEGY_INDEX.md
  hype/
    AI_CONTEXT.md
    5m-pullback-trail/
      scripts/    # 该策略的一次性复现、审计、搜索脚本
      artifacts/  # 该策略需要保留的 JSON/CSV/HTML 研究产物
    ema-crossover/
    ema-trend-breakout/
    candle-count-reversal/
    transfer/
  mu/

src/strategy_lab/
  data/       # 数据抓取、归一化、质量检查、因子和特征
    cli.py    # 数据优先的 CLI 入口
    ingest/   # 交易所、数据源和外部市场数据抓取
    exporters/ # 可复用的窄口径研究数据集导出工具

tests/              # active 数据层和 CLI 测试

archive/
  code/platform/    # 旧策略平台、工作流和平台测试
  code/web/         # 旧 Dashboard 前端
  code/web-root/    # 旧 Dashboard 根 package/workspace
  configs/          # 旧顶层环境配置示例
  docs/             # 旧规划和实施文档
  research/         # 旧策略研究和平台实验文档
  scripts/research/ # 少量仍未归入 active research 的历史脚本
  reports/legacy/   # 少量曾经入库的旧报告产物
```

## 数据湖约定

本仓库只保留一个本地数据湖：`data/raw`、`data/normalized`、`data/features`。不要按策略新建数据根目录；策略研究应显式声明数据来源、交易所、市场类型、周期、symbol 和时间范围。

标准 OHLCV 分区示例：

```text
data/normalized/ohlcv/
  exchange=binance/
    market_type=spot/
      timeframe=1h/
        date=2026-04-30/
          symbol=btc_usdt.parquet
```

查询唯一键是 `exchange + market_type + timeframe + symbol + ts`。`ts` 使用 UTC，`is_closed = true` 的 K 线是研究默认安全口径，`source` 必须标识数据来源。

## 研究资产规则

新的策略研究默认在 `research/<topic>/` 或 `research/hype/<family>/` 内自管理：

- `README.md`、主账和 `decision-log.md` 记录持久结论。
- `diagnostics/`、`ablations/`、`live-specs/`、`research-notes/` 按研究性质分类放 Markdown。
- `scripts/` 放只服务该研究的一次性复现、搜索、审计脚本。
- `artifacts/` 放需要随报告保留的 JSON、CSV、HTML、交易路径图等产物。

只有可复用的数据抓取、归一化、质量审计、特征构建或窄口径数据集导出工具，才应进入 `src/strategy_lab/`。顶层 `reports/` 仍被 git 忽略，只能作为临时草稿或旧脚本缓存，不再作为 active research 的引用入口。

## HYPE 家族规则

不要只引用裸版本号。

请使用明确的家族 id：

- `HYPE-CC-V35`：K 线计数反转家族。
- `HYPE-EMA-X-V14`：EMA 金叉/死叉家族。
- `HYPE-EMA-TB-V35`：EMA 趋势突破家族。
- `MU-HYPE-XFER`：从 HYPE 趋势内核迁移到 MU 的研究方向。

即使版本号相同，它们也是不同策略，不应串联引用。

## 快速开始

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

检查数据 CLI：

```bash
./.venv/bin/quant-strategy-lab --help
./.venv/bin/quant-strategy-lab layout
./.venv/bin/quant-strategy-lab factors
```
