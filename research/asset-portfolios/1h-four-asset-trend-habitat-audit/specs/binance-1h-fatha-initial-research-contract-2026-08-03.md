# BIN-1H-FATHA 初始研究合同（2026-08-03）

## 1. 研究问题

本轮回答四个问题：

1. HYPE 是否只是振幅大，还是在 `3d/7d/14d` 上同时具有更高的路径效率、较少反复和更好的延迟可捕获性？
2. BTC/ETH/SOL 增加的是独立趋势事件，还是把同一负期望规则分散得更平滑？
3. 事后确实存在强趋势时，延迟 `4h/12h/24h` 进入还剩多少空间，`2R` 后半 MFE 保护是否会过早触发？
4. anchor 当时已知的过去 `7d/28d` 同向状态，能否在成本后识别未来 Long/Short 趋势？

本轮是 habitat diagnostic，不是策略、selector 或组合回测，不产生订单、不登记版本、不 promotion。

## 2. 数据与窗口

- 固定 universe：Binance USD-M `HYPEUSDT/BTCUSDT/ETHUSDT/SOLUSDT` perpetual。
- 输入：标准数据湖闭合 `15m` OHLCV 与 funding；每币必须通过 UTC、连续性、重复、关键空值、OHLCV 合法性、raw/normalized parity 与 funding 来源审计。
- 执行路径：只保留由四根连续 `15m` 聚合出的完整 `1h` bar；hourly close 在 bar 结束时才可见。
- Anchor：每日 `00:00 UTC`；anchor price 是该时刻已经闭合的最后一根 `1h close`。
- Horizon：未来 `72/168/336h`（`3d/7d/14d`）；past volatility 使用之前完整 `720h` 的 hourly log-return RMS。
- 横向主证据：四币共同可用窗口，起点还需满足 `720h` lookback，终点需完整保留 `336h` future path。
- 背景证据：各币全历史用相同规则；不得根据全历史结果改变共同窗口阈值。

## 3. 事后趋势 habitat

每个 anchor/horizon 先用最终 log return 的符号定义事后 Long/Short，只衡量该路径是否存在，不声称实时可知。

- `amplitude=abs(final log return)`。
- `hourly_efficiency=amplitude/sum(abs(hourly log changes))`。
- `daily_efficiency=amplitude/sum(abs(24h sampled log changes))`；横向主比较使用 daily efficiency，hourly efficiency作为微观噪声审计。
- `scaled_amplitude=amplitude/(past_hourly_rms*sqrt(horizon))`。
- `MFE/MAE`：按事后方向计算路径内最大有利/不利 log move，再除以 `R=past_hourly_rms*sqrt(24)`。
- `first_passage`：以 `±1R` 为边界，记录先到有利还是不利；两边均未到为 none。
- `required_giveback_share`：路径中从运行 MFE 到后续 progress 的最大回吐，占最终最大 MFE 的比例。
- `half_mfe_triggered_after_2R`：运行 MFE 达 `2R` 后，progress 是否曾跌破运行 MFE 的 `50%`。
- 延迟 `4/12/24h`：记录延迟后到 horizon 终点的同方向剩余 log return、占完整最终 move 的比例，以及扣 `28bps` round-trip hurdle 后是否仍为正。

冻结“强趋势”定义：`scaled_amplitude>=1.5` 且 `daily_efficiency>=0.35`。另报告 `daily_efficiency>=0.25/0.40/0.60` 阶梯，不根据结果更换主阈值。

## 4. 事前 admission

- `past_7d_return` 与 `past_28d_return` 同为正时给 Long admission，同为负时给 Short admission，否则 flat。
- 对 admission 后未来 `3d/7d/14d` 分方向报告：方向延续率、signed final return、scaled return、MFE/MAE、`+1R/-1R` first passage、base cost 后 1x hypothetical return。
- Base cost：一次 entry/exit 共 `2×(10bps fee+4bps adverse slippage)=28bps`；funding 按实际 horizon 内 rate 累加，Long 支付正 funding、Short 相反。
- 与同资产同方向的 unconditional anchors 对比；不因某资产结果更好而新增过滤器。

## 5. 趋势状态寿命

在日频 anchor 上以 `7d/28d` 对齐方向形成 Long/Short/Flat state，统计：

- 非 Flat 时间占比；
- Long/Short episode 数；
- episode 持续天数中位数、P75、P90 与最大值；
- 每年/每季度状态覆盖，防止单一阶段制造“趋势明显”的视觉印象。

## 6. 不确定性与判断

- 日频 anchor 可以重叠；关键共同窗口差异使用 `14d` calendar block bootstrap `5,000` 次，而不是把每日行当独立样本。
- HYPE 分别减 BTC/ETH/SOL：比较强趋势率、daily efficiency、`24h` 延迟剩余空间、半 MFE 触发率和 admission cost-after return；95% CI 跨零即不宣称 HYPE 更优。
- Long/Short、`3d/7d/14d` 分开，不用合并平均掩盖方向差异。

结果分类预先固定：

1. HYPE habitat 强但 admission 弱：主要是事前识别问题。
2. HYPE 振幅强但效率/延迟/回吐弱：高波动不等于可交易趋势。
3. 多资产 habitat 均存在且 admission 有跨资产同向证据：才值得另立 Trend Campaign Engine。
4. 多资产 admission 均无成本后优势：增加资产不能修复机制，停止策略化。

## 7. 产物

- 每 anchor/horizon 路径明细 parquet；
- 共同窗口/全历史 habitat 与 admission CSV；
- episode、季度稳定性、共同窗口排名与 HYPE 配对 bootstrap CSV/JSON；
- 中文结论报告、主账和决策记录。

## 8. 揭示后诊断扩展：行情走出来后是否延续

该扩展在第 1 轮 habitat/admission 聚合结果已经可见、但下列统计尚未运行时冻结；因此只能作为机制诊断，不能反写为预注册证据或 promotion 依据。

- 在每个 anchor 后等待固定 `4h/12h/24h`，仅用这段已经发生的 close-to-close 位移符号决定 Long/Short，不使用传统技术指标，也不使用 horizon 终点方向。
- `early_scaled_move=abs(early move)/(past_hourly_rms*sqrt(delay))`，同时记录 early path efficiency；二者只由价格幅度、速度和来回程度构成。
- 从 delay 时刻开始，衡量到原 `3d/7d/14d` horizon 的同向剩余 return、延续率、MFE/MAE、`±1R` first passage，以及 `28bps + 实际 funding` 后净值。
- 每个资产/期限/等待时间固定报告全部样本，以及按 `early_scaled_move` 横截面三等分的 low/mid/high；三等分是描述性分组，不选择最优阈值。
- 若 high 组没有稳定优于 low 组，或成本后仍为负，则“位移越大/速度越快，未来越延续”的物理类比在该尺度不成立。
