# HYPE-1D-MA7-ABT V7.1 Binance USDT本位Top30迁移诊断

## 结论

裁决：`TRANSFER_FAIL / diagnostic-only / not promoted / not live-ready`。

按用户要求，本轮过滤掉所有`USDC`本位合约，只保留 Binance U本位 futures 中 `quoteAsset=USDT`、`status=TRADING`、`contractType in {PERPETUAL, TRADIFI_PERPETUAL}` 的合约；候选池共`683`个，其中普通`perp_usdt`为`527`个、`tradifi_perp`为`156`个。按最近30个已闭合UTC日K `quote_volume` 取前30并用 V7.1 固定参数逐标的回测。

30个标的全部通过脚本内日K/1h K基础质量检查；`SNXXUSDT`无交易，实际有交易标的`29/30`。正收益`9/30`，中位收益`-20.81%`，最佳仍为`HYPEUSDT` `+257.97%/-28.85%`，最差为`BANKUSDT` `-89.46%/-92.85%`。结果仍不支持把 V7.1 迁移为通用多标的策略。

本诊断不搜索参数、不创建新版本、不推进runner、不构成小额实盘授权。

## 数据与方法

- 数据源：Binance futures public API。
- 市场：`quoteAsset=USDT`，`contractType in {PERPETUAL, TRADIFI_PERPETUAL}`，`status=TRADING`。
- Top30选择：每个候选合约最近30个已闭合UTC日K `quote_volume` 求和排序；所有`USDC`本位合约已过滤。
- 回测数据：每个Top30标的最多拉取最近`520`个已闭合日K、对应`1h` K线与 fundingRate；上市不足520日的标的按可用全窗回测并在机器证据中标记短历史。
- 成本：fee `0.001` per fill；base slippage `4 bps` adverse per fill；stress slippage `8 bps`；funding 使用 Binance fundingRate timestamp，mark 近似为相邻小时close。
- 规则：使用 V7.1 固定 `SMA7/ATR7/RSI6`、多空 reclaim、OAPP、PEHC、冷却和风险保护参数；本脚本按外部复现规格实现，不复用历史HYPE动态改写engine。

## 最近30日成交额Top30

| Rank | Symbol | Type | 30d quote volume |
| ---: | --- | --- | ---: |
| 1 | `BTCUSDT` | `perp_usdt` | `231,691,564,424` |
| 2 | `ETHUSDT` | `perp_usdt` | `187,524,521,252` |
| 3 | `SNDKUSDT` | `tradifi_perp` | `88,320,570,892` |
| 4 | `SKHYNIXUSDT` | `tradifi_perp` | `55,013,974,426` |
| 5 | `SOXLUSDT` | `tradifi_perp` | `48,805,092,387` |
| 6 | `MUUSDT` | `tradifi_perp` | `36,976,662,781` |
| 7 | `XAUUSDT` | `tradifi_perp` | `36,359,531,688` |
| 8 | `SOLUSDT` | `perp_usdt` | `31,410,839,987` |
| 9 | `KORUUSDT` | `tradifi_perp` | `27,763,239,998` |
| 10 | `SPCXUSDT` | `tradifi_perp` | `27,048,330,121` |
| 11 | `SKHYUSDT` | `tradifi_perp` | `23,883,217,236` |
| 12 | `CLUSDT` | `tradifi_perp` | `22,803,939,196` |
| 13 | `XAGUSDT` | `tradifi_perp` | `18,893,924,451` |
| 14 | `BANKUSDT` | `perp_usdt` | `16,657,833,074` |
| 15 | `ZECUSDT` | `perp_usdt` | `12,970,967,868` |
| 16 | `XRPUSDT` | `perp_usdt` | `12,377,785,860` |
| 17 | `HYPEUSDT` | `perp_usdt` | `12,339,463,152` |
| 18 | `BZUSDT` | `tradifi_perp` | `9,578,866,246` |
| 19 | `AKEUSDT` | `perp_usdt` | `9,052,561,174` |
| 20 | `SNXXUSDT` | `tradifi_perp` | `8,331,055,454` |
| 21 | `DRAMUSDT` | `tradifi_perp` | `7,580,344,443` |
| 22 | `DOGEUSDT` | `perp_usdt` | `7,310,119,791` |
| 23 | `DEXEUSDT` | `perp_usdt` | `6,401,084,015` |
| 24 | `EWYUSDT` | `tradifi_perp` | `6,307,239,949` |
| 25 | `BNBUSDT` | `perp_usdt` | `5,995,395,643` |
| 26 | `SAMSUNGUSDT` | `tradifi_perp` | `4,865,494,097` |
| 27 | `TUTUSDT` | `perp_usdt` | `4,620,814,491` |
| 28 | `QQQUSDT` | `tradifi_perp` | `4,510,280,597` |
| 29 | `ADAUSDT` | `perp_usdt` | `4,310,099,675` |
| 30 | `1000PEPEUSDT` | `perp_usdt` | `3,999,000,575` |

