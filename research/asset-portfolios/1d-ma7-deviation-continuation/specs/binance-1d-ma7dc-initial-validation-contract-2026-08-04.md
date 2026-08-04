# Binance 1D MA7 延续与偏离初始验证合同

## 1. 研究问题

在 HYPEUSDT、BTCUSDT、ETHUSDT 的完整 UTC 日 K 上，固定 `SMA7`，验证以下当时可见状态是否能稳定排序未来 `1d/3d/7d/14d` 的顺趋势终值、MFE、MAE 与 first-passage：

1. MA7 方向是否具有基础延续；
2. MA7 斜率越强，未来是否越容易继续；
3. 价格相对 MA7 的顺趋势偏离是否存在“中等健康、极端衰竭”的非线性形状；
4. 偏离收缩后重新扩张，是否优于持续扩张时追入。

本阶段只验证度量，不生成订单、PnL、版本或 promotion 结论。

## 2. 冻结数据与因果时序

- Market：Binance USD-M perpetual。
- Assets：HYPEUSDT、BTCUSDT、ETHUSDT，三者分开输出。
- Source：标准数据湖 normalized + raw parity；先审计 15m 源，再聚合完整 1h 和完整 UTC 1d。
- 日线索引表示上一完整 UTC 日最早已知的午夜；状态只使用该时刻及以前的闭合日 K。
- 未来路径只用于标签；最后不足 horizon 的行保持 unknown，不以失败填充。
- 历史已经被研究者查看，全部结果只标记为 diagnostic，不是新 OOS。

## 3. 固定状态量

主均线固定为简单移动平均，不比较或搜索其他长度：

```text
MA7_t = mean(Close[t-6:t])
ATR7_t = mean(TrueRange[t-6:t])
direction_t = sign(MA7_t - MA7_{t-1})
slope_strength_t = abs(MA7_t - MA7_{t-1}) / ATR7_t
raw_deviation_t = (Close_t - MA7_t) / ATR7_t
signed_deviation_t = direction_t * raw_deviation_t
deviation_velocity_t = direction_t * (raw_deviation_t - raw_deviation_{t-1})
```

方向必须连续两日一致，才进入结构状态：

- `expansion`：顺趋势偏离为正且继续扩大；
- `pullback`：顺趋势偏离仍为正但正在收缩；
- `restart`：前一日收缩、当日重新扩大，且两日均未反穿 MA7；
- `crossed`：价格已经位于 MA7 的反趋势一侧；
- `unstable_direction`：MA7 方向未连续两日一致。

## 4. 固定未来标签

每个 horizon 分别输出：

- `future_signed_log_return`：按当日 MA7 方向签名的未来终值对数收益；
- `future_net_log_return`：减去 `2 × (0.001 fee + 0.0004 slippage)` 的往返成本门槛，仅用于判断潜在空间是否覆盖默认成本；
- `MFE_R / MAE_R`：未来日内极值相对当日 ATR7；
- `first_passage`：先触达顺势 `+1 ATR7`，还是反向 `-0.5 ATR7`；同一日同时触达按失败处理；
- `continuation`：未来顺趋势终值是否大于零。

## 5. 冻结诊断

- 连续变量：Spearman IC、14 日 calendar-block bootstrap 95% CI、四个连续时间块的 IC 同号数。
- Beta 控制：long 条件均值必须与所有可用日锚的无条件 long 未来收益比较，short 同理；不能把 BTC/ETH 的长期上涨漂移记作 MA7 增量。该控制是在读取初跑结论前的结论审计中补入，只收紧、不放宽任何门禁。
- 偏离形状：每个时点只用此前样本形成 expanding causal quintile；比较五档未来结果，禁止用全样本分位数回填过去。
- 状态比较：`restart`、`expansion`、`pullback`、`crossed` 分别报告样本数、终值、成本后终值、MFE、MAE、first-passage 成功率；偏离 quintile 也按四个连续时间块复核，避免全样本最高档由单一牛市阶段制造。
- 方向分组：`all / long / short` 分开输出。
- 最近切片：以数据终点锚定 `1d/7d/1m/3m/6m/1y`；样本不足只报告，不据此调参。

## 6. 预声明判断门禁

每个资产、每个方向分别检查四项：

1. `directional_continuation`：未来 7d、14d 平均成本后顺趋势终值均为正，且 7d 四个连续块至少三块为正；long/short 分组还必须在两个 horizon 均优于同方向无条件市场漂移；
2. `slope_increment`：斜率强度对未来 7d、14d 的 IC 均为正，且至少一个 horizon 的 block-bootstrap 95% CI 下界大于零；
3. `interior_deviation`：7d、14d 的最佳偏离 quintile 均不在两端，且最佳档成本后终值为正；
4. `restart_increment`：7d、14d restart 均至少 20 个样本、成本后终值为正，并同时高于 expansion 的成本后终值。

四项中：`3–4` 项为 `supported`，`2` 项为 `partial`，`0–1` 项为 `not supported`。这只是度量证据标签，不是策略状态或 promotion 许可。

## 7. 停止边界

- 不搜索 MA5–MA30，不切换 EMA 救结果；
- 不因 HYPE/BTC/ETH 某个资产失败而改变该资产的阈值；
- 不把 overlapping daily anchors 当成独立交易；
- 若本轮未形成稳定关系，停止该固定 SMA7 状态定义，不进入入场、加仓或退出策略设计。
