# BIN-1D-BE-COST P0 Crisis Override 裁决

## 结论

Exact neutral control 在 `1e-12` 内复现 CBCT P1 growth 的 `21.270651982678306x/-37.19612846945293%`。冻结 `12/12` 个 crisis configs 全部完成，`0` hard-base pass，P0 `HARD-GATE-FAILED`并关闭 research line；audit/prospective 未读取。

Growth/risk frontier 再次为同一路径：`EMA200/slope60/confirm3`：

- base `23.1321x/-35.22%`；
- stress `22.6556x/-35.22%`，log-growth retention `99.34%`；
- delay `7.2746x/-37.00%`，retention `63.17%`；
- 24笔 shadow trades、3个 crisis episodes / 6 legs；
- 最大单笔正 log-growth占 `39.25%`。

它提高收益并修复原 2022 最大回撤，但 MDD仍超标 `15.22pp`，delay与集中度也失败。

## 因果归因

最佳配置的 `override_base_exits=0`。三个 crisis episodes 都在账户 shadow 已flat时入场；crisis state通过阻止随后 fresh shadow entries及增加short basket收益改善2022路径，却没有在持仓中强制切换。

修复2022后，新的最大ordered drawdown出现在一笔最终大幅盈利的BTC long：

- entry `2020-10-21 00:00 UTC`，exit `2021-02-18 00:00 UTC`；
- 最终 trade log-growth `+1.369754`；
- equity favorable peak `2021-01-08 15:00`，adverse trough `2021-01-22 01:00`；
- 单笔持仓中 ordered pullback `-35.22%`。

这不是慢周期危机entry识别问题。EMA100更快配置虽然产生1–2次实际override，却把终值降至`6.37x–11.61x`、MDD恶化到`-46.69%`至`-59.86%`；不支持继续缩短EMA或改confirm救参。

## 治理裁决

- `research line closed / HARD-GATE-FAILED / explore / not promoted / not live-ready`；
- 禁止增加return/vol阈值、stop/TP或更快EMA邻域；
- audit/prospective未读取，无版本、无handoff；
- 可继承的方法证据：危机short basket有独立收益增量，但当前硬风险来自盈利runner的持仓内回吐。后继必须另立partial-profit runner family，不静默改写COST/CBCT。

## 证据

- [冻结合同](../specs/binance-1d-be-cost-p0-contract-2026-08-12.md)
- [机器摘要](../artifacts/binance_1d_be_cost_p0_2026-08-12.json) — SHA256 `603bd71392362996c310e9a0584d3530aebd58a7ebbc94aacf476a9b004798dd`
- [12路grid](../artifacts/binance_1d_be_cost_p0_2026-08-12_grid.csv) — SHA256 `5300b6494d88d4477fc7d6637c2cb962e63bb3a9682d110fe9a554ae3de50225`
- [完整交易路径](../artifacts/binance_1d_be_cost_p0_growth_frontier_trade_path_2026-08-12.html) — 24笔shadow与6条crisis legs均连线
- [研究脚本](../scripts/research_binance_1d_be_cost_p0.py) · [HTML脚本](../scripts/render_binance_1d_be_cost_p0_trade_paths.py) · [测试](../../../../tests/test_binance_1d_be_cost_p0.py)
