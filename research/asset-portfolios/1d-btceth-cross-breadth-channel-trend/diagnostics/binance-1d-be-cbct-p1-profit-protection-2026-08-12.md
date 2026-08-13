# BIN-1D-BE-CBCT P1 浮盈保护裁决

## 结论

P1 按冻结合同完成 exact control + `18/18` 个 profit-protection 配置，形成 `18` 条独立交易路径。结果为 `0` hard-target pass、`0` soft-base pass、`0` soft-continue pass：P1 `HARD-GATE-FAILED`，CBCT research line 关闭；audit/prospective 未读取，无版本、无 handoff。

P1 不是完全无效。最佳收益臂把 P0 control 的 `13.2404x/-48.00%` 改善为 `21.2707x/-37.20%`，首次在本 family 的 `1x` 成本后台账中超过 `20x`。但它仍比 MDD 硬门差 `17.20pp`，最大单笔正 log-growth 占比 `38.64%` 也超过冻结的 `35%` 门，因此不能成为候选。

## Frontier

| Frontier | `activation/giveback/confirm` | 净终值 | Ordered MDD | 交易数 | 最大单笔正 log 占比 |
| --- | --- | ---: | ---: | ---: | ---: |
| Growth | `1ATR / 35% / 2d` | `21.2707x` | `-37.20%` | 30 | `38.64%` |
| Risk | `1ATR / 20% / 1d` | `4.4107x` | `-34.20%` | 39 | `12.80%` |

Growth 臂相对 control 的 log-growth retention 为 `118.35%`、MDD改善 `10.81pp`，说明 profit protection 同时提高收益并降低回撤；但 MDD 的绝对缺口仍大。Risk 臂把 MDD再改善 `13.80pp`，代价是终值降至 `4.41x`，显示更紧回吐会过早截断趋势。

由于没有配置先通过 base soft gate，合同规定不运行 `8bps` 与 `+1d` 补充压力；这些空值不是漏跑，而是预注册的 sequential gate。

## 剩余回撤结构

Growth frontier 的小时收盘路径最大 peak-to-trough 为约 `-35.86%`，从 `2022-06-18 20:00 UTC` 延续到 `2022-11-10 20:00 UTC`；ordered `1h` high/low 口径进一步扩大到 `-37.20%`。期间不是单一 stop 失效，而是多笔状态串联：

- ETH short 的盈利退出后，`2022-08-14` 建立 ETH long并以 `-21.27%` log-growth 结束；
- 随后的 BTC shorts 贡献有限，其中 `2022-11-10` 入场的一笔最终 `-8.77%` log-growth；
- profit protection 能减少单笔趋势回吐，却不能判断跨交易的慢周期方向，也没有组合级 campaign reset。

这说明下一机制需要在 entry 前明确慢周期 regime/campaign 状态，而不是在 CBCT 内继续调 giveback、chandelier 或 cooldown。

## 治理裁决

- CBCT：`research line closed / HARD-GATE-FAILED / explore / not promoted / not live-ready`；
- P1 winner 只是 development observation，不登记、不打开 audit/prospective；
- 按合同禁止加入 handoff/re-entry/RSI 或继续搜索 profit-protection 邻域；
- 可迁移的方法证据仅是：`MFE 1ATR + 35% giveback + 2d confirm` 在本 development 上有增量，后继 family 必须另立身份、慢周期状态机与 prospective 合同，不能把该结果称为 clean OOS。

## 证据

- [P1 冻结合同](../specs/binance-1d-be-cbct-p1-profit-protection-contract-2026-08-12.md)
- [P1 机器摘要](../artifacts/binance_1d_be_cbct_p1_profit_protection_2026-08-12.json) — SHA256 `622ded82b9d0e5101a8ca9aeb68dbd16a480655ff91b818b0bcf804e76fe0263`
- [19 路 metrics](../artifacts/binance_1d_be_cbct_p1_profit_protection_2026-08-12_metrics.csv) — SHA256 `38896db5a93c8c45a497672d7b41298047c28315312c3133c70880ba295ab545`
- [Growth 完整交易路径](../artifacts/binance_1d_be_cbct_p1_growth_frontier_trade_path_2026-08-12.html) — 30 笔 entry/exit 均连线
- [Risk 完整交易路径](../artifacts/binance_1d_be_cbct_p1_risk_frontier_trade_path_2026-08-12.html) — 39 笔 entry/exit 均连线
- [P1 脚本](../scripts/search_binance_1d_be_cbct_p1_profit_protection.py) · [共享因果引擎](../scripts/search_binance_1d_be_cbct_p0.py) · [测试](../../../../tests/test_binance_1d_be_cbct_p0.py)
