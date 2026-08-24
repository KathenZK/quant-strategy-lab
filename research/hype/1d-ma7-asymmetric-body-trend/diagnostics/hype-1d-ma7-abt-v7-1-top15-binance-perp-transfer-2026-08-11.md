# HYPE-1D-MA7-ABT V7.1 Binance U本位Top15迁移诊断

## 结论

裁决：`TRANSFER_FAIL / diagnostic-only / not promoted / not live-ready`。

按 Binance `721` 个 U本位 futures 合约最近30个已闭合UTC日K `quote_volume` 排名，选出成交额最大的15个标的，并用 V7.1 固定参数逐标的回测。该口径包含普通 `USDT` 永续、`USDC` 永续，以及 App “传统金融/Pre-IPO”里的 `TRADIFI_PERPETUAL` 合约，因此覆盖截图中的 `SNDKUSDT`、`SKHYNIXUSDT`、`SPCXUSDT`、`BTCUSDC`、`ETHUSDC` 等标的。

15个标的全部通过脚本内日K/1h K基础质量检查且都有交易，但只有2个正收益，中位收益为`-27.49%`；Top15里大部分 TradFi/USDC 合约为负。该结果不支持把 V7.1 解释为可迁移的通用日线 MA7 策略。

本诊断不搜索参数、不创建新版本、不推进runner、不构成小额实盘授权。

## 数据与方法

- 数据源：Binance futures public API。
- 市场：`status=TRADING`，`contractType in {PERPETUAL, TRADIFI_PERPETUAL}`，`quoteAsset in {USDT, USDC}`；实际候选池为`527`个`perp_usdt`、`38`个`perp_usdc`、`156`个`tradifi_perp`。
- Top15选择：对每个U本位futures合约拉取最近30个已闭合UTC日K，按 `quote_volume` 求和排序；该口径匹配 App “U本位合约/全部”，不是只看 `USDT + PERPETUAL`。
- 回测数据：每个Top15标的最多拉取最近`520`个已闭合日K、对应`1h` K线与 fundingRate；上市不足520日的标的按可用全窗回测并在机器证据中标记短历史。
- 成本：fee `0.001` per fill；base slippage `4 bps` adverse per fill；stress slippage `8 bps`；funding 使用 Binance fundingRate timestamp，mark 近似为相邻小时close。
- 规则：使用 V7.1 固定 `SMA7/ATR7/RSI6`、多空 reclaim、OAPP、PEHC、冷却和风险保护参数；本脚本按外部复现规格实现，不复用历史HYPE动态改写engine。

## 最近30日成交额Top15

| Rank | Symbol | Type | 30d quote volume |
| ---: | --- | --- | ---: |
| 1 | `BTCUSDT` | `perp_usdt` | `231,691,564,424` |
| 2 | `ETHUSDT` | `perp_usdt` | `187,524,521,252` |
| 3 | `SNDKUSDT` | `tradifi_perp` | `88,320,570,892` |
| 4 | `BTCUSDC` | `perp_usdc` | `60,788,974,036` |
| 5 | `SKHYNIXUSDT` | `tradifi_perp` | `55,013,974,426` |
| 6 | `SOXLUSDT` | `tradifi_perp` | `48,805,092,387` |
| 7 | `ETHUSDC` | `perp_usdc` | `43,256,121,239` |
| 8 | `MUUSDT` | `tradifi_perp` | `36,976,662,781` |
| 9 | `XAUUSDT` | `tradifi_perp` | `36,359,531,688` |
| 10 | `SOLUSDT` | `perp_usdt` | `31,410,839,987` |
| 11 | `KORUUSDT` | `tradifi_perp` | `27,763,239,998` |
| 12 | `SPCXUSDT` | `tradifi_perp` | `27,048,330,121` |
| 13 | `SKHYUSDT` | `tradifi_perp` | `23,883,217,236` |
| 14 | `CLUSDT` | `tradifi_perp` | `22,803,939,196` |
| 15 | `XAGUSDT` | `tradifi_perp` | `18,893,924,451` |

## 回测结果

按 base `4 bps` slippage 的净收益排序：

