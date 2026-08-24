# XA-1D-CLASSIC-EWMAC 经典复现契约

> 状态：`explore contract / diagnostic-only / not promoted / not live-ready`。冻结日期：2026-08-10（UTC+8），跑数前冻结。
> 研究问题：用传统四大资产类别代理，固定经典 EWMAC 参数、零逐资产调参，能否复现趋势跟踪文献中的核心性质：跨资产正收益、低相关、危机分散与成本敏感性。

## 1. 文献口径

- 趋势文献基准：Hurst, Ooi, Pedersen, *A Century of Evidence on Trend-Following Investing*，使用股票指数、债券、商品、外汇四大类、67 个市场的趋势策略。
- 信号口径：本契约使用 Carver 式 EWMAC 连续 forecast，而不是该论文的月频 `1/3/12m` time-series momentum sign signal；二者同属线性趋势滤波族，但不可把数值指标逐项等同。
- 数据限制：仓库当前没有 Bloomberg/Datastream/GFD/连续期货 roll 数据。本轮使用 Yahoo Finance ETF/FX 调整后 OHLC 代理，只能验证性质，不是严格论文复刻。

## 2. 冻结信号

- 日线 EWMAC 速度对：`8/32`、`16/64`、`32/128`、`64/256`。
- 单对 raw forecast：`(EMA_fast - EMA_slow) / σ_price`，其中 `σ_price` 为日价格变化 EWMA 标准差，半衰期 `20` 日。
- forecast scalar：`8/32=5.3`、`16/64=3.75`、`32/128=2.65`、`64/256=1.87`。
- 单对 forecast 与合成 forecast 均截断于 `±20`；可用速度对少于 `2` 时该资产空仓。
- 合成 forecast 为可用速度对等权平均；全部计算只使用 T-1 收盘及更早数据。

## 3. 冻结仓位与组合

- 单资产子系统目标：`w_i = (F_i / 10) * (20% / σ_i)`，`σ_i` 为日收益 EWMA 标准差半衰期 `20` 年化。
- 组合 raw 权重：当日活跃资产数为 `N_t`，每个资产先除以 `N_t` 等风险分摊。
- 组合层波动目标：用 raw 组合日收益 EWMA 标准差半衰期 `20` 估计组合波动，缩放到 `10%` 年化目标。
- 总名义杠杆上限：`Σ|w_i| <= 3.0`，越界按比例压缩。
- 缓冲带：仅当目标与持仓差异超过该资产满 forecast 组合权重的 `10%` 时调仓。
- 非交易日处理：ETF/FX 代理在日历联合账本上非交易日收益为 `0`，forecast 与波动最多前填 `5` 个自然日；超限则资产失活并强制平仓。

## 4. 冻结资产代理

| 类别 | 代理 |
| --- | --- |
| 股票指数 | `SPY`, `IWM`, `QQQ`, `EFA`, `EEM`, `EWJ`, `EWU`, `EWG`, `EWC`, `EWA` |
| 债券 | `SHY`, `IEF`, `TLT`, `TIP` |
| 商品 | `GLD`, `SLV`, `USO`, `UNG`, `DBC`, `DBA`, `CORN`, `WEAT`, `SOYB` |
| 外汇 | `UUP`, `FXE`, `FXY`, `FXB`, `FXA`, `FXC`, `FXF` |

选择纪律：本轮不因跑数失败或个别标的拖累而删除资产；若 Yahoo 当前不可取得某个代理，脚本 fail closed，不用替代 ticker 偷换。

## 5. 数据与成本

- 数据源：Yahoo Finance chart API 原始 JSON 留档，OHLC 用 `adjclose / close` 因子调整。
- 质量检查：symbol 匹配、空 OHLC/adjclose 丢弃数、重复交易日、OHLC 合法性、行数、最大 session gap、raw SHA256。
- 主窗口：从至少 `12` 个资产同时可用且信号有效的首日开始。
- 三本台账：
  - `gross_zero_cost`：0 成本，用于对比文献毛收益性质。
  - `futures_like_2bps_side`：每边 `2 bps`，近似低成本期货/高流动性执行。
  - `etf_stress_10bps_side`：每边 `10 bps`，承接前序 ETF 执行面压力口径。
- 不包含融资、借券、税费、管理费/绩效费、真实期货 roll yield。

## 6. 报告义务

- 输出主窗口三本台账：总收益、CAGR、实现波动、Sharpe、MDD、年单边换手、成本拖累、平均/峰值杠杆。
- 输出近期 `1d/7d/1m/3m/6m/1y` 分片，仅审计不选参。
- 输出 2007-2009、2020 疫情急跌、2022 通胀冲击三个压力窗口，对比 `SPY` 与 `60/40 SPY/IEF`。
- 输出与 `SPY`、`IEF`、`60/40 SPY/IEF` 的相关性，以及 `80% 60/40 + 20% 策略` 的组合诊断。
- 输出按资产类别的逐年贡献，检查收益是否只来自单一类别。

## 7. 判定纪律

本轮没有 promotion 门禁，不登记版本，不声明 live-ready。若 gross/低成本台账能复现正收益、低相关与危机分散，可登记为“经典性质在公开代理上部分复现”；若只有 0 成本成立而成本后失败，结论应指向执行面或数据代理限制。无论结果如何，禁止在同一历史上删资产、改成本、改速度对、改波动目标或改缓冲带后声称同一契约通过。
