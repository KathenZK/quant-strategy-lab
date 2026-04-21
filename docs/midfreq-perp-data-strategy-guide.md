# 中低频永续合约数据与策略决策说明

这份文档记录 `Signal Lab` 当前阶段的数据接入与策略范围决策，目标是避免平台一开始就做散。

默认前提：

- 只做中低频
- 先做永续合约
- 研究、回测、模拟交易优先
- 第一版优先单交易所落地，建议从 `Binance USDT-M` 开始

## 1. 当前阶段是否只需要 `basis / funding / OI` 和 `liquidations`

可以，但要加一个前提：

不是“只需要这两类数据”，而是“策略层先只围绕这两层做”。

第一版最小可用数据集应该是：

- `OHLCV`
- `volume / dollar volume`
- `funding`
- `open interest`
- `basis / premium index`
- `liquidations`

其中：

- `OHLCV + volume` 是底座
- `basis / funding / OI` 是主线 alpha
- `liquidations` 是事件层和风险层

当前阶段不建议把 `onchain` 放进第一版主链路。

## 2. 每类数据是否收费

### `basis / funding / OI`

通常最适合先走免费原生接口。

现实情况：

- 主流交易所通常提供公开市场数据接口
- 接口本身一般不收费
- 主要成本在于频率限制、历史深度、字段不统一和数据清洗

适合当前阶段的结论：

- 第一版优先直接接交易所免费接口
- 当你需要更长历史、更高稳定性、多交易所统一格式时，再考虑付费供应商

### `liquidations`

这类通常分成两种：

- 实时流：很多时候可以免费拿到
- 完整历史：往往需要自己长期录制，或者直接采购第三方数据

适合当前阶段的结论：

- 第一版先接免费实时 liquidation stream
- 同时持续落本地，慢慢自己形成历史库
- 如果后面要做多交易所、长历史、统一质量的 liquidation 研究，再考虑付费数据

### `onchain`

这类最要区分原始数据和加工后指标。

原始数据层面：

- 公共 RPC
- 浏览器 API
- 开源 SQL / 社区数据集
- 免费层分析平台

通常可以低成本起步。

但真正贵的是：

- 地址标签
- 交易所归因
- entity-adjusted 指标
- 跨链统一口径
- 长期维护和历史回补

适合当前阶段的结论：

- 第一版不作为主线数据源
- 等主线策略稳定后，再决定是否采购链上数据平台

## 3. 每类数据适合什么策略

### `basis / funding / OI`

这类最适合做主线策略。

适合的策略类型：

- 趋势确认
- 拥挤度识别
- 过热反转
- carry / basis 套利

更适合：

- `1h` 到 `1d` 的中低频
- 永续合约方向盘
- 合约趋势确认和仓位调整

不太适合：

- 高频盘口策略
- 只靠单一极值做短时冲击交易

### `liquidations`

这类更适合做事件增强和风险控制。

适合的策略类型：

- liquidation cascade 监控
- 极端事件后的反转观察
- 波动率 regime 切换
- 风险开关和减仓规则

更适合：

- 风控层
- 事件层
- timing filter

不建议第一版直接把它当作主 alpha。

### `onchain`

这类更适合中低频增强，不适合当前第一版主线。

适合的策略类型：

- 现货选币
- 板块轮动
- 基本面增强
- 资金流确认

在当前阶段的定位：

- 先不纳入主链路
- 后续作为第二阶段扩展项评估

## 4. 第一版建议接哪些具体接口

如果只做中低频永续合约，且第一家交易所先做 `Binance USDT-M`，建议第一版只接这些：

### 必接

- 合约元信息：`exchangeInfo`
  - 获取 `symbol`、`tick size`、`lot size`、交易状态
- 永续 K 线：`klines`
  - 主频先用 `1h`
- Funding 历史：`fundingRate`
  - 用于 funding 水平、过热过滤和 z-score
- OI 当前值：`openInterest`
  - 用于实时监控
- OI 历史：`openInterestHist`
  - 用于 `OI change` 和 `price + OI regime`
- Premium / basis：
  - `premiumIndex`
  - `premiumIndexKlines`
  - `basis`
  - 这是主线策略的核心数据