## 回测结果

按 base `4 bps` slippage 的净收益排序：

| Symbol | Type | Net | 1h MDD | Trades | Win | PF | Sharpe | Exposure | Funding | 8bps Net |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `HYPEUSDT` | `perp_usdt` | `+257.97%` | `-28.85%` | 25 | `60.0%` | `3.11` | `2.08` | `41.2%` | `+1.22%` | `+251.13%` |
| `TUTUSDT` | `perp_usdt` | `+189.13%` | `-70.46%` | 36 | `36.1%` | `2.83` | `0.99` | `34.8%` | `-3.00%` | `+180.74%` |
| `1000PEPEUSDT` | `perp_usdt` | `+119.61%` | `-40.77%` | 34 | `50.0%` | `1.78` | `1.20` | `45.5%` | `-3.84%` | `+113.74%` |
| `ADAUSDT` | `perp_usdt` | `+41.47%` | `-35.77%` | 31 | `51.6%` | `1.45` | `0.74` | `36.1%` | `-1.45%` | `+37.99%` |
| `XAGUSDT` | `tradifi_perp` | `+35.59%` | `-18.35%` | 12 | `66.7%` | `3.52` | `1.22` | `41.9%` | `+1.76%` | `+34.32%` |
| `XRPUSDT` | `perp_usdt` | `+17.59%` | `-36.18%` | 38 | `47.4%` | `1.25` | `0.48` | `41.9%` | `-0.75%` | `+14.07%` |
| `AKEUSDT` | `perp_usdt` | `+14.29%` | `-70.17%` | 16 | `43.8%` | `1.21` | `0.74` | `26.3%` | `-3.74%` | `+12.81%` |
| `BZUSDT` | `tradifi_perp` | `+1.30%` | `-10.79%` | 3 | `33.3%` | `1.02` | `0.27` | `13.6%` | `+1.48%` | `+1.06%` |
| `SPCXUSDT` | `tradifi_perp` | `+0.77%` | `-33.23%` | 7 | `57.1%` | `1.03` | `0.36` | `35.7%` | `+0.40%` | `+0.22%` |
| `SNXXUSDT` | `tradifi_perp` | `+0.00%` | `+0.00%` | 0 | `NA` | `NA` | `NA` | `0.0%` | `+0.00%` | `+0.00%` |
| `QQQUSDT` | `tradifi_perp` | `-4.34%` | `-11.62%` | 6 | `33.3%` | `0.64` | `-0.89` | `26.2%` | `-0.60%` | `-4.81%` |
| `CLUSDT` | `tradifi_perp` | `-9.06%` | `-21.97%` | 7 | `28.6%` | `0.42` | `-0.78` | `23.4%` | `+0.31%` | `-9.57%` |
| `SKHYUSDT` | `tradifi_perp` | `-15.89%` | `-25.33%` | 2 | `0.0%` | `0.00` | `-1.82` | `23.6%` | `+0.07%` | `-16.03%` |
| `XAUUSDT` | `tradifi_perp` | `-16.63%` | `-21.21%` | 16 | `31.2%` | `0.40` | `-1.49` | `29.7%` | `+0.77%` | `-17.70%` |
| `DOGEUSDT` | `perp_usdt` | `-17.91%` | `-48.93%` | 36 | `41.7%` | `0.87` | `-0.05` | `33.2%` | `-0.92%` | `-20.30%` |
| `SKHYNIXUSDT` | `tradifi_perp` | `-23.71%` | `-40.08%` | 4 | `25.0%` | `0.36` | `-2.02` | `23.0%` | `-1.42%` | `-23.99%` |
| `EWYUSDT` | `tradifi_perp` | `-26.01%` | `-34.73%` | 7 | `28.6%` | `0.07` | `-2.04` | `15.9%` | `+0.40%` | `-26.44%` |
| `KORUUSDT` | `tradifi_perp` | `-26.94%` | `-35.13%` | 2 | `0.0%` | `0.00` | `-1.55` | `13.9%` | `-0.41%` | `-27.07%` |
| `ETHUSDT` | `perp_usdt` | `-27.49%` | `-63.10%` | 42 | `28.6%` | `0.87` | `-0.34` | `39.7%` | `-1.40%` | `-29.94%` |
| `DRAMUSDT` | `tradifi_perp` | `-27.68%` | `-41.53%` | 5 | `20.0%` | `0.28` | `-2.43` | `22.5%` | `-0.48%` | `-28.01%` |
| `BTCUSDT` | `perp_usdt` | `-30.33%` | `-41.70%` | 40 | `32.5%` | `0.54` | `-0.98` | `36.2%` | `+0.01%` | `-32.55%` |
| `SOLUSDT` | `perp_usdt` | `-37.18%` | `-52.59%` | 33 | `36.4%` | `0.63` | `-0.71` | `30.8%` | `-0.99%` | `-38.85%` |
| `SOXLUSDT` | `tradifi_perp` | `-37.28%` | `-43.97%` | 5 | `40.0%` | `0.18` | `-1.19` | `24.2%` | `+0.96%` | `-37.58%` |
| `SAMSUNGUSDT` | `tradifi_perp` | `-41.06%` | `-41.06%` | 5 | `0.0%` | `0.00` | `-4.88` | `25.6%` | `+1.02%` | `-41.33%` |
| `SNDKUSDT` | `tradifi_perp` | `-44.48%` | `-45.44%` | 6 | `0.0%` | `0.00` | `-3.69` | `15.2%` | `+0.60%` | `-44.78%` |
| `MUUSDT` | `tradifi_perp` | `-44.96%` | `-57.34%` | 10 | `10.0%` | `0.31` | `-2.12` | `26.8%` | `-1.93%` | `-45.43%` |
| `ZECUSDT` | `perp_usdt` | `-45.31%` | `-71.13%` | 33 | `36.4%` | `0.68` | `-0.27` | `28.3%` | `-1.19%` | `-46.82%` |
| `BNBUSDT` | `perp_usdt` | `-45.78%` | `-52.65%` | 38 | `36.8%` | `0.44` | `-1.40` | `41.2%` | `-0.45%` | `-47.43%` |
| `DEXEUSDT` | `perp_usdt` | `-51.11%` | `-70.82%` | 36 | `30.6%` | `0.46` | `-0.40` | `35.5%` | `-1.23%` | `-52.50%` |
| `BANKUSDT` | `perp_usdt` | `-89.46%` | `-92.85%` | 28 | `21.4%` | `0.40` | `-1.42` | `28.0%` | `+1.38%` | `-89.72%` |

