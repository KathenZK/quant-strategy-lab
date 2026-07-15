# HYPE-15M-MII V1.4A 近期不开单诊断

日期：2026-07-14

## 结论

当前 dry-run 的 `HYPE-15M-MII-V1.4A` 最近不开仓，主因不是 runner 漏单，而是 **`ATR96% >= 0.75%` 波动率过滤把几乎所有 RSI 反转信号挡掉**。

- 最近 `7d`：RSI raw cross `99` 次，过 ATR `0` 次，最终信号 `0` 次。
- 最近 `30d`：raw `425`，过 ATR `168`，最终 `10`。
- 最近 `90d`：raw `1274`，过 ATR `565`，最终 `45`；ATR96% 中位 `0.668%`，最新 `0.560%`。
- 最后一笔 V1.4A 研究开仓：`2026-06-29T22:30:00+00:00`。

`min_rvol96=0.85`（相对 V1.3 的 `1.0`）不能解决当前干旱，因为卡点在 ATR，不在 RVOL。V1.4 与 V1.4A 入场漏斗相同；TP/SL 只影响已开仓后的出场，不会制造新入场信号。

## 数据口径

- Exchange / market / symbol / timeframe：Binance USD-M `HYPE/USDT:USDT` `15m`
- Source：标准数据湖 raw/normalized
- Range：见 artifact JSON `data_quality`
- Cost：fee `0.001`/fill + slippage `4 bps`/fill；本漏斗不计入 funding
- Entry timing：K+1 open
- Active dry-run：`HYPE-15M-MII-V1.4A`（`min_rvol96=0.85`，`TP=1.4*ATR96`，`SL=3.0*ATR96`）

## 决定

保持 `V1.4A` dry-run 规则不变。不要为了“最近几天开单”直接下调 `min_atr_pct96`；此前网格已证明放宽 ATR 会显著伤害收益和回撤。若要在低波动 regime 交易，应另开新版本搜索，而不是改当前 dry-run。

## 证据

- 脚本：[`research_hype_15m_mii_v1_4a_recent_signal_drought.py`](../scripts/research_hype_15m_mii_v1_4a_recent_signal_drought.py)
- 产物：[`hype_15m_mii_v1_4a_recent_signal_drought_2026-07-14.json`](../artifacts/hype_15m_mii_v1_4a_recent_signal_drought_2026-07-14.json)
