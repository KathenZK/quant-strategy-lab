# HYPE-1D-MA7-ABT V7.1 MA20替换 Binance USDT本位Top20诊断

## 结论

裁决：`TRANSFER_MIXED_POSITIVE / diagnostic-only / not promoted / not live-ready`。

按用户要求，本轮在上一轮USDT-only口径上取最近30个已闭合UTC日K `quote_volume` Top20，只把 V7.1 中用于 reclaim、slope、hysteresis 与 PEHC 复核的 `SMA7` 替换为 `SMA20`；`ATR7`、`RSI6`、OAPP、PEHC、冷却、成本和funding处理保持不变。该变体改变了策略身份，不登记为 V7.1，也不构成promotion或runner授权。

MA20替换后，Top20中`11/20`正收益，中位收益`+1.25%`，最佳为`AKEUSDT` `+61.47%/-44.63%`，最差仍为`BANKUSDT` `-47.03%/-68.98%`。同一Top20上，MA7原逻辑只有`6/20`正收益、中位`-20.17%`；MA20显著改善横截面中心，但把`HYPEUSDT`从MA7的`+257.97%`降为`-2.65%`，说明这是机制替换线索，不是 V7.1 的无痛参数优化。

## 数据与方法

- 数据源：Binance futures public API。
- 市场：`quoteAsset=USDT`，`contractType in {PERPETUAL, TRADIFI_PERPETUAL}`，`status=TRADING`；候选池共`683`个，其中`perp_usdt=527`、`tradifi_perp=156`。
- Top20选择：每个候选合约最近30个已闭合UTC日K `quote_volume` 求和排序；所有`USDC`本位合约已过滤。
- 回测数据：每个Top20标的最多拉取最近`520`个已闭合日K、对应`1h` K线与 fundingRate。
- 成本：fee `0.001` per fill；base slippage `4 bps` adverse per fill；stress slippage `8 bps`；funding 使用 Binance fundingRate timestamp，mark 近似为相邻小时close。
- 规则：V7.1外部复现逻辑，仅将均线长度从`7`改为`20`；不搜索参数，不重估其它阈值。

## 最近30日成交额Top20

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

## 回测结果

按 base `4 bps` slippage 的净收益排序：

