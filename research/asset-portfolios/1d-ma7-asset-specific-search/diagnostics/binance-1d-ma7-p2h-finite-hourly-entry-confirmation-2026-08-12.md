# Binance 1D MA7 P2-H Finite Hourly Entry Confirmation 裁决

## 结论

P2-H 对 P2-G 的 `17,821` 笔 actual entries 检验三个预注册的 closed-1h / next-hour-open 确认结构。三个 arm 均未同时满足尾部拒绝、非尾部保留、winner保留和 calendar gate；selected arm 为 `None`。

| Arm | Weakest tail rejected | Weakest nontail retained | Weakest winner retained | Worst median delay | Weakest calendar | Final |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `H1_POSITIVE_CLOSE` | `27.50%` | `85.96%` | `90.05%` | `1h` | `0%` | FAIL |
| `H2_POSITIVE_CLOSE` | `42.50%` | `77.48%` | `83.74%` | `3h` | `25%` | FAIL |
| `PDX_PRIOR_DAY_EXTREME` | `72.50%` | `44.92%` | `54.05%` | `8h` | `0%` | FAIL |

因此关闭当前 `24h` finite hourly confirmation 线，不实现完整 PnL 状态机、不登记 V2、不读取 audit/prospective。

## 冻结范围

- 合同：[P2-H finite hourly confirmation 合同](../specs/binance-1d-ma7-p2h-finite-hourly-entry-confirmation-contract-2026-08-12.md)
- Parent：[P2-G entry-information 裁决](binance-1d-ma7-p2g-entry-information-attribution-2026-08-12.md)
- Daily signal、original entry/exit、`EARLY_TAIL<=-8%`：全部不变
- Pending expiry：original entry 后 `24h`
- 确认：只读完整 `1h` close，candidate fill 固定下一真实 `1h` open
- 同小时 adverse/confirm：adverse first
- 展开 evidence：`53,463` arm×trade rows、`69,861` pair×stratum rows、`5,160` unique-entry×stratum rows

## 双口径 asset overall

### H1 — 一根盈利侧 close

| Weighting / asset | Tail reject | Nontail retain | Winner retain | Median delay |
| --- | ---: | ---: | ---: | ---: |
| Pair BTC | `48.09%` | `87.16%` | `92.65%` | `1h` |
| Pair ETH | `38.29%` | `86.86%` | `90.64%` | `1h` |
| Unique BTC | `27.50%` | `85.96%` | `91.89%` | `1h` |
| Unique ETH | `35.44%` | `87.23%` | `90.05%` | `1h` |

它几乎不损失机会，但大多数 early tail 在第一根正向 close 前已发生，无法承担风险修复角色。

### H2 — 连续两根盈利侧 close

| Weighting / asset | Tail reject | Nontail retain | Winner retain | Median delay |
| --- | ---: | ---: | ---: | ---: |
| Pair BTC | `56.77%` | `80.20%` | `89.76%` | `3h` |
| Pair ETH | `49.63%` | `79.58%` | `87.87%` | `3h` |
| Unique BTC | `42.50%` | `77.48%` | `86.49%` | `3h` |
| Unique ETH | `53.16%` | `77.68%` | `83.74%` | `3h` |

H2 是三者中最接近风险/机会平衡的结构，但两资产双口径最弱 tail rejection只有 `42.50%`，未达到冻结的 `60%`；calendar最弱也仅 `25%`。不得因为它“相对最好”而进入 PnL。

### PDX — 突破前日极值

| Weighting / asset | Tail reject | Nontail retain | Winner retain | Median delay |
| --- | ---: | ---: | ---: | ---: |
| Pair BTC | `87.33%` | `53.49%` | `58.26%` | `6h` |
| Pair ETH | `89.51%` | `52.75%` | `65.37%` | `8h` |
| Unique BTC | `72.50%` | `44.92%` | `54.05%` | `8h` |
| Unique ETH | `79.75%` | `49.29%` | `61.89%` | `8h` |

PDX 能拒绝尾部，但代价是删除超过一半非尾部交易和约 `38%–46%` winners。候选到 original exit 的路径诊断不能修复被删除趋势与账户机会成本，因此不授权完整回测。

## 因果裁决

三个结构形成单调 frontier：确认越严格，尾部拒绝越高，但非尾部与 winner retention快速下降。这个结果说明 early-tail 与有效趋势在最初数小时的简单方向确认上高度重叠；没有一个固定 pending 规则能稳定分离二者。

按 HYPE 演进方法，应保留 exact control、尊重失败门并转向新的入场形态信息，而不是：

- 把 H1 与 PDX按事后 outcome混合；
- 把 `24h` expiry 改成结果最有利时长；
- 增加 ATR buffer 搜索来填平两端；
- 只在 BTC/ETH 的有利年份启用。

## 下一步

- P2-H：`HARD-GATE-FAILED / explore / not promoted / not live-ready`
- 关闭：当前单纯 hourly directional confirmation 家族
- 下一轮：预注册 entry 前完整日线的形态/路径质量归因，例如 aligned body、close-location、directional efficiency；这些信息与旧 MA7 threshold 不同，但仍可 closed-bar/next-open执行
- 若形态信息仍无跨资产稳定性，则应停止继续扩充同一 MA7 entry substrate，转向独立新机制家族而非宣称 V2

## 机器证据

- [主 JSON](../artifacts/binance_1d_ma7_p2h_hourly_entry_confirmation_2026-08-12.json) — SHA256 `3a486e94223c5a1bfe40b506646d93f48b4f3613ccd8b75a6186ff5812966590`
- [逐笔 arm events](../artifacts/binance_1d_ma7_p2h_hourly_entry_confirmation_2026-08-12_events.csv) — SHA256 `ee2f0f58bbeb7200742f3b7569e3f0d286cde079a2ee7a39a23c2193ef519c27`
- [汇总 metrics](../artifacts/binance_1d_ma7_p2h_hourly_entry_confirmation_2026-08-12_metrics.csv) — SHA256 `ed0c053ca2ef913329cac5ad0262c122a2c11ff55cca7cb6c389817b5eb93273`
- [复现脚本](../scripts/audit_binance_1d_ma7_p2h_hourly_entry_confirmation.py)
