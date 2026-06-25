# MU Binance vs Polygon 15m 对齐验证

> 迁移说明：本文由 legacy Cursor Canvas `mu-binance-polygon-alignment.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：MU-HYPE-XFER legacy Canvas。

已用 Polygon 拉取 MU 最近一年 15m 美股 aggregate，并与 Binance MUUSDT TRADIFI_PERPETUAL 按 UTC 15m 时间戳对齐。

Source: Binance data lake + Polygon aggregates · Polygon span 2025-06-17 08:00 UTC → 2026-06-16 23:45 UTC · aligned overlap 2026-04-07 13:30 UTC → 2026-06-16 23:45 UTC.

> **拉取成功**
> Polygon key 可用，已拿到 MU 一年 15m 数据：15,951 根，覆盖 04:00-20:00 ET 的盘前、常规盘和盘后。对齐 Binance 后，价格和收益跟踪结果与 Yahoo 验证高度一致。

### 关键指标

| 指标 | 数值 |
| --- | --- |
| Polygon one-year 15m bars | 15,951 |
| 15m return correlation | 0.9951 |
| 15m direction agreement | 94.05% |
| overnight bars returned | 0 |

## 分时段收益相关性

X 轴：美东时段；Y 轴：15m 收益相关性与方向一致率。Source: reports/mu_binance_polygon_15m_alignment_by_session.csv。

原 Canvas 使用图表展示；这里保留图表底层数据。

| 分类 | Return correlation | Direction agreement (%) |
| --- | --- | --- |
| premarket | 0.9945 | 93.23 |
| regular | 0.997 | 97.07 |
| afterhours | 0.9814 | 90.24 |

## 误差幅度

X 轴：美东时段；Y 轴：15m 收益差绝对值，单位 bps。常规盘误差最低，盘后相关性最弱。

原 Canvas 使用图表展示；这里保留图表底层数据。

| 分类 | Mean abs return diff (bps) | P95 abs return diff (bps) |
| --- | --- | --- |
| premarket | 5.85 | 15.31 |
| regular | 4.69 | 12.36 |
| afterhours | 4.98 | 12.46 |

### 分时段统计

| 时段 | 对齐 bars | 收益相关 | 方向一致 | 平均收益差 bps | P95 收益差 bps | 平均价格差 |
| --- | --- | --- | --- | --- | --- | --- |
| premarket | 1,078 | 0.9945 | 93.23% | 5.85 | 15.31 | 0.1051% |
| regular | 1,299 | 0.9970 | 97.07% | 4.69 | 12.36 | 0.0897% |
| afterhours | 800 | 0.9814 | 90.24% | 4.98 | 12.46 | 0.0822% |

> **关键限制**
> Polygon 本次 aggregates 查询没有返回 20:00-04:00 ET overnight bars。它能把一年期盘前、盘中、盘后验证完整，但不能直接验证 Binance 夜盘价格发现段。

## 产物路径

| 文件 | 内容 |
| --- | --- |
| scripts/fetch_polygon_equity_aggregates.py | Polygon US stock aggregate 下载脚本 |
| data/external/us_equities/polygon/symbol=mu/timeframe=15m/mu_15m_2025-06-17_2026-06-17_adjusted.parquet | MU 一年 15m Polygon 数据 |
| reports/mu_us_equity_polygon_15m_2025-06-17_2026-06-17_summary.json | Polygon 数据覆盖与价格统计 |
| scripts/compare_mu_binance_polygon_alignment.py | Binance vs Polygon 对齐脚本 |
| reports/mu_binance_polygon_15m_alignment.json | 整体与分时段对齐统计 |
| reports/mu_binance_polygon_15m_aligned.csv | UTC 15m 对齐明细 |
| reports/mu_binance_polygon_15m_alignment_by_session.csv | 分时段统计 |
