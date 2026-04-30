# Strategy Lab 数据湖与实验产物约定

这份文档定义 `quant-strategy-lab` 项目内部的数据、策略实验、回测产物和前端展示约定。

项目定位是一个策略实验室：不同策略共享同一个数据湖；策略可以单独配置 universe、参数、风险和执行假设；所有回测、扫描和实验记录写到同一个报告与 registry 区域，供后端 API 和前端统一展示。

## 1. 核心原则

- 项目只有一套本地数据湖：`data/raw`、`data/normalized`、`data/features`。
- 不按策略、时间窗口或临时研究任务创建新的数据根目录，例如不再使用 `data/binance-spot-1h-local` 这类 profile 目录。
- 策略共享行情、因子和特征数据；策略差异通过 `configs/` 里的 workflow、strategy params、risk 和 execution 配置表达。
- 回测报告、实验记录、扫描结果和结构化产物统一写入 `reports/`，不按策略另建独立 reports 根目录。
- 前端只面向统一数据湖和统一 reports/registry 展示，不需要理解某个策略的私有数据目录。
- 数据湖是标准，策略代码适配数据湖；不能为了某个策略在数据湖里新增兼容副本。

## 2. 标准目录结构

项目根目录下的数据和报告结构固定为：

```text
data/
  raw/
  normalized/
  features/

reports/
  _registry/
    runs.sqlite
  runs/
  experiments/
  comparisons/
```

其中：

- `data/raw`：交易所原始或近原始数据，保留来源语义，便于追溯。
- `data/normalized`：策略和因子默认读取的标准化数据。
- `data/features`：可复用因子、特征和 manifest。
- `reports/_registry/runs.sqlite`：所有 workflow、experiment、comparison 的统一运行索引。
- `reports/runs`、`reports/experiments`、`reports/comparisons`：结构化回测产物、指标、交易记录和报告文件。

不推荐的目录：

```text
data/binance-spot-1h-local/
data/spot-cta/
data/strategy-a/
reports/spot-cta-only/
```

这些目录会让同一批行情被复制多份，后续难以判断哪个版本是最新、干净、可回测的数据。

## 3. 数据湖分区规范

周期行情数据必须按 canonical 分区写入：

```text
data/normalized/ohlcv/
  exchange=binance/
    market_type=spot/
      timeframe=1h/
        date=2026-04-30/
          symbol=btc_usdt.parquet
          symbol=eth_usdt.parquet
```

关键维度：

- `exchange`：交易所，例如 `binance`、`okx`、`bybit`。
- `market_type`：市场类型，例如 `spot`、`perp`。
- `timeframe`：周期，例如 `1m`、`5m`、`1h`、`4h`、`1d`。
- `date`：按 K 线开始时间 `ts.date()` 分区，不是写入时间。
- `symbol`：保留在 parquet 字段中，同时可作为文件名，例如 `symbol=btc_usdt.parquet`。

OHLCV 的唯一业务键是：

```text
exchange + market_type + timeframe + symbol + ts
```

读取 OHLCV 时必须显式过滤 `exchange`、`market_type`、`timeframe` 和需要的 `symbol/date range`，避免不同交易所、市场类型或周期混在一起。

## 4. 标准字段要求

`normalized/ohlcv` 至少包含：

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

约定：

- `ts` 使用 UTC 时间。
- `is_closed = true` 的 K 线才能进入策略回测和扫描。
- `quote_volume`、`trade_count`、`vwap` 是策略判断流动性和成交质量的重要字段，不能 silently drop。
- `source` 必须能说明数据来源，例如 `binance_kline_api`、`ccxt`、`binance_vision`。
- Unicode symbol 是合法的，例如 `币安人生/USDT`，不能用 ASCII 规则过滤真实交易对。

## 5. 策略如何共享数据

策略不能拥有自己的行情数据目录。策略需要差异化时，通过配置表达：

```text
configs/workflows/strategies/
  spot_cta_trend.binance.spot.1h.local.yaml
  trend_confirmation.mvp.yaml
  ...
```

策略可定制的内容包括：

- `exchange`
- `market_type`
- `timeframe`
- `symbols` 或动态 universe 规则
- 因子参数
- signal threshold
- allocator 参数
- risk limits
- execution assumptions

策略读取同一套 `data/normalized`，生成自己的 signal、target weights、trades 和 backtest report。

例如现货 CTA 策略可以读取：

```text
exchange = binance
market_type = spot
timeframe = 1h
quote_asset = USDT
```

