# Signal Lab

`Signal Lab` 是一个面向加密量化研究的研究优先平台，第一阶段聚焦两类场景：

- 中低频现货选币与轮动
- 永续合约因子研究与组合回测

当前已经落地的基础模块：

- 项目骨架与 CLI 入口
- 配置加载与目录布局
- 统一数据模型与数据湖路径抽象
- `ccxt` OHLCV 抓取与原始层 Parquet 落盘
- 因子元数据、注册表与首批基础因子
- 因子评估函数（forward return、Rank IC、分层收益）

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
signal-lab layout
```

3. 查看内置因子目录

```bash
signal-lab factors
```

4. 抓取一份样例 K 线到原始数据湖

```bash
signal-lab fetch-ohlcv --exchange binance --symbol BTC/USDT --timeframe 1h --market-type spot --limit 200
```

## 文档

- 平台路线图：`docs/platform-roadmap.md`

## 下一步

接下来优先补齐：

1. `funding`、`open interest` 等衍生品数据抓取
2. 组合回测引擎
3. Paper broker 与风控闭环
