# 脚本入口

本目录只保存 `BTC-15M-Keltner-Trend-Breakout` 当前研究所需的一次性脚本，不是 runner 或共享内核。

[`research_btc_15m_keltner_trend_breakout.py`](research_btc_15m_keltner_trend_breakout.py)读取已通过审计的 Binance USD-M `BTCUSDT` perpetual 原生 `15m` 标准数据湖与官方 funding，执行冻结搜索和一次 holdout 揭示。

入口自检：

```shell
uv run python research/btc/15m-keltner-trend-breakout/scripts/research_btc_15m_keltner_trend_breakout.py smoke
```

仅使用 train/validation 搜索并冻结选择：

```shell
uv run python research/btc/15m-keltner-trend-breakout/scripts/research_btc_15m_keltner_trend_breakout.py search
```

验证冻结选择和候选 CSV 哈希后执行一次 holdout 揭示：

```shell
uv run python research/btc/15m-keltner-trend-breakout/scripts/research_btc_15m_keltner_trend_breakout.py reveal
```

脚本固定 fee `0.001`/fill、adverse slippage `4 bps`/fill、历史 funding、下一根 open 入场、gap-aware stop、`stop-first` 冲突和固定 `1.0x` allocation。`reveal` 已完成；同一选择再次运行只读取既有揭示产物。
