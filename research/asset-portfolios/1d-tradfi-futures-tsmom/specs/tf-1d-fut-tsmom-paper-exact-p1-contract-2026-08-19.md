# TF-1D-FUT-TSMOM Paper-Exact P1 冻结契约

> 冻结时间：2026-08-19，读取作者/AQR 收益结果和运行本地公式前冻结。状态：
> `explore / diagnostic-only / not promoted / not live-ready`。

## 1. 研究问题与边界

区分两个问题：

1. 论文作者公开的原始及更新 TSMOM 因子历史表现怎样；
2. 把论文公式原样应用于当前可得的24个期货连续代码和30个长期代理，今天表现怎样。

作者因子是论文结果审计，不是独立重建；本地数据又不是论文的58个逐合约期货/远期市场。
任何结果都不得写成“已在相同原始数据上完全复刻论文”。

## 2. 论文原式

- 信号：每个市场月末过去12个月累计 excess return 的符号；正数做多，负数做空。
- 持有：未来1个月；月末信号从下一交易期开始生效。
- 单市场权重：`sign(12M return) × 40% / sigma_t`。
- 波动率：日收益 EWMA，`delta/(1-delta)=60`，即 `delta=60/61`；使用滞后信息，
  年化方差乘数 `261`，同时扣除以同一权重估计的 EWMA 日均收益。
- 组合：当月所有有效市场简单等权 `1/N_t`。
- 不使用资产类别25%权重、组合层二次波动目标、组合 scalar 或 gross leverage cap。
- Always-long control：把信号替换成 `+1`，其余公式完全相同。

## 3. 三个冻结表面

### A. 作者/AQR 因子

- 原论文文件：`https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/Time-Series-Momentum-Original-Paper-Data.xlsx`
- 更新文件：`https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/Time-Series-Momentum-Factors-Monthly.xlsx`
- 原论文裁决窗口：`1985-01` 至 `2009-12`；更新窗口按文件内最后完整月机械截止。
- 使用文件给出的 diversified TSMOM 和四资产类别 monthly excess returns，不重新加成本。
- 输出原论文窗口、论文后窗口和完整更新窗口；论文后窗口只作时间稳定性诊断。

### B. 24个期货连续代码

- 资产池和数据快照沿用 P0 的冻结24市场，零删减。
- 评估窗口固定 `2022-01-03` 至 `2026-07-31`，与 P0 同窗。
- Yahoo 连续代码继续标记 `raw_unaccepted`；只能验证公式在当前表面的表现。
- 成本：`0 bps` 论文毛口径；`2 bps/边` 本地低成本诊断。

### C. 30个长期 ETF/FX 代理

- 资产池和源快照沿用已冻结 proxy validation，零删减。
- 评估窗口固定 `2013-01-02` 至 `2026-07-31`，与原代理观察同窗。
- 成本：`0/2/10 bps/边`；明确标记 `proxy_only_not_futures_evidence`。

## 4. 指标与时序门禁

- 月频作者序列：CAGR、年化算术收益、年化波动、Sharpe、Sortino、MDD、Calmar、
  正收益月份比例、总收益、分年收益。
- 本地日频：同上并增加日胜率、年换手、平均/峰值 gross、市场与类别贡献，以及数据结束点
  锚定的 `1d/7d/1m/3m/6m/1y` 切片。
- 月末当日收益不得使用新信号；新权重只作用于下一有效交易日。
- 作者文件、配置、审计、指标、路径与 SHA256 清单保存到本家族 `artifacts/`。
- 不搜索 lookback、权重、波动目标、市场子集或 leverage cap；结果揭示后不修改本契约。

## 5. 预先裁决口径

- 论文历史是否强：看作者原论文 `1985–2009` diversified factor。
- 时间稳定性：比较作者更新序列的 `2010–latest` 与原论文窗口，不用完整样本掩盖衰减。
- 当代可复现性：看24期货和30代理同式结果；二者必须单独报告，禁止拼接。
- 即使本地结果优秀，数据 provenance blocker 未解决前也不登记版本或晋级。

