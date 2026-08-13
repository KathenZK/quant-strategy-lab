# BIN-1D-MA7-TFML 产物索引

## P0 Source

- [Source manifest](p0_data_2026-08-10/p0_source_manifest.json)
- [Source data quality](p0_data_2026-08-10/p0_data_quality.json)
- [P0 manifest](p0_data_2026-08-10/manifest.json)
- [P0 manifest SHA256](p0_data_2026-08-10/manifest.sha256)

## P0/P1 Expected-Utility Development

- [Accepted event panel](p1_development_2026-08-10/p0_accepted_events.parquet)
- [P0 capacity](p1_development_2026-08-10/p0_capacity.json)
- [Price + flow OOF](p1_development_2026-08-10/p1_price_plus_flow_oof.parquet)
- [Price utility control OOF](p1_development_2026-08-10/p1_price_utility_control_oof.parquet)
- [Flow-only OOF](p1_development_2026-08-10/p1_flow_only_oof.parquet)
- [P1 summary](p1_development_2026-08-10/p1_summary.json)
- [P1 full report](p1_development_2026-08-10/p1_report.json)
- [P1 manifest](p1_development_2026-08-10/manifest.json)
- [P1 manifest SHA256](p1_development_2026-08-10/manifest.sha256)

P0 有效；P1 文件保留为 aggregate-isolation 违规后的历史失效输出，无 frozen model、P2 或 HYPE artifact。

## P0E Fresh-Universe Source / Events

- [Fresh flow source manifest](p0e_data_2026-08-10/p0_source_manifest.json)
- [Fresh flow data quality](p0e_data_2026-08-10/p0_data_quality.json)
- [Fresh flow manifest](p0e_data_2026-08-10/manifest.json)
- [Fresh price/funding quality](p0e_price_data_2026-08-10/p0_data_quality_manifest.json)
- [13-asset event panel](p0e_events_2026-08-10/p0e_events.parquet)
- [P0E event capacity](p0e_events_2026-08-10/p0e_event_capacity.json)
- [P0E event manifest](p0e_events_2026-08-10/manifest.json)

## P1E Fresh-Universe Development

- [Accepted panel](p1e_development_2026-08-10/p0e_accepted_events.parquet)
- [P0E capacity](p1e_development_2026-08-10/p0e_capacity.json)
- [Price + flow fresh OOF](p1e_development_2026-08-10/p1e_price_plus_flow_oof.parquet)
- [Price control fresh OOF](p1e_development_2026-08-10/p1e_price_utility_control_oof.parquet)
- [Flow-only fresh OOF](p1e_development_2026-08-10/p1e_flow_only_oof.parquet)
- [P1E summary](p1e_development_2026-08-10/p1e_summary.json)
- [P1E full report](p1e_development_2026-08-10/p1e_report.json)
- [P1E manifest](p1e_development_2026-08-10/manifest.json)

P0E flow source/caches 可审计，但 price/funding generator source 未保留并被原生 manifest 标记 blocker；P1E 文件另因 aggregate-isolation 违规保留为历史失效输出，无 frozen model、P2 或 HYPE artifact。
