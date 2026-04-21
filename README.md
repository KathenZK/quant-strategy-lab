# Signal Lab

`Signal Lab` 是一个面向加密量化研究的研究优先平台，第一阶段聚焦两类场景：

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
./.venv/bin/signal-lab layout
```

3. 查看内置因子目录

```bash
./.venv/bin/signal-lab factors
```

4. 刷新一个交易对的现货或永续数据

```bash
./.venv/bin/signal-lab refresh-symbol --exchange binance --symbol BTC/USDT --timeframe 1h --market-type spot --limit 200
```

5. 计算一个交易对的全部可用因子

```bash
./.venv/bin/signal-lab build-features --exchange binance --symbol BTC/USDT --market-type spot
```

6. 对一个 symbol universe 生成因子报告

```bash
./.venv/bin/signal-lab factor-report --exchange binance --symbols BTC/USDT,ETH/USDT,SOL/USDT --factor ret_24 --market-type spot --benchmark-symbol BTC/USDT
```

7. 跑回测

```bash
./.venv/bin/signal-lab backtest-factor --exchange binance --symbols BTC/USDT,ETH/USDT,SOL/USDT --factor ret_24 --market-type spot
```

8. 跑模拟交易

```bash
./.venv/bin/signal-lab paper-trade --exchange binance --symbols BTC/USDT,ETH/USDT,SOL/USDT --factor ret_24 --market-type spot
```

9. 直接按策略工作流配置跑整条链路

```bash
./.venv/bin/signal-lab run-strategy --workflow-config configs/strategy.example.yaml
```

10. 查看特征产物清单和版本指纹

```bash
./.venv/bin/signal-lab feature-manifests --factor ret_24
```

11. 查看增量刷新状态

```bash
./.venv/bin/signal-lab refresh-state
```

## 文档

- 平台路线图：`docs/platform-roadmap.md`
- 策略配置示例：`configs/strategy.example.yaml`

## 下一步

接下来优先补齐：

1. 接入更多交易所与 `basis` / `liquidations` / 链上数据
2. 做更完整的组合归因和策略调度
3. 把 Paper broker 进一步扩成 Live broker