| Symbol | Type | Net | 1h MDD | Trades | Win | PF | Sharpe | Exposure | Funding | 8bps Net |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `XAGUSDT` | `tradifi_perp` | `+35.59%` | `-18.35%` | 12 | `66.7%` | `3.52` | `1.22` | `41.9%` | `+1.76%` | `+34.32%` |
| `SPCXUSDT` | `tradifi_perp` | `+0.77%` | `-33.23%` | 7 | `57.1%` | `1.03` | `0.36` | `35.7%` | `+0.40%` | `+0.22%` |
| `CLUSDT` | `tradifi_perp` | `-9.06%` | `-21.97%` | 7 | `28.6%` | `0.42` | `-0.78` | `23.4%` | `+0.31%` | `-9.57%` |
| `SKHYUSDT` | `tradifi_perp` | `-15.89%` | `-25.33%` | 2 | `0.0%` | `0.00` | `-1.82` | `23.6%` | `+0.07%` | `-16.03%` |
| `XAUUSDT` | `tradifi_perp` | `-16.63%` | `-21.21%` | 16 | `31.2%` | `0.40` | `-1.49` | `29.7%` | `+0.77%` | `-17.70%` |
| `SKHYNIXUSDT` | `tradifi_perp` | `-23.71%` | `-40.08%` | 4 | `25.0%` | `0.36` | `-2.02` | `23.0%` | `-1.42%` | `-23.99%` |
| `KORUUSDT` | `tradifi_perp` | `-26.94%` | `-35.13%` | 2 | `0.0%` | `0.00` | `-1.55` | `13.9%` | `-0.41%` | `-27.07%` |
| `ETHUSDT` | `perp_usdt` | `-27.49%` | `-63.10%` | 42 | `28.6%` | `0.87` | `-0.34` | `39.7%` | `-1.40%` | `-29.94%` |
| `BTCUSDT` | `perp_usdt` | `-30.33%` | `-41.70%` | 40 | `32.5%` | `0.54` | `-0.98` | `36.2%` | `+0.01%` | `-32.55%` |
| `BTCUSDC` | `perp_usdc` | `-35.09%` | `-40.92%` | 42 | `31.0%` | `0.51` | `-1.19` | `35.9%` | `+0.24%` | `-37.26%` |
| `ETHUSDC` | `perp_usdc` | `-35.23%` | `-59.50%` | 43 | `30.2%` | `0.77` | `-0.64` | `36.9%` | `-0.56%` | `-37.45%` |
| `SOLUSDT` | `perp_usdt` | `-37.18%` | `-52.59%` | 33 | `36.4%` | `0.63` | `-0.71` | `30.8%` | `-0.99%` | `-38.85%` |
| `SOXLUSDT` | `tradifi_perp` | `-37.28%` | `-43.97%` | 5 | `40.0%` | `0.18` | `-1.19` | `24.2%` | `+0.96%` | `-37.58%` |
| `SNDKUSDT` | `tradifi_perp` | `-44.48%` | `-45.44%` | 6 | `0.0%` | `0.00` | `-3.69` | `15.2%` | `+0.60%` | `-44.78%` |
| `MUUSDT` | `tradifi_perp` | `-44.96%` | `-57.34%` | 10 | `10.0%` | `0.31` | `-2.12` | `26.8%` | `-1.93%` | `-45.43%` |

## 读数

- 正收益标的：`2/15`；负收益标的：`13/15`。
- 中位净收益：`-27.49%`，说明不是少数尾部亏损拖累，而是横截面中心已经为负。
- 截图中的 TradFi/股票/商品类合约已进入Top15，但除`XAGUSDT`和`SPCXUSDT`外均为负；`SNDKUSDT`、`SKHYNIXUSDT`、`MUUSDT`等股票类高成交合约表现明显失败。
- `BTCUSDC`、`ETHUSDC`进入Top15后均为负，与对应`BTCUSDT`、`ETHUSDT`方向一致，说明之前只看USDT并未漏掉正向主流边。
- `HYPEUSDT`在 App 口径Top15中被更高成交额的 TradFi/USDC 合约挤出，因此本轮不是HYPE局部最优回测，而是完整 U本位Top15迁移诊断。

## 裁决

本轮Top15迁移诊断失败。V7.1继续保持`registered / not promoted / not live-ready`；外部Top15结果不能支持 live spec、dry-run、live 或扩大到多币种组合。若要继续研究，应先把目标从“复用HYPE参数”改为“跨资产重新验证MA7机制是否有共同边”，并预注册资产选择、时间切分和参数是否允许重估。

## 证据

- [机器证据](../artifacts/hype_1d_ma7_abt_v7_1_top15_binance_perp_transfer_2026-08-11.json)
- [审计脚本](../scripts/audit_hype_1d_ma7_abt_v7_1_top15_binance_perp_transfer.py)
