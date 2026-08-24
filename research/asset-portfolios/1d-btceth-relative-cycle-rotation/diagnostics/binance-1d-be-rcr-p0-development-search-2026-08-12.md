# BIN-1D-BE-RCR P0 Development 搜索结论（2026-08-12）

## 裁决

- P0：`HARD-GATE-FAILED / explore / not promoted / not live-ready`
- 登记版本：无
- researcher-exposed audit：未读取
- prospective：未读取，起点保持锁定

## 完整搜索

冻结合同共执行 `7,560/7,560` 个配置，成本口径为 `0.001/fill + 4bps/fill + actual funding`，组合只有一个固定数量 `1x` BTC/ETH long/short 仓位。

| 前沿 | development equity | daily-close MDD | ordered 1h MDD | 结论 |
|---|---:|---:|---:|---|
| growth frontier | `21.2605x` | `-48.6763%` | `-69.6600%` | 收益过线，风险严重失败 |
| risk frontier | `8.6109x` | `-24.5154%` | `-30.7607%` | 全网格最低日线回撤，仍未过 `20%` |

- `equity>=20x && daily MDD<=20%`：`0`；
- daily MDD `<=20%`：`0`；
- daily MDD `<=25%`：仅 `1` 个配置，其 equity 为 `8.6109x`；
- 因日线初筛已经为零，合同规定的候选 ordered gate、stress、delay 与唯一候选排序没有启动。

## 固定前沿参数与因果线索

- growth frontier：`regime_h=40, relative_h=40, vol_h=28, deadzone=0, switch_margin=0.25, confirm_days=3`；`74` 笔，BTC/ETH 持仓小时分别 `17,880/15,288`，long/short `40/34`。
- risk frontier：`regime_h=90, relative_h=60, vol_h=56, deadzone=1.0, switch_margin=0.25, confirm_days=2`；`43` 笔，BTC/ETH 持仓小时分别 `8,328/4,776`，long/short `30/13`。
- 两条前沿完整自然年正收益比例均为 `100%`，滚动 365 日正收益比例分别 `87.10%/95.21%`；失败不是长期方向完全无效，而是单次反转与连续误判造成的路径尾部。
- growth frontier 最大单笔正 log-growth 占比 `8.65%`，risk frontier 为 `20.69%`；不存在单笔盈利独占全部收益的假象。
- growth frontier 最差交易是 `2024-05-13` 至 `2024-05-24` 的 ETH short，单笔 log-growth `-34.62%`；其他显著亏损同时覆盖 ETH long 与 short。risk frontier 最差交易仍为 ETH short squeeze（`-15.12%`）。

因此，共同周期方向与相对选币能够创造 growth，但不具备独立的尾部退出/再武装机制。下一实验只能预注册保护状态并与两条冻结前沿做 exact control；不得用 leverage/vol-target 缩放把 `24.5%–69.7%` 的原始风险伪装为达标。

## 复现

```bash
.venv/bin/python research/asset-portfolios/1d-btceth-relative-cycle-rotation/scripts/search_binance_1d_be_rcr_p0.py --run-date 2026-08-12
.venv/bin/python research/asset-portfolios/1d-btceth-relative-cycle-rotation/scripts/diagnose_binance_1d_be_rcr_p0_frontiers.py --run-date 2026-08-12
```

机器产物见 `artifacts/binance_1d_be_rcr_p0_search_2026-08-12*` 与 `artifacts/binance_1d_be_rcr_p0_frontiers_2026-08-12*`。

完整逐笔交互路径：[growth frontier](../artifacts/binance_1d_be_rcr_p0_growth_frontier_trade_path_2026-08-12.html)；[risk frontier](../artifacts/binance_1d_be_rcr_p0_risk_frontier_trade_path_2026-08-12.html)。每笔 entry/exit 均在对应 BTC 或 ETH 面板连线。
