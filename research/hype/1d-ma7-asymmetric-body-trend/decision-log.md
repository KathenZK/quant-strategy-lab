# Decision Log

## 2026-08-04

决定：将用户提出的固定 `SMA7` 非对称多空规则建立为独立 `HYPE-1D-MA7-Asymmetric-Body-Trend` 研究线；由于“MA7 不穿过实体”存在方向歧义，保留字面版、方向性实体反转版和对称收盘反转版分别审计。三种解释在成本后全期均大幅亏损且相位/参数不稳，因此保持 `explore / not promoted / not live-ready`，不登记版本、不继续在已揭示历史上调参。证据：[初始合同](specs/hype-1d-ma7-abt-initial-contract-2026-08-04.md) · [初始报告](diagnostics/hype-1d-ma7-abt-initial-validation-2026-08-04.md) · [机器摘要](artifacts/hype_1d_ma7_abt_summary_2026-08-04.json)。

## 2026-08-04 — 多空分离趋势候选

决定：按用户要求保留固定 `SMA7`，搜索多空独立的 reclaim、斜率、迟滞退出和 ATR 保护，记录一个全期成本后 `+293.20%` 的 post-reveal 历史候选；因最终选择使用了已揭示最后 `90d`、仅 13 笔且相位门槛失败，继续保持 `explore / not promoted / not live-ready`，不登记版本。证据：[候选观察规格](specs/hype-1d-ma7-abt-separated-trend-observation-2026-08-04.md) · [搜索报告](diagnostics/hype-1d-ma7-abt-separated-trend-search-2026-08-04.md) · [机器摘要](artifacts/hype_1d_ma7_separated_summary_2026-08-04.json)。

## 2026-08-05 — BTC/ETH 零调参迁移

决定：第 `041` 组原参数迁移到 BTC/ETH 后，组合在共同 `425d` 均亏损；UTC short-only 虽同向盈利，但 `12h` 相位同时翻负且样本低，不改变 HYPE 候选的 `explore / not promoted / not live-ready` 状态，也不在目标资产历史上继续调参。证据：[跨资产迁移诊断](../../asset-portfolios/1d-ma7-separated-trend-transfer/diagnostics/binance-1d-ma7-separated-trend-transfer-2026-08-05.md)。

## 2026-08-05 — 登记 V1

决定：按用户要求将第 `041` 组多空分离参数登记为 `HYPE-1D-MA7-Asymmetric-Body-Trend-V1`；登记只冻结身份，已知 post-reveal、低样本、相位失败、跨资产组合迁移失败和长仓首日无 hard stop 等缺口全部保留，状态为 `registered / not promoted / not live-ready`。证据：[V1 规格](specs/hype-1d-ma7-abt-v1-spec.md) · [家族主账](hype-1d-ma7-abt-core-ledger.md)。

## 2026-08-05 — SOX 全历史迁移

决定：V1 原参数在 Yahoo `^SOX` 的 `1994-2026` 全历史零成本回测为 `-36.29%`、MDD `-76.58%`，长期绝对与超额收益均失败；该证据不改变 V1 的登记身份，但进一步阻止 promotion，状态保持 `registered / not promoted / not live-ready`。证据：[SOX 全历史诊断](../../sox/1d-ma7-separated-trend-transfer/diagnostics/sox-1d-ma7-v1-transfer-2026-08-05.md)。

## 2026-08-05 — EMA7 替换

决定：只把 V1 的 SMA7 换成 `EMA(span=7)` 后，全期组合为 `+35.93%`、MDD `-46.15%`，但 long-only / short-only 均亏损且 `12h` 相位转为 `-19.34%`；EMA7 不登记、不替换 V1，不继续在已揭示历史上搜索 EMA span。证据：[EMA7 诊断](diagnostics/hype-1d-v1-ema7-substitution-2026-08-05.md)。

## 2026-08-05 — 迁移到 HYPE 4H

决定：日线 V1 状态机迁移到独立 HYPE 4H 家族后，bar-transfer / clock-equivalent combined 分别为 `-67.72% / -2.61%`，后者 long-only 虽为 `+17.07%`，但 short-only、成本、延迟、相位和超额收益均失败；不改变日线 V1 身份，不登记 4H 版本。证据：[4H 迁移诊断](../4h-ma7-asymmetric-body-trend/diagnostics/hype-4h-ma7-source-v1-transfer-2026-08-05.md)。

## 2026-08-05 — 3x 杠杆

决定：每次入场目标 `3x`、持仓期间数量固定时，已揭示历史 combined 为 `+2,907.12%`、MDD `-56.40%`，但 `12h` 相位仅 `+6.98%`、MDD `-91.11%`，实际杠杆最高漂至约 `4.28x`，且未建模精确 maintenance margin 和 liquidation fee；V1 继续固定 `1x`，3x 不登记、不推进 runner。证据：[3x 杠杆诊断](diagnostics/hype-1d-v1-3x-leverage-2026-08-05.md)。

## 2026-08-05 — MU 双市场迁移

决定：V1 原参数在 Binance `MUUSDT` 上 combined 为 `-12.30%`，在 Nasdaq `MU` 上虽为 `+51.51%`，但只触发多头、远逊于 buy-and-hold，且股票数据为 `raw_unaccepted`；该结果不改变 HYPE V1 身份，只增加跨市场无超额与空头不可迁移证据。证据：[MU 双市场诊断](../../mu/1d-ma7-separated-trend-transfer/diagnostics/mu-1d-ma7-dual-market-transfer-2026-08-05.md)。

## 2026-08-05 — BTC 周 K 迁移

决定：V1 状态机换成 Binance BTC 周 K 后，两种时间合同 combined 均为 `-21.72%`、MDD `-29.61%`，long-only / short-only 与半周偏移相位也全部亏损；该结果不改变 HYPE V1 登记身份，只增加 timeframe transfer 失败证据，BTC 周线不登记版本。证据：[BTC 周 K 迁移诊断](../../btc/1w-ma7-asymmetric-body-trend/diagnostics/btc-1w-ma7-v1-transfer-2026-08-05.md)。

## 2026-08-05 — BTC/ETH 共享参数回测 HYPE

决定：BTC/ETH development 选出的共享 MA7 参数原样用于 HYPE 后 combined `-65.15%`、MDD `-73.47%`，long-only / short-only 和两个日界均亏损；共享参数不替换 HYPE V1，也不根据 HYPE 已揭示结果重新调参。证据：[共享参数 HYPE control 诊断](../../asset-portfolios/1d-ma7-asset-specific-search/diagnostics/binance-ma7-shared-params-on-hype-2026-08-05.md)。
