# BIN-1H-MHCSML 数据质量与补洞报告（2026-07-18）

## 结论

- 数据门禁：`PASS`，研究范围为 `2020-01-01 00:00 <= ts < 2026-07-01 00:00 UTC`。
- 研究数据来自 Binance Vision monthly/daily 官方归档与 Binance FAPI；补洞数据同时保存 raw 证据、normalized 分区、请求窗口和 SHA256。
- 最终 OHLCV `14,114,255` 行 / `790` symbols，mark price `14,308,668` 行 / `788` symbols，funding `2,428,690` 行 / `792` symbols。
- 关键字段空键、重复键、身份错误、缺 source、缺月份、非法/非正 OHLC、负成交字段、未闭合 bar 和 funding 冲突均为 `0`。
- 本次只读取数据质量统计，没有读取 `2026-07-19` 起 prospective OOS 的标签、IC、逐腿或组合绩效。

## 为什么旧 PASS 不够

旧审计只确认每个 symbol-month 的月归档文件存在，但月 ZIP 内部仍可能缺小时。重新做逐 symbol 连续性检查后发现：

| 数据集 | 初始内部缺小时 | Binance Vision daily 补回 | FAPI 再补回 | 最终未生成 bar |
| --- | ---: | ---: | ---: | ---: |
| OHLCV 1h | `7,883` | `7,632` | `0` | `251` |
| Mark price 1h | `36,048` | `17,688` | `18,288` | `72` |

OHLCV 剩余 12 个区间、mark 剩余 7 个区间。对应 FAPI 在明确的 start/end 窗口内也返回空数组；7 个 mark 区间全部落在无成交 bar 的区间内。这些是停牌、合约迁移或交易所未生成 bar 的 nontradable intervals，不是可以用前值填充的缺失价格。

完整区间保存在本地 artifact `artifacts/nontradable_intervals_2020_2026q2.csv`。因子/标签构建必须排除 entry-to-exit 与任一区间相交的样本；不得 forward-fill open、close、mark 或交易量。

## Funding 重复修复

复审发现 HYPE 逐日 API 层与 canonical 月归档修复层有 `1,040` 个研究窗内重复键，费率最大差为 `0`。逐文件对拍后：

- 412 个完全冗余逐日文件按原 SHA256 移入 `data/raw/_quarantine/`；
- 一个混合文件将原文件隔离后，只把 canonical 层没有的 2 条记录写回；
- 另一个只含 3 条独有记录的文件保持不变；
- 最终 funding 重复键和冲突均为 `0`。

隔离是非破坏性的，原文件、原 SHA、目标路径和重写文件 SHA 均记录在 `artifacts/redundant_hype_funding_quarantine_manifest.json`。

## 数据使用边界

1. 旧 `BIN-1H-CSLGBM` 因子面板在本次补洞前生成，不能直接作为新家族的冻结数据集；新面板必须从修复后的数据湖重建。
2. `2026Q2` 已经揭示，可进入 reused holdout 诊断，但不能成为独立最终 OOS。
3. `2026-07-01 <= ts < 2026-07-19 UTC` 只允许做无标签数据准备；不得根据收益、标签、IC 或分组表现选型。
4. `2026-07-19 <= ts < 2026-10-19 UTC` prospective OOS 在窗口结束前只允许键、schema、闭合 bar 和缺口检查。

## 证据

- 数据门禁生成器：[finalize_data_quality_manifest.py](../scripts/finalize_data_quality_manifest.py)
- Daily 补洞：[repair_binance_vision_daily_gaps.py](../scripts/repair_binance_vision_daily_gaps.py)
- FAPI 补洞：[repair_binance_fapi_gaps.py](../scripts/repair_binance_fapi_gaps.py)
- Funding 隔离：[quarantine_redundant_hype_funding.py](../scripts/quarantine_redundant_hype_funding.py)
- 本地总 manifest：`artifacts/data_quality_manifest_2026-07-18.json`

数据门禁通过只授权构建因子与历史 OOF，不代表模型、组合或 promotion 通过。
