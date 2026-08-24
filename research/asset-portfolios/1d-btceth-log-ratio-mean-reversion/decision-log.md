# BIN-1D-BE-LRMR Decision Log

## 2026-08-12 — P0 家族与合同冻结

- RCR P0–P6 在不揭示 audit/prospective 的前提下关闭；price/funding risk overlays 均未达到 `20x/20%`。
- 去重确认仓库无 BTC/ETH log-ratio/pairs/cointegration 家族。
- 新建双腿相对价值 family；以初始 `0.5x + 0.5x` 固定数量替代单腿方向暴露。
- 冻结数据、区间、双腿成本、funding、搜索空间与 conservative ordered MDD；结果产生前不改合同。

## 2026-08-12 — P0 HARD-GATE-FAILED；research line closed

- `15,288/15,288` 完成；daily hard-target `0`。
- growth `1.5471x/-44.88% ordered MDD`；risk `1.0325x/-19.66%`。
- 双腿 fast/detailed/hourly terminal ledger parity PASS；失败不是会计 blocker。
- 收益差距为数量级，不做参数/杠杆救援；audit/prospective 未揭示，无版本。
