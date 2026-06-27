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

之前趋势策略已经犯过“回测漂亮但不能实盘”的错误；近期 `HYPE-5M-Pullback-Trail`（历史别名：`HYPE-5M-PBTR`）V2.1A/V3.3/V4 又暴露了同类锁仓止损问题。以后任何不能通过 live-realistic 执行审计的策略，都必须明确降级为失败或待修复研究，不允许包装成可交接版本。

## 先读这些

- `AGENTS.md`：AI agent 在本仓库工作的规则。
- `research/README.md`：研究档案总入口、策略家族名称和版本号防串线规则。
- `research/hype/README.md`：HYPE 研究入口与阅读上下文。

## 当前结构

```text
data/
  raw/ normalized/ features/  # 本地数据湖核心层
  cache/ external/            # 本地缓存和外部数据

research/
  README.md
  hype/
    README.md
    5m-pullback-trail/
      scripts/    # 该策略的一次性复现、审计、搜索脚本
      artifacts/  # 该策略需要保留的 JSON/CSV/HTML 研究产物
    1m-ema-crossover/
    15m-ema-crossover/
    15m-ema-trend-breakout/
    15m-candle-count-reversal/
  mu/

src/strategy_lab/
  data/       # 最小数据湖内核：layout/schema/normalize/read-write/quality/features/factors

tests/              # active 数据湖内核测试

archive/
  code/platform/    # 少量被研究文档引用的历史策略源码快照
  configs/          # 旧顶层环境配置示例
  docs/             # 旧规划和实施文档
  research/         # 旧策略研究、HYPE transfer 和平台实验文档
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

新的策略研究默认在 `research/<asset>/<timeframe>-<strategy-family-slug>/` 内自管理；非资产专属研究可放在 `research/<topic>/`：

- `README.md`、主账和 `decision-log.md` 记录持久结论。
- `diagnostics/`、`ablations/`、`live-specs/`、`research-notes/` 按研究性质分类放 Markdown。
- `scripts/` 放只服务该研究的一次性复现、搜索、审计脚本。
- `artifacts/` 放需要随报告保留的 JSON、CSV、HTML、交易路径图等产物。

只有可复用的数据湖内核、归一化、质量审计、特征构建或因子计算工具，才应进入 `src/strategy_lab/`。交易所抓取、补洞、回测搜索和一次性导出默认放在对应 `research/.../scripts/`，并必须记录数据来源与质量校验。顶层 `reports/` 仍被 git 忽略，只能作为临时草稿或旧脚本缓存，不再作为 active research 的引用入口。

## HYPE 家族规则

不要只引用裸版本号。

请优先使用展开后的完整家族名；短 id 只作为历史别名：

- `HYPE-Candle-Count-Reversal-V35`（别名：`HYPE-CC-V35`）：K 线计数反转家族。
- `HYPE-EMA-Crossover-V14`（别名：`HYPE-EMA-X-V14`）：EMA 金叉/死叉家族。
- `HYPE-1M-EMA-Crossover`（别名：`HYPE-1M-EMA-X`）：Binance HYPEUSDT `1m` EMA 金叉/死叉家族。
- `HYPE-EMA-Trend-Breakout-V35`（别名：`HYPE-EMA-TB-V35`）：EMA 趋势突破家族。
- `HYPE-5M-Pullback-Trail-V2`（别名：`HYPE-5M-PBTR-V2`）：Binance HYPE `5m` 回踩/恢复 + ATR trailing stop 家族。
- `MU-HYPE-Transfer`（别名：`MU-HYPE-XFER`）：从 HYPE 趋势内核迁移到 MU 的研究方向。

即使版本号相同，它们也是不同策略，不应串联引用。

## 快速开始

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

本仓库不再提供通用数据同步 CLI。研究数据维护应使用对应 `research/.../scripts/` 下的明确脚本，并在研究文档或 decision log 中记录数据来源、覆盖范围和质量检查结果。
