# MU Binance vs Yahoo 15m 对齐验证

> 迁移说明：本文由 legacy Cursor Canvas `mu-binance-yahoo-alignment.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：MU-HYPE-XFER legacy Canvas。

将 Binance MUUSDT TRADIFI_PERPETUAL 15m 与 Yahoo Finance MU 美股 15m includePrePost 按 UTC 时间戳精确对齐，验证永续价格是否贴近真实美股价格。

Source: Binance data lake + Yahoo Finance chart API · aligned 2026-04-07 13:30 UTC → 2026-06-16 23:45 UTC · 3,172 matched 15m bars.

> **结论**
> Binance MUUSDT 与 Yahoo 真盘 MU 在可对齐的 04:00-20:00 ET 区间高度一致：15m 收益相关性 0.995，日频收益相关性 0.9999，收盘价中位比值 1.00081。限制是 Yahoo 免费 15m 不覆盖 20:00-04:00 ET 夜盘，所以无法直接验证 V1 最关键的 overnight 段。

### 关键指标

| 指标 | 数值 |
| --- | --- |
| 15m return correlation | 0.9950 |
| 15m direction agreement | 93.66% |
| mean abs close diff | 0.0915% |
| daily return correlation | 0.9999 |

## 分时段收益相关性

X 轴：美东时段；Y 轴：15m 收益相关性与方向一致率。Source: reports/mu_binance_yahoo_15m_alignment_by_session.csv。

原 Canvas 使用图表展示；这里保留图表底层数据。

| 分类 | Return correlation | Direction agreement (%) |
| --- | --- | --- |
| premarket | 0.9943 | 93.56 |
| regular | 0.9969 | 97.07 |
| afterhours | 0.9818 | 88.25 |

## 误差幅度

X 轴：美东时段；Y 轴：15m 收益差绝对值，单位 bps。数值越低代表跟踪越紧。

原 Canvas 使用图表展示；这里保留图表底层数据。

| 分类 | Mean abs return diff (bps) | P95 abs return diff (bps) |
| --- | --- | --- |
| premarket | 5.93 | 16.09 |
| regular | 4.71 | 12.44 |
| afterhours | 4.87 | 12.38 |

### 分时段统计

| 时段 | 对齐 bars | 收益相关 | 方向一致 | 平均收益差 bps | P95 收益差 bps | 平均价格差 |
| --- | --- | --- | --- | --- | --- | --- |
| premarket | 1,072 | 0.9943 | 93.56% | 5.93 | 16.09 | 0.1029% |
| regular | 1,299 | 0.9969 | 97.07% | 4.71 | 12.44 | 0.0895% |
| afterhours | 800 | 0.9818 | 88.25% | 4.87 | 12.38 | 0.0793% |

> **对策略的含义**
> Binance MUUSDT 在盘前、常规盘、盘后都能很好贴住 Yahoo 真盘价格；regular session 最干净，afterhours 方向一致率下降到 88.25%。V1 的 overnight 逻辑仍需要更高质量美股夜盘数据源验证，Yahoo 免费数据无法覆盖。

## 产物路径

| 文件 | 内容 |
| --- | --- |
| scripts/compare_mu_binance_yahoo_alignment.py | 可重复对齐脚本 |
| reports/mu_binance_yahoo_15m_alignment.json | 整体与分时段统计 |
| reports/mu_binance_yahoo_15m_aligned.csv | 按 UTC 15m 对齐后的明细 |
| reports/mu_binance_yahoo_15m_alignment_by_session.csv | premarket / regular / afterhours 分桶统计 |
| data/external/us_equities/yahoo/symbol=mu/timeframe=15m/mu_15m_60d_include_prepost.parquet | Yahoo MU 15m includePrePost 原始拉取结果 |
