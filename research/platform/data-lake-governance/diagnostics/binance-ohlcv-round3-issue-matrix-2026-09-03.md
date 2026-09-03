# Binance OHLCV Round 3 问题矩阵（修复前）

日期：2026-09-03  
性质：独立复现，不把第二轮 READY 当前提。修复前结果见 [binance_ohlcv_r3_pre_fix_repro_2026-09-03.json](../artifacts/binance_ohlcv_r3_pre_fix_repro_2026-09-03.json)。

| ID | 问题 | 修复前复现 | 状态 |
| --- | --- | --- | --- |
| R3-01 | cutoff 只写 manifest，不约束聚合；改 cutoff 仍 `already_published`；请求 2026-09-03 静默截到 2026-08-24 仍 PASS | 截止 `2026-07-01T01:00:00Z` 仍产出 `end=02:00`（收盘 03:00）；窗口越界 `silent_truncate=true` | 待修复 |
| R3-02 | 改错 exchange/market_type/timeframe/input/cutoff 后 manifest 仍 PASS | `kraken`/`spot`/`1d` 的假清单被 `assert_published_derived_manifest` 接受 | 待修复 |
| R3-03 | 非物化 SQL 审计对坏 schema/身份 CAST 后 PASS | 见回归测试：异交易所、spot、字符串 `is_closed`、无时区 ts、`trade_count=inf` | 待修复 |
| R3-04 | 内容已改但 size+mtime 缓存可复用旧指纹 | 快路径按 `(relpath,size,mtime)` 缓存；同大小同 mtime 改价可走旧审计 | 待修复 |
| R3-05 | 删除 lineage 字段仍可能通过；新版本默认注册表不认识 | `assert_cache_sidecar_fresh` 在缺少 `input_manifest_sha256` 时通过 | 待修复 |
| R3-06 | 4h 内部缺口 5,577 根只 report_only，研究默认可跨缺口计算 | 第二轮 SQL 审计 `gap_policy=report_only` | 待修复 |
| R3-07 | 旧 1h 成交额差异未追溯到原始文件 | 第二轮机器 blocker 仍在，文字却写成语义不同 | 待修复 |
| R3-08 | 平台治理状态被策略 glossary 测试误伤；消费者检查只覆盖硬编码名单 | 文档一致性 16 pass / 1 fail（研究平台状态列） | 待修复 |
