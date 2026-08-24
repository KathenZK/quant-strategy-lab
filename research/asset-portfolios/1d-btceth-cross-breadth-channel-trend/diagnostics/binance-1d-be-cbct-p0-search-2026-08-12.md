# BIN-1D-BE-CBCT P0 冻结搜索裁决

## 结论

冻结的 `2,808/2,808` 个 development 配置全部完成，`0` 个同时达到成本后 `>=20x` 与 ordered `1h` MDD `<=20%`。P0 判定为 `HARD-GATE-FAILED / explore / not promoted / not live-ready`；researcher-exposed audit 与 prospective 均未读取，不登记版本。

| Frontier | 共享参数 | 净终值 | Ordered MDD | 平仓数 |
| --- | --- | ---: | ---: | ---: |
| Growth | `entry20 / exit10 / EMA50 / trail5ATR / confirm2 / cooldown7 / maxhold120` | `13.2404x` | `-48.00%` | 24 |
| Risk | `entry40 / exit5 / EMA100 / trail2ATR / confirm3 / cooldown0 / maxhold off` | `1.6607x` | `-27.88%` | 13 |

最低回撤臂仍比硬门差 `7.88pp`，且收益仅 `1.66x`；最高收益臂距离 `20x` 尚有 `6.76x`，回撤超标 `28.00pp`。这不是排名或精度问题，而是收益与风险前沿没有交集。

## 归因

Growth frontier 的多空与资产拆分如下：

- long-only `9.2650x/-35.22%`，short-only `1.3436x/-40.78%`；
- BTC-only `4.7097x/-37.55%`，ETH-only `5.1025x/-48.46%`；
- 最大单笔正 log-growth 占比 `41.21%`，超过冻结的 `30%` 集中度门；
- 完整年正收益比例 `80%`、rolling 365d 正收益比例 `78.99%`，时间覆盖并非主要失败项。

成本拆分进一步表明，growth frontier 从纯价格毛值 `22.1427x`，经实际 funding 降至 `14.1579x`，再经手续费与 `4bps/fill` 滑点降至 `13.2404x`。交易摩擦确有显著影响，但即便完全移除成本，ordered MDD 仍约 `48%`，因此不能靠成本优化解决双目标。

Risk frontier 的 13 笔全部由 chandelier stop 退出；更紧的风险层把 MDD 压至 `-27.88%`，同时把纯价格毛值压至 `1.9238x`。继续搜索同一 `entry/exit/EMA/trail/confirm/cooldown/maxhold` 参数面不具备机制依据。

## 裁决与下一步

- P0：`HARD-GATE-FAILED / explore / not promoted / not live-ready`；
- 不打开 audit/prospective，不用杠杆、vol target 或降低门槛救援；
- P0 参数面停止扩张；只允许先冻结、再检验 HYPE 演进中方法级的“浮盈后保护”单机制臂。若该机制不能跨越收益/风险 soft-continue 门，则关闭 CBCT family 并另立新机制。

## 证据

- [冻结合同](../specs/binance-1d-be-cbct-p0-contract-2026-08-12.md)
- [搜索摘要](../artifacts/binance_1d_be_cbct_p0_search_2026-08-12.json) — SHA256 `d0055e16c66f80eac84827325eb12edccb920bd26d54b7567d617517b17fea4d`
- [全网格](../artifacts/binance_1d_be_cbct_p0_search_2026-08-12_grid.csv) — SHA256 `cf4ab8eccc1c4a360a29e4fce608f731db02ac9377093698ad9083df0eedc357`
- [Frontier 归因](../artifacts/binance_1d_be_cbct_p0_frontiers_2026-08-12.json) — SHA256 `bec433dac4400a52a4db8a90eaf2afc56d57f7bd71aefc915a10eedacd5d192f`
- [Growth 完整交易路径](../artifacts/binance_1d_be_cbct_p0_growth_frontier_trade_path_2026-08-12.html) — 24 笔 entry/exit 均连线
- [Risk 完整交易路径](../artifacts/binance_1d_be_cbct_p0_risk_frontier_trade_path_2026-08-12.html) — 13 笔 entry/exit 均连线
- [搜索脚本](../scripts/search_binance_1d_be_cbct_p0.py) · [归因脚本](../scripts/diagnose_binance_1d_be_cbct_p0_frontiers.py) · [HTML 脚本](../scripts/render_binance_1d_be_cbct_p0_trade_paths.py)
