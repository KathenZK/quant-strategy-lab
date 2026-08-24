# Scripts

- [`fetch_gold_gc_stooq_snapshot.py`](fetch_gold_gc_stooq_snapshot.py)：下载并校验固定 commit
  的 Stooq `GC.F` 快照，将日线按日写入统一 raw 数据湖，保留 `raw_unaccepted` provenance。
- [`research_gold_1d_multi_speed_tsmom.py`](research_gold_1d_multi_speed_tsmom.py)：加载 raw
  分区、执行四分支与两成本版本、写出配置/指标/路径/年度结果和中文诊断。
- [`render_gold_1d_multi_speed_tsmom.py`](render_gold_1d_multi_speed_tsmom.py)：由同一 retained
  path CSV 生成自包含交互 HTML。
- [`fetch_gold_gc_yahoo_recent.py`](fetch_gold_gc_yahoo_recent.py)：获取 2020 年起 Yahoo Chart
  API `GC=F` raw quote OHLC，作为 2022–2026 独立近期段的预热与行情输入。
- [`research_gold_1d_multi_speed_tsmom_recent.py`](research_gold_1d_multi_speed_tsmom_recent.py)：
  用冻结规则运行 2021-12 起的近期扩展，并加入 Buy&Hold 基准。

复现命令将在[诊断报告](../diagnostics/gold-1d-ms-tsmom-backtest-2026-08-18.md)中冻结。
