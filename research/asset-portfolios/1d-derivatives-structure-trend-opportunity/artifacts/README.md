# BIN-1D-DSTO 产物索引

## 原 Full-Field P0：官方源质量失败

- [Source manifest](p0_data_2026-08-10/p0_source_manifest.json)
- [Data quality](p0_data_2026-08-10/p0_data_quality.json)
- [Manifest](p0_data_2026-08-10/manifest.json)
- [Manifest checksum](p0_data_2026-08-10/manifest.sha256)

全部 `6,385` 个 ZIP 通过文件身份校验，但内容存在缺行、错位、重复和大段 ratio null；gapful 拼接只保留在本地 unaccepted cache，不作为 artifact。

## P0R/P1：精确 OI + Funding

- [P0R capacity](p1_oi_funding_development_2026-08-10/p0_data_capacity.json)
- [Accepted anchor panel](p1_oi_funding_development_2026-08-10/p0_p1_anchor_panel.parquet)
- [Full OOF scores](p1_oi_funding_development_2026-08-10/p1_full_oof_scores.parquet)
- [Price-control OOF scores](p1_oi_funding_development_2026-08-10/p1_control_oof_scores.parquet)
- [P1 summary](p1_oi_funding_development_2026-08-10/p1_summary.json)
- [P1 full report](p1_oi_funding_development_2026-08-10/p1_report.json)
- [Manifest](p1_oi_funding_development_2026-08-10/manifest.json)
- [Manifest checksum](p1_oi_funding_development_2026-08-10/manifest.sha256)

P0R 通过；P1 文件保留为 aggregate-isolation 违规后的历史失效输出，不再视为 hard-gate evidence；未生成 frozen model 或 HYPE 产物。