- Liquidation 实时流：
  - `forceOrder` 类 stream
  - 第一版建议直接录流并做聚合

### 建议补但不要做重

- `24h ticker` 或基础成交额
  - 用于 universe 过滤和流动性筛选
- 基础可交易性字段
  - 用于风险过滤，不用于高频

### 第一版不建议先接

- 多交易所同时接入
- 完整 order book
- 链上指标
- 复杂事件新闻流

## 5. 第一版优先做哪 3 个策略

### 策略 1：趋势确认主线

定位：

- 第一条主 alpha
- 优先级最高

核心逻辑：

- 价格趋势成立
- `OI` 同向上升
- `basis` 同向扩张
- `funding` 没有过热到失真

适合频率：

- `1h` 生成信号
- `4h` 做确认
- 持仓 `8h - 3d`

### 策略 2：拥挤度反转

定位：

- 第二条 alpha
- 在主线稳定后再做

核心逻辑：

- `funding` 极端
- `basis` 极端
- `OI` 堆积
- 价格开始钝化或背离

适合频率：

- `4h - 1d`
- 持仓 `4h - 2d`

### 策略 3：liquidation 事件风险层

定位：

- 不建议第一版把它当独立主策略
- 更适合作为 overlay

核心逻辑：

- 爆仓潮来临时，市场结构容易恶化
- 先用于降杠杆、暂停新开仓、调整 timing
- 之后再考虑是否在极端事件后做反转或延续信号

适合频率：

- 原始数据实时或分钟级
- 聚合后供 `5m / 15m / 1h` 使用

## 6. 每个策略对应哪些字段和因子

### 策略 1：趋势确认主线

核心字段：

- `close`
- `volume`
- `open_interest`
- `funding_rate`
- `basis` 或 `premium_index`

建议因子：

- `ret_4h`
- `ret_1d`
- `breakout_20`
- `oi_change_4h`
- `oi_change_1d`
- `basis_change_4h`
- `basis_level_zscore`
- `funding_zscore_3d`
- `volume_surge_20`

### 策略 2：拥挤度反转

核心字段：

- `close`
- `open_interest`
- `funding_rate`
- `basis`

建议因子：

- `funding_zscore_3d`
- `basis_zscore_3d`
- `oi_zscore_3d`
- `price_oi_divergence`
- `basis_reversion_score`
- `funding_reversion_score`

### 策略 3：liquidation 事件风险层

核心字段：

- `liquidation_long_notional`
- `liquidation_short_notional`
- `liquidation_count`
- `close`
- `open_interest`
- `volume`

建议因子：

- `liq_spike_zscore`
- `liq_imbalance`
- `liq_notional_vs_dollar_volume`
- `post_liq_oi_drop`
- `short_horizon_realized_vol`
- `event_cooldown_flag`

## 7. 当前阶段明确不做什么

为了避免第一版越做越散，当前阶段明确不做：

- 不先接链上
- 不先做多交易所
- 不先把 liquidation 当独立主 alpha
- 不先做 order book / HFT / 做市
- 不先堆几十个因子
- 不先做过大的交易 universe
- 不先上复杂组合优化
- 不先直连实盘

## 8. 当前推荐的产品范围

如果现在就定第一版范围，建议这样收敛：

### 数据范围

- `Binance USDT-M`
- `OHLCV`
- `volume`
- `funding`
- `open interest`
- `basis / premium`
- `liquidations`

### 策略顺序

1. 先做“趋势确认主线”
2. 再加“liquidation 风险层”
3. 最后再做“拥挤度反转”

### 明确延后

- `onchain`
- 多交易所
- order book
- 高频
- 复杂优化
- 实盘直连

## 9. 对 `Signal Lab` 的直接建议

当前项目接下来的实现优先级建议是：

1. 把 `basis / premium` 接入数据层并落入标准化表
2. 把 `OI` 历史与衍生品指标因子补全
3. 把 liquidation stream 接入并聚合成中低频事件特征
4. 把 liquidation 因子接入风险过滤和杠杆控制
5. 用第一条“趋势确认主线”跑通长期研究、回测和 paper trading

这条路线的目标不是一开始就做“最全平台”，而是先做出一条能稳定复现的主线策略。