另一个策略也可以读取同一批 Binance spot 1h 数据，但用不同 universe、不同因子、不同持仓规则。

## 6. 配置约定

本地 app profile 应指向标准数据湖：

```yaml
storage:
  shared: false
  root_dir: data
  raw_dir: data/raw
  normalized_dir: data/normalized
  features_dir: data/features
  reports_dir: reports
```

不要为某个策略配置新的 `root_dir`：

```yaml
# 不推荐
storage:
  root_dir: data/binance-spot-1h-local
  reports_dir: reports/binance-spot-1h-local
```

如果需要隔离实验结果，应使用 run id、workflow name、experiment name 或 comparison name 区分，而不是复制行情数据。

## 7. 报告和实验记录

所有策略运行都写入同一个 `reports/` 根目录。

推荐产物：

```text
reports/
  _registry/
    runs.sqlite
  runs/
    <run_id>/
      metrics.json
      prices.parquet
      signals.parquet
      weights.parquet
      trades.parquet
      equity_curve.parquet
  experiments/
  comparisons/
```

统一 registry 需要记录：

- run id
- workflow name
- strategy type
- strategy params
- universe
- data range
- timeframe
- metrics
- artifact paths
- created time

这样前端可以从一个 registry 中列出所有策略运行、回测表现、交易记录和对比结果。

## 8. 前端展示约定

前端不直接关心某个策略的数据目录。前端通过后端 API 读取：

- 数据湖概览：有哪些 exchange、market type、timeframe、symbol、date range。
- 策略列表：有哪些 strategy config、可运行 workflow。
- 回测列表：来自 `reports/_registry/runs.sqlite`。
- 单次回测详情：读取对应 run artifact，例如 metrics、equity curve、signals、weights、trades。
- 策略对比：读取 comparison artifact 和 registry metadata。

前端展示层应该围绕“同一个数据湖 + 多个策略实验 + 统一报告中心”组织，而不是围绕文件夹名组织。

## 9. 数据清理原则

如果发现历史目录或脏数据：

1. 确认没有同步、扫描或回测进程正在读取。
2. 保留最新、可信、字段完整的数据。
3. 删除旧的 strategy/profile 数据目录。
4. 确保最终只剩 `data/raw`、`data/normalized`、`data/features`。
5. 重新跑数据覆盖统计和关键字段检查。
6. 用至少一个 workflow scanner 验证策略可读取。

本项目当前应保持：

```text
data/
  raw/
  normalized/
  features/
```

如果临时需要隔离重拉数据，完成验证后必须合并回标准三目录，并删除临时目录。

## 10. 常用命令

查看数据湖布局：

```bash
./.venv/bin/quant-strategy-lab layout -c configs/environments/binance-spot-1h-local.yaml
```

同步 Binance spot 1h：

```bash
./.venv/bin/quant-strategy-lab sync-binance-spot-ohlcv \
  --timeframe 1h \
  --since-days 90 \
  --limit 3000 \
  --max-symbols 0 \
  --min-quote-volume 0 \
  -c configs/environments/binance-spot-1h-local.yaml
```

扫描现货 CTA：

```bash
./.venv/bin/quant-strategy-lab scan-spot-cta \
  --workflow-config configs/workflows/strategies/spot_cta_trend.binance.spot.1h.local.yaml \
  --use-local-universe \
  --min-avg-dollar-volume 0 \
  --min-history-bars 120 \
  --max-symbols 0 \
  --top-n 20 \
  -c configs/environments/binance-spot-1h-local.yaml
```

运行策略回测：

```bash
./.venv/bin/quant-strategy-lab run-strategy \
  --workflow-config configs/workflows/strategies/spot_cta_trend.binance.spot.1h.local.yaml \
  -c configs/environments/binance-spot-1h-local.yaml
```

## 11. 判断是否符合约定

符合：

- 多个策略读取同一套 `data/normalized/ohlcv`。
- 不同策略通过 `configs/workflows/strategies/*.yaml` 定制。
- 回测结果统一进入 `reports/` 和 `reports/_registry/runs.sqlite`。
- 前端通过统一 API 展示数据、策略、回测和对比。

不符合：

- 每个策略各自维护一份行情数据。
- `data/` 下出现 `strategy-name`、`timeframe-profile`、`local-copy` 这类长期目录。
- 报告散落在多个不可统一索引的 reports 根目录。
- 前端需要根据策略名猜测数据文件夹。

