# 脚本入口

本目录只存放 `BTC-15M-EMA-Trend-Breakout` 当前研究所需的一次性脚本，不是 runner 或共享内核。

## 数据刷新与审计

[`refresh_and_audit_btc_15m_data.py`](refresh_and_audit_btc_15m_data.py) 仅处理 Binance USD-M Futures `BTCUSDT` perpetual `15m`：

- 从 `2024-07-14T00:00:00Z` 刷新至 Binance 服务器时间所确定的最新已闭合 `15m` K 线；
- 从 Binance Vision 官方 monthly funding archives 读取完整月份，并用 FAPI funding history 补齐近期尾部；
- 成功时写入标准 raw/normalized OHLCV、raw/normalized funding 与 compatibility funding，而不是只写本家族缓存；
- 审计 UTC 连续性、重复、关键空值、OHLC/成交量、`is_closed`、raw/normalized 逐列对齐及 funding 最大间隔；
- 任一 data-quality blocker 会保留审计报告并以非零状态退出，且不会刷新标准数据分区。

联网审计但完全不写磁盘：

```shell
python research/btc/15m-ema-trend-breakout/scripts/refresh_and_audit_btc_15m_data.py --no-write --timeout 60
```

刷新标准数据湖并写入本家族审计产物：

```shell
python research/btc/15m-ema-trend-breakout/scripts/refresh_and_audit_btc_15m_data.py --timeout 60
```

`--timeout` 是每次 HTTP 请求的秒数。`--no-write` 不写 archives、标准数据湖或本家族 artifacts；审计 JSON 仅打印到标准输出。

## V40 正式搜索与一次性 holdout reveal

以下三个入口动态加载并校验共享
[`ema-trend-breakout/v2` 内核](../../../_shared-kernels/ema-trend-breakout/v2/engine.py)
SHA256
`36e5d10c0d281701c46446344dd50af7a7589ec03285be3289e82362e1c2917a`。
搜索进程只加载 `ts < holdout_start`；reveal 进程只能使用已经冻结并通过全部
SHA 校验的 selection，不允许重新选参。

先根据最新无 blocker 审计冻结时间边界：

```shell
uv run python research/btc/15m-ema-trend-breakout/scripts/freeze_btc_15m_v40_splits.py
```

该命令要求审计终点严格等于 `2026-07-17T14:45:00Z`，并写入
[`btc_15m_v40_frozen_splits_2026-07-17.json`](../artifacts/btc_15m_v40_frozen_splits_2026-07-17.json)。
随后运行正式搜索：

```shell
uv run python research/btc/15m-ema-trend-breakout/scripts/search_btc_15m_v40_transfer.py
```

搜索默认使用 `min(8, cpu_count)` 个 macOS `fork` worker，通过 copy-on-write
共享父进程已加载的 frame、funding、features 与冻结内核；worker 只返回 metrics，
所有 artifact 仍只由父进程最终写入。可用 `--workers N` 调整并发度；`--workers 1`
严格走原串行路径。候选结果始终恢复为输入 spec 顺序，worker 异常会传播到父进程。

搜索包含 V40 原样 baseline、Stage1A `216` 个 long-only 变体、由 train-only
稳定高原选出的三个 seed 所扩展的 Stage1B `72` 个双向变体；Stage1 没有合格
高原时自动运行 stepwise Stage2。第一波对最多四个 near-miss 分别只增加一个
组件：volume-only `3` 项、ATR-regime-only `2` 项、exit-only `4` 项，最多
`36` 项；然后每个 seed 只取第一波 development 表现最好的单组件父项，再增加
一个不同类型组件，第二波最多 `28` 项，Stage2 总计最多 `64` 项。不同 step 与
component type 不互作邻居；CSV 保留 component、parent 和相对 parent 的改善。
进度写到 stdout，只保留候选 metrics，不累计保存每个候选的 equity。产物为：

- [`btc_15m_v40_candidate_metrics_2026-07-17.csv`](../artifacts/btc_15m_v40_candidate_metrics_2026-07-17.csv)
- [`btc_15m_v40_search_summary_2026-07-17.json`](../artifacts/btc_15m_v40_search_summary_2026-07-17.json)
- [`btc_15m_v40_frozen_selection_2026-07-17.json`](../artifacts/btc_15m_v40_frozen_selection_2026-07-17.json)

确认 selection 已冻结后，以独立进程执行唯一一次 holdout reveal：

```shell
uv run python research/btc/15m-ema-trend-breakout/scripts/reveal_btc_15m_v40_holdout.py
```

reveal 会输出 summary、逐笔交易、holdout equity 与完整 development
`IS60d-gap10d-OOS30d` walk-forward CSV。最近 `1d/7d/30d/90d/182d/365d`
均以数据终点锚定并独立 flat-reset 回测，不受 holdout 起点截断。summary 另含
post-reveal gate：holdout 成本后正收益、至少 `30` 笔、MDD 不超过 `25%`、
双倍成本仍正收益、development WFO 正收益 fold 占比超过 `50%`；冻结角色为
near-miss 时无论揭示结果如何都不得升级为 candidate。若同一 selection 已有完整
reveal，脚本只打印并复核既有产物；若 selection 或任一 SHA 不同则拒绝覆盖。

不读取行情、不写产物的入口自检：

```shell
uv run python research/btc/15m-ema-trend-breakout/scripts/freeze_btc_15m_v40_splits.py --smoke
uv run python research/btc/15m-ema-trend-breakout/scripts/search_btc_15m_v40_transfer.py --smoke --workers 1
uv run python research/btc/15m-ema-trend-breakout/scripts/reveal_btc_15m_v40_holdout.py --smoke
```

两项候选的串行/并行 metrics 完全一致性测试（只读取 development 子集，不写
artifact）：

```shell
uv run python research/btc/15m-ema-trend-breakout/scripts/search_btc_15m_v40_transfer.py --parallel-equivalence-test --workers 2
```
