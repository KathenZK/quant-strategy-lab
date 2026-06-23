# 文档索引

本目录围绕数据和研究证据组织，不再围绕旧策略平台组织。

## 主要入口

- `research/README.md`：研究档案总览。
- `research/STRATEGY_INDEX.md`：策略家族 id 和版本号防串线规则。
- `research/hype/AI_CONTEXT.md`：阅读 HYPE 研究材料前必须先看的上下文。
- `research/hype/README.md`：HYPE 研究入口。

## HYPE 研究

- `research/hype/families/candle-count-reversal/`：`HYPE-CC` 家族。
- `research/hype/families/ema-crossover/`：`HYPE-EMA-X` 家族。
- `research/hype/families/ema-trend-breakout/`：`HYPE-EMA-TB` 家族。
- `research/hype/transfer/`：暂保留的 HYPE 跨资产迁移验证历史材料，不是新的 HYPE 策略家族。
- `research/mu/`：`MU-HYPE-XFER` 迁移研究。

旧策略平台、比较框架、工作流、Dashboard 和非 HYPE 策略文档统一归档在顶层 `archive/`。

## 数据湖约定

本仓库是数据优先的量化研究档案。数据湖是主要工程资产，策略代码不再是主要组织层。

核心原则：

- 只保留一个本地数据湖：`data/raw`、`data/normalized`、`data/features`。
- 不创建按策略拆分的数据根目录。
- 研究脚本可以是临时的，但数据身份必须稳定。
- `reports/` 是本地运行产物目录，已被 git 忽略。
- 持久结论应写入 `docs/research/`。

标准布局：

```text
data/
  raw/
  normalized/
  features/
  _state/
  cache/
  external/
  reports/
  strategy_lab.duckdb

reports/
  _registry/
  runs/
  experiments/
```

说明：

- `data/raw`、`data/normalized`、`data/features` 是研究默认使用的数据湖核心层。
- `data/cache` 和 `data/external` 保存下载缓存或第三方外部数据。
- `data/reports` 只放和数据处理直接相关的本地产物。
- 顶层 `reports/` 是研究脚本和旧 run registry 的本地产物目录，已被 git 忽略；它不是长期知识入口。
- `strategy_lab.duckdb` 是本地仓库级查询/缓存数据库文件，默认不作为研究结论引用。

## OHLCV 分区

标准 OHLCV 数据按以下方式分区：

```text
data/normalized/ohlcv/
  exchange=binance/
    market_type=spot/
      timeframe=1h/
        date=2026-04-30/
          symbol=btc_usdt.parquet
```

业务唯一键是：

```text
exchange + market_type + timeframe + symbol + ts
```

查询和研究时必须显式过滤 `exchange`、`market_type`、`timeframe`、`symbol` 和日期范围。

`normalized/ohlcv` 应包含字段：

```text
ts
exchange
symbol
market_type
timeframe
base_asset
quote_asset
open
high
low
close
volume
quote_volume
trade_count
vwap
is_closed
source
date
```

字段规则：

- `ts` 使用 UTC。
- `is_closed = true` 的 K 线是研究默认安全口径。
- `source` 必须标识数据来源，例如 `ccxt`、`binance_kline_api` 或 `binance_vision`。
- 真实交易所 symbol 可以包含非 ASCII 字符，不要用 ASCII-only 假设过滤 symbol。

## Active Code 边界

`src/strategy_lab/` 下的 active package code 可以做：

- 数据抓取。
- 数据归一化。
- 数据真实性和质量审计。
- 可复用因子和特征构建。
- 窄口径研究数据集导出。

除非有明确决策，否则 active package code 不应重新扩展成通用策略平台。历史策略、工作流、Dashboard 和回测代码位于 `archive/code/platform/`。

## 研究输出规则

新的实验默认流程：

1. 使用标准数据湖。
2. 需要时生成一次性研究脚本。
3. 本地产物写入 `reports/`。
4. 持久结论写入 `docs/research/`。
5. 只有当代码属于可复用数据基础设施或窄口径数据集导出工具时，才提升到 `src/strategy_lab/`。
