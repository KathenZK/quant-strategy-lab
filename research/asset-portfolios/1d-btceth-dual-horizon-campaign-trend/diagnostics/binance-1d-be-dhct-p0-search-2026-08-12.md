# BIN-1D-BE-DHCT P0 冻结搜索裁决

## 结论

冻结的 `108/108` 个 development 配置全部完成，base-screen pass `0`。收益最高与回撤最低由同一配置、同一交易路径取得：`15.3468x/-35.23% ordered MDD`，仍未达到 `20x/20%`。P0 判定 `HARD-GATE-FAILED`，research line 按合同关闭；audit/prospective 未读取，无版本、无 handoff。

## 唯一 frontier

- `regime_ema=100`
- `slope_days=60`
- `regime_confirm=3`
- `breakout_n=40`
- `cooldown_days=3`
- 固定 `5ATR` chandelier 与 `1ATR/35%/2d` profit protection

该路径共 24 笔：long/short `18/6`，BTC/ETH `12/12`；19 次 profit-protection、4 次 stop、1 次 regime invalidation。最大单笔正 log-growth 占比 `42.47%`，即使收益/回撤硬门放行也会失败集中度门。

小时收盘路径最大 peak-to-trough 约 `-32.76%`，发生于 `2021-01-08 14:00` 至 `2021-01-27 14:00 UTC`；保守 ordered `1h` high/low 口径为 `-35.23%`。慢周期 state 将 CBCT P1 的 2022 跨交易回撤部分删除，但把终值从 `21.27x` 降至 `15.35x`，并没有形成新的收益/风险前沿。

## 机制裁决

1. 共同慢周期 regime 不是完全无信息：最佳配置同时占据 growth/risk frontier，说明 state 确实系统性改变路径。
2. 但它主要通过减少机会降低风险，仍保留约 `35%` 尾部回撤；不是差一个 EMA 或 confirm 阈值。
3. profit protection 仍承担 19/24 次退出，campaign invalidation 仅触发 1 次；慢周期 state 对退出连续性的贡献不足。
4. 按冻结停止规则，不扩 EMA/slope/breakout/cooldown，不修改 giveback，不做 leverage/vol target。

下一研究假设必须离开“单仓择一 BTC/ETH 趋势”结构，测试真正同时持有且可相互对冲的双 sleeve 或其他独立收益源；否则强相关资产的单仓切换难以把 20x 收益与 20% MDD同时实现。

## 证据

- [P0 合同](../specs/binance-1d-be-dhct-p0-contract-2026-08-12.md)
- [机器摘要](../artifacts/binance_1d_be_dhct_p0_search_2026-08-12.json) — SHA256 `574968ebdeb2b528445d0a0331d3c887d2856cedb23a8d4dde8b738a8ebefefe`
- [108 路网格](../artifacts/binance_1d_be_dhct_p0_search_2026-08-12_grid.csv) — SHA256 `8f70d380e765a5275560f2e94942b8503a064efa6b458213296fdd9b6dac87f4`
- [完整交易路径](../artifacts/bin_1d_be_dhct_p0_growth_frontier_trade_path_2026-08-12.html) — 24 笔 entry/exit 均连线；growth/risk path-equal
- [搜索脚本](../scripts/search_binance_1d_be_dhct_p0.py) · [状态测试](../../../../tests/test_binance_1d_be_dhct_p0.py)
