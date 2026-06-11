# Quant Strategy Lab

这个仓库的核心资产是 HYPE 策略研究文档与 Canvas 台账；代码主要服务于复现、回测和展示。

## 核心研究入口

- [HYPE 趋势策略研究](/Users/ZK/.cursor/projects/Users-ZK-OpenCode-quant-strategy-lab/canvases/hype-trend-strategy-research.canvas.tsx)：趋势突破族版本台账、结果矩阵、研究结论。
- [HYPE 15m Strategy Milestone Comparison](/Users/ZK/.cursor/projects/Users-ZK-OpenCode-quant-strategy-lab/canvases/hype-strategy-milestone-comparison.canvas.tsx)：K 线计数反转族里程碑对比。
- `docs/research/hype/README.md`：HYPE Markdown 规格书与诊断文档索引。
- `docs/research/hype/canvases/README.md`：Cursor Canvas 研究资产分类目录。
- `docs/README.md`：全项目文档目录。

## 文档结构

- `docs/research/hype/trend-breakout/`：HYPE 15m EMA96/384 趋势突破族。
- `docs/research/hype/candle-count/`：HYPE 10/8 反向 K 与 ATR 风控族。
- `docs/strategies/`：非 HYPE 策略说明。
- `docs/platform/`：数据湖、策略对比框架等平台约定。
- `docs/archive/`：历史实施计划和阶段记录。

## 代码入口

- Python 平台代码：`src/strategy_lab/`
- CLI 入口：`quant-strategy-lab`
- 策略与实验配置：`configs/`
- 前端策略实验室：`web/`
- 测试：`tests/`

## 快速开始

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

查看 CLI：

```bash
./.venv/bin/quant-strategy-lab --help
./.venv/bin/quant-strategy-lab layout
./.venv/bin/quant-strategy-lab factors
```
