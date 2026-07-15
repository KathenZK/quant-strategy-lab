# Decision Log

## 2026-07-14 — 建立独立六币多腿研究家族

决定将六币三交易臂、币内多腿融合和抢占/非抢占单仓状态机作为新家族研究，不覆盖既有 `BIN-1H-AR-MAE-V1`；最近三个月锁定 OOS，先完成 OHLCV 与 funding 数据湖补齐和质量审计。

## 2026-07-14 — 数据质量门禁通过并锁定 OOS

六币共同窗口经 Binance API 全量补齐，funding 经官方月度归档加 API 补尾后写入 raw/normalized 数据湖；质量 blocker 为 `0`。锁定 OOS 为 `[2026-04-14 09:00 UTC, 2026-07-14 09:00 UTC)`，证据见 [数据质量报告](diagnostics/binance-six-asset-1h-data-quality-2026-07-14.md)。

## 2026-07-14 — 四条冻结路线首次锁定 OOS 全部失败

在 OOS 未读状态下完成 `72,000` 组单臂预拟合搜索并冻结四条账户路线，冻结产物 SHA-256 为 `cc02c1228b8232338bd0280263b7079635a6ad0815aab1c80af4c6f2b32e6c6d`。首次揭示后，独立臂/币内融合与抢占/不抢占四条路线的 OOS 胜率仅 `53.19%–54.55%`，收益均为负，回撤均超过 `33%`，全部违反硬门槛。

后验 `5,200` 组账户路由表面和 `126` 组局部成分扰动仅用于解释失败，禁止用于重新选择。当前保持 `explore / not promoted / not live-ready`，不登记版本、不生成 live spec、不交接 runner。详见 [锁定 OOS 失败诊断](diagnostics/binance-1h-ml6as-prefit-oos-failure-2026-07-14.md)。