| Symbol | Type | Net | 1h MDD | Trades | Win | PF | Sharpe | Exposure | Funding | 8bps Net |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `AKEUSDT` | `perp_usdt` | `+61.47%` | `-44.63%` | 8 | `37.5%` | `2.39` | `0.98` | `16.0%` | `+0.33%` | `+60.36%` |
| `MUUSDT` | `tradifi_perp` | `+29.47%` | `-18.65%` | 4 | `75.0%` | `9.19` | `1.56` | `27.1%` | `-0.54%` | `+29.06%` |
| `SNDKUSDT` | `tradifi_perp` | `+10.55%` | `-34.18%` | 6 | `50.0%` | `1.36` | `0.74` | `32.7%` | `+0.61%` | `+10.02%` |
| `CLUSDT` | `tradifi_perp` | `+9.91%` | `-9.22%` | 2 | `100.0%` | `NA` | `1.35` | `20.9%` | `-0.57%` | `+9.74%` |
| `ZECUSDT` | `perp_usdt` | `+9.12%` | `-55.11%` | 20 | `40.0%` | `1.05` | `0.39` | `24.1%` | `+6.35%` | `+7.36%` |
| `SKHYNIXUSDT` | `tradifi_perp` | `+8.36%` | `-3.87%` | 1 | `100.0%` | `NA` | `2.22` | `8.5%` | `+0.62%` | `+8.29%` |
| `XAGUSDT` | `tradifi_perp` | `+8.17%` | `-10.53%` | 6 | `50.0%` | `1.49` | `0.76` | `14.5%` | `+0.55%` | `+7.68%` |
| `XAUUSDT` | `tradifi_perp` | `+4.75%` | `-7.58%` | 8 | `50.0%` | `2.26` | `0.54` | `17.9%` | `-0.29%` | `+4.09%` |
| `SKHYUSDT` | `tradifi_perp` | `+3.88%` | `-4.55%` | 1 | `100.0%` | `NA` | `1.90` | `18.5%` | `-0.01%` | `+3.81%` |
| `SPCXUSDT` | `tradifi_perp` | `+1.70%` | `-13.58%` | 2 | `50.0%` | `2.15` | `0.40` | `15.7%` | `+0.82%` | `+1.54%` |
| `BZUSDT` | `tradifi_perp` | `+0.81%` | `-8.13%` | 4 | `25.0%` | `1.20` | `0.21` | `21.0%` | `-0.34%` | `+0.50%` |
| `SOXLUSDT` | `tradifi_perp` | `-1.76%` | `-43.43%` | 4 | `50.0%` | `0.95` | `0.43` | `37.5%` | `+0.21%` | `-2.07%` |
| `ETHUSDT` | `perp_usdt` | `-2.33%` | `-37.38%` | 17 | `35.3%` | `0.99` | `0.04` | `15.0%` | `-0.36%` | `-3.66%` |
| `HYPEUSDT` | `perp_usdt` | `-2.65%` | `-36.38%` | 18 | `44.4%` | `1.00` | `0.18` | `25.6%` | `-0.46%` | `-4.05%` |
| `KORUUSDT` | `tradifi_perp` | `-4.27%` | `-11.66%` | 1 | `0.0%` | `0.00` | `-1.05` | `9.9%` | `+0.10%` | `-4.35%` |
| `SNXXUSDT` | `tradifi_perp` | `-4.85%` | `-16.75%` | 1 | `0.0%` | `0.00` | `-1.06` | `18.0%` | `+0.13%` | `-4.93%` |
| `BTCUSDT` | `perp_usdt` | `-14.98%` | `-20.56%` | 17 | `23.5%` | `0.60` | `-0.56` | `17.6%` | `+0.28%` | `-16.14%` |
| `XRPUSDT` | `perp_usdt` | `-20.72%` | `-31.22%` | 20 | `35.0%` | `0.67` | `-0.46` | `21.7%` | `-0.29%` | `-21.97%` |
| `SOLUSDT` | `perp_usdt` | `-25.76%` | `-34.75%` | 19 | `42.1%` | `0.49` | `-0.59` | `13.3%` | `-1.18%` | `-26.91%` |
| `BANKUSDT` | `perp_usdt` | `-47.03%` | `-68.98%` | 19 | `21.1%` | `0.59` | `-0.57` | `22.1%` | `-2.91%` | `-47.88%` |

## 与MA7同Top20对比

| Variant | Positive | Median Net | Best | Worst |
| --- | ---: | ---: | --- | --- |
| `MA7` | `6/20` | `-20.17%` | `HYPEUSDT +257.97%` | `BANKUSDT -89.46%` |
| `MA20` | `11/20` | `+1.25%` | `AKEUSDT +61.47%` | `BANKUSDT -47.03%` |

## 读数

- MA20显著降低MA7在TradFi高成交合约上的亏损，`SNDKUSDT`、`SKHYNIXUSDT`、`MUUSDT`由MA7负收益转为MA20正收益。
- MA20也降低部分主流币亏损幅度，如`BTCUSDT`、`ETHUSDT`、`SOLUSDT`、`BANKUSDT`相对MA7都有改善，但除`ZECUSDT`外仍多为负。
- 最大风险是身份破坏：`HYPEUSDT`从MA7 Top20同窗的`+257.97%`变为MA20的`-2.65%`，说明MA20不是 V7.1 的保守增强，而是换了核心节奏。
- 正收益里多笔数很少：`SKHYNIXUSDT`、`SKHYUSDT`各1笔，`CLUSDT`、`SPCXUSDT`各2笔，不能当作稳定跨资产边。

## 裁决

MA20替换值得作为新的机制线索继续研究，但不能写回 V7.1，也不能支持 promotion。若继续推进，应另立 MA20-root 或 multi-MA family，预注册样本、时间切分、是否允许阈值重估，以及对 HYPE 本体失效的处理原则。

## 证据

- [机器证据](../artifacts/hype_1d_ma7_abt_v7_1_ma20_top20_binance_usdt_u_margin_transfer_2026-08-12.json)
- [MA7 USDT Top30对照证据](../artifacts/hype_1d_ma7_abt_v7_1_top30_binance_usdt_u_margin_transfer_2026-08-12.json)
- [审计脚本](../scripts/audit_hype_1d_ma7_abt_v7_1_top15_binance_perp_transfer.py)
