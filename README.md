# Quant Strategy Lab

`Quant Strategy Lab` 是一个面向加密量化研究的研究优先平台，第一阶段聚焦两类场景：

- 中低频现货选币与轮动
- 永续合约因子研究与组合回测

当前已经落地的基础模块：

- 项目骨架与 CLI 入口
- 配置加载与目录布局
- 统一数据模型、标准化流程与 `Parquet + DuckDB` 数据湖
- `ccxt` 的 `OHLCV` / `funding` / `open interest` 抓取与落盘
- 15 个内置因子、批量因子计算与特征存储
- 因子研究实验室：`Rank IC`、分层收益、衰减、换手、walk-forward
- 组合回测引擎：手续费、滑点、资金费率、风控约束
- `PaperBroker`、风险管理与模拟交易会话
- Markdown 报告输出：因子报告、回测报告、模拟盘报告
- 配置驱动的一键策略编排、运行清单与增量刷新状态

## 项目结构

```text
docs/                    方案文档
configs/                 示例配置
research/notebooks/      研究笔记
src/signal_lab/          平台代码
tests/                   单元测试
```

## 快速开始

1. 创建虚拟环境并安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

2. 查看默认目录布局

```bash
./.venv/bin/quant-strategy-lab layout
```

3. 查看内置因子目录

```bash
./.venv/bin/quant-strategy-lab factors
```

4. 刷新一个交易对的现货或永续数据

```bash
./.venv/bin/quant-strategy-lab refresh-symbol --exchange binance --symbol BTC/USDT --timeframe 1h --market-type spot --limit 200
```

5. 计算一个交易对的全部可用因子

```bash
./.venv/bin/quant-strategy-lab build-features --exchange binance --symbol BTC/USDT --market-type spot
```

6. 对一个 symbol universe 生成因子报告

```bash
./.venv/bin/quant-strategy-lab factor-report --exchange binance --symbols BTC/USDT,ETH/USDT,SOL/USDT --factor ret_24 --market-type spot --benchmark-symbol BTC/USDT
```

7. 跑回测

```bash
./.venv/bin/quant-strategy-lab backtest-factor --exchange binance --symbols BTC/USDT,ETH/USDT,SOL/USDT --factor ret_24 --market-type spot
```

8. 跑模拟交易

```bash
./.venv/bin/quant-strategy-lab paper-trade --exchange binance --symbols BTC/USDT,ETH/USDT,SOL/USDT --factor ret_24 --market-type spot
```

9. 直接按策略工作流配置跑整条链路

```bash
./.venv/bin/quant-strategy-lab run-strategy --workflow-config configs/strategy.example.yaml
```

10. 查看特征产物清单和版本指纹

```bash
./.venv/bin/quant-strategy-lab feature-manifests --factor ret_24
```

11. 查看增量刷新状态

```bash
./.venv/bin/quant-strategy-lab refresh-state
```

12. 采集 liquidation 实时事件并写入数据湖

```bash
./.venv/bin/quant-strategy-lab collect-liquidations --duration-seconds 60
```

13. 写入隔离的 `MVP` 基准场景数据

```bash
./.venv/bin/quant-strategy-lab seed-trend-mvp -c configs/app.mvp-baseline.yaml
```

14. 运行正式 `MVP` 趋势主线配置

```bash
./.venv/bin/quant-strategy-lab run-strategy --workflow-config configs/trend_confirmation.mvp.yaml
```

15. 运行基准回测工作流

```bash
./.venv/bin/quant-strategy-lab run-strategy --workflow-config configs/trend_confirmation.mvp.baseline.yaml -c configs/app.mvp-baseline.yaml
```

16. 运行拥挤度反转策略工作流

```bash
./.venv/bin/quant-strategy-lab run-strategy --workflow-config configs/crowding_reversal.mvp.yaml
```

17. 写入拥挤度反转 baseline 数据

```bash
./.venv/bin/quant-strategy-lab seed-crowding-mvp -c configs/app.crowding-baseline.yaml
```

18. 运行拥挤度反转 baseline 回测

```bash
./.venv/bin/quant-strategy-lab run-strategy --workflow-config configs/crowding_reversal.mvp.baseline.yaml -c configs/app.crowding-baseline.yaml
```

19. 运行统一策略对比

```bash
./.venv/bin/quant-strategy-lab compare-strategies --comparison-config configs/strategy_comparison.mvp.baseline.yaml -c configs/app.mvp-baseline.yaml
```

20. 写入共享比较 baseline 数据

```bash
./.venv/bin/quant-strategy-lab seed-shared-comparison-mvp -c configs/app.shared-comparison-baseline.yaml
```

21. 运行共享 baseline 策略对比

```bash
./.venv/bin/quant-strategy-lab compare-strategies --comparison-config configs/strategy_comparison.shared-baseline.yaml -c configs/app.shared-comparison-baseline.yaml
```

## 文档

- 平台路线图：`docs/platform-roadmap.md`
- 中低频永续合约数据与策略决策：`docs/midfreq-perp-data-strategy-guide.md`
- 数据源与表结构规范：`docs/data-source-spec.md`
- MVP 实施计划：`docs/mvp-implementation-plan.md`
- 趋势确认主线 MVP：`docs/trend-confirmation-mvp.md`
- 趋势确认主线基准报告：`docs/trend-confirmation-mvp-baseline.md`
- 策略配置示例：`configs/strategy.example.yaml`
- 趋势确认正式配置：`configs/trend_confirmation.mvp.yaml`
- 拥挤度反转正式配置：`configs/crowding_reversal.mvp.yaml`
- 拥挤度反转 MVP：`docs/crowding-reversal-mvp.md`
- 拥挤度反转基准报告：`docs/crowding-reversal-mvp-baseline.md`
- 策略对比框架：`docs/strategy-comparison-framework.md`
- 趋势 vs 拥挤度反转基准对比：`docs/trend-vs-crowding-baseline.md`
- 趋势 vs 拥挤度反转共享基准对比：`docs/trend-vs-crowding-shared-baseline.md`

## 下一步

接下来优先补齐：

1. 接入更多交易所与 `basis` / `liquidations` / 链上数据
2. 做更完整的组合归因和策略调度
3. 把 Paper broker 进一步扩成 Live broker