## 读数

- Top30里`tradifi_perp`占`17/30`，股票/商品/指数类已经充分进入样本；过滤USDC后，`HYPEUSDT`回到成交额第17名并成为最佳。
- 正收益`9/30`但质量分化明显：`TUTUSDT`和`AKEUSDT`回撤超过`-70%`，`SPCXUSDT`、`BZUSDT`只略正，`SNXXUSDT`无交易。
- 高成交股票类里`SNDKUSDT`、`SKHYNIXUSDT`、`MUUSDT`均明显为负；黄金/白银分化，`XAGUSDT`为正而`XAUUSDT`为负。
- 主流`BTCUSDT`、`ETHUSDT`、`SOLUSDT`、`BNBUSDT`、`DOGEUSDT`仍均为负，说明 V7.1 的主要优势仍更像 HYPE 局部结构，而非USDT本位高成交合约的普遍规律。

## 裁决

本轮USDT-only Top30迁移诊断失败。V7.1继续保持`registered / not promoted / not live-ready`；该结果不能支持 live spec、dry-run、live 或扩大到多标的组合。

## 证据

- [机器证据](../artifacts/hype_1d_ma7_abt_v7_1_top30_binance_usdt_u_margin_transfer_2026-08-12.json)
- [审计脚本](../scripts/audit_hype_1d_ma7_abt_v7_1_top15_binance_perp_transfer.py)
