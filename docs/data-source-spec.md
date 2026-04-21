# 数据源与表结构规范

这份文档定义 `Signal Lab` 当前阶段的中低频永续合约数据范围、来源、刷新方式和标准化表结构。

适用范围：

- 第一版只做中低频永续合约
- 第一家交易所先做 `Binance USDT-M`
- 主线策略先围绕 `basis / funding / OI`
- `liquidations` 先作为事件层和风险层

## 1. 当前阶段数据范围

第一版只保留这 6 类数据：

- `ohlcv`
- `funding_rates`
- `open_interest`
- `basis_or_premium`
- `liquidations`
- `asset_metadata`

其中：

- `ohlcv` 和 `volume` 是底座
- `funding_rates`、`open_interest`、`basis_or_premium` 是主线 alpha 数据
- `liquidations` 是事件增强和风险控制数据
- `asset_metadata` 是交易和风控的基础依赖

当前阶段明确不接：

- `onchain_metrics`
- `ticker_or_top_of_book` 的高频持续采集
- 完整 `order book`
- 多交易所统一历史库

## 2. 数据来源优先级

### 第一优先级：交易所原生公开接口

适合：

- `funding`
- `OI`
- `basis`
- `premium index`
- `liquidations`

原因：

- 免费
- 字段最原始
- 延迟最低
- 足够支撑第一版研究与回测

### 第二优先级：`ccxt`

适合：

- `OHLCV`
- 部分 `funding`
- 部分 `OI`

原因：

- 接入成本低
- 接口统一
- 适合作为项目内的基础适配层

但要注意：

- 某些衍生品字段不够完整
- `basis` 和 `liquidations` 不建议完全依赖抽象层

### 第三优先级：第三方专业数据商

当前阶段先不接。

只在这些情况再评估：

- 需要多交易所统一历史
- 需要更长历史深度
- 需要完整 liquidation 历史
- 需要更高质量缺失修复

## 3. Binance USDT-M 第一版接口范围

### 必接接口

- 合约元信息
  - `exchangeInfo`
- 永续 K 线
  - `klines`
- Funding 历史
  - `fundingRate`
- OI 当前值
  - `openInterest`
- OI 历史
  - `openInterestHist`
- Premium / basis
  - `premiumIndex`
  - `premiumIndexKlines`
  - `basis`
- Liquidation 实时流
  - `forceOrder` 类 stream

### 建议补但不做重

- `24h ticker`
  - 用于 universe 过滤和基础流动性检查
- 标记价格 / 指数价格
  - 用于 basis 计算和回测参考

### 当前阶段不建议接

- 完整盘口深度
- 高频成交明细作为主研究对象
- 多交易所并行接入

## 4. 刷新频率建议

### `ohlcv`

- 主存储频率：`1h`
- 可选派生频率：`4h`、`1d`
- 刷新方式：
  - 回填历史时全量拉取
  - 日常运行时增量更新

### `funding_rates`

- 原始频率按交易所返回粒度存储
- 常见使用频率：`8h` 或对齐到 `1h`
- 研究层可派生：
  - 当前 funding
  - rolling mean
  - z-score

### `open_interest`

- 优先保留原始历史粒度
- 研究层统一对齐到 `1h`
- 常用派生：
  - `oi_change_4h`
  - `oi_change_1d`
  - `oi_zscore`

### `basis_or_premium`

- 原始层尽量保留交易所原始数据
- 研究层统一对齐到 `1h`
- 常用派生：
  - level
  - change
  - z-score

### `liquidations`

- 原始层存事件流
- 研究层聚合为：
  - `5m`
  - `15m`
  - `1h`

常用聚合字段：

- 多头爆仓名义金额
- 空头爆仓名义金额
- 爆仓次数
- 爆仓不平衡度

## 5. 标准化命名与字段约定

统一约定：

- 时间统一为 `UTC`
- `symbol` 统一大写
- `exchange`、`market_type`、`source` 统一小写
- 原始层保留交易所字段
- 标准化层统一字段名与字段类型

核心通用字段：

- `ts`
- `exchange`
- `symbol`
- `market_type`
- `base_asset`
- `quote_asset`
- `source`
- `date`

## 6. 标准化表定义

### `ohlcv`

用途：

- 所有价格因子和回测的底座

核心字段：

- `ts`
- `exchange`
- `symbol`
- `market_type`
- `base_asset`
- `quote_asset`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `source`
- `date`

分区建议：

- `exchange`
- `market_type`
- `symbol`
- `date`

### `funding_rates`

用途：

- funding 水平
- funding z-score
- 拥挤度和 carry 研究

核心字段：

- `ts`
- `exchange`
- `symbol`
- `market_type`
- `base_asset`
- `quote_asset`
- `funding_rate`
- `next_funding_ts`
- `source`
- `date`

分区建议：

- `exchange`
- `market_type`
- `symbol`
- `date`

### `open_interest`

用途：

- `OI change`
- `price + OI regime`
- 拥挤度和趋势确认

核心字段：

- `ts`
- `exchange`
- `symbol`
- `market_type`
- `base_asset`
- `quote_asset`
- `open_interest`
- `open_interest_value`
- `source`
- `date`

分区建议：

- `exchange`
- `market_type`
- `symbol`
- `date`

### `basis_or_premium`

用途：

- basis 水平
- basis 扩张/收缩
- perp pricing 偏离

核心字段：

- `ts`
- `exchange`
- `symbol`
- `market_type`
- `base_asset`
- `quote_asset`
- `basis`
- `premium_index`
- `mark_price`
- `index_price`
- `annualized_basis`
- `source`
- `date`

说明：

- 第一版允许部分字段为空
- 关键是先保证 `basis` 或 `premium_index` 至少有一个稳定来源

分区建议：

- `exchange`
- `market_type`
- `symbol`
- `date`

### `liquidations`

用途：

- 极端事件检测
- 风险过滤
- 杠杆切换

原始事件字段：

- `ts`
- `exchange`
- `symbol`
- `market_type`
- `side`
- `price`
- `size`
- `notional`
- `source`
- `date`

聚合特征层建议字段：

- `ts`
- `exchange`
- `symbol`
- `market_type`
- `liquidation_long_notional`
- `liquidation_short_notional`
- `liquidation_count`
- `liquidation_imbalance`
- `source`
- `date`

### `asset_metadata`

用途：

- universe 管理
- 交易约束
- 订单和风控校验

核心字段：

- `exchange`
- `symbol`
- `market_type`
- `base_asset`
- `quote_asset`
- `status`
- `tick_size`
- `lot_size`
- `min_notional`
- `source`

## 7. 特征层派生规范

特征层不直接复制所有原始表，而是只保存可复用因子输入。

第一版重点派生：

### 价格与流动性

- `ret_1h`
- `ret_4h`
- `ret_1d`
- `breakout_20`
- `volume_surge_20`
- `dollar_volume`

### 衍生品

- `funding_zscore_3d`
- `oi_change_4h`
- `oi_change_1d`
- `oi_zscore_3d`
- `basis_change_4h`
- `basis_level_zscore`
- `price_oi_regime`

### liquidation 事件层

- `liq_spike_zscore`
- `liq_notional_vs_dollar_volume`
- `liq_imbalance`
- `post_liq_oi_drop`
- `event_cooldown_flag`

## 8. 数据质量检查

第一版必须做的校验：

- 时间戳去重
- 时区统一
- 数值字段可解析
- 同一 symbol 同一时间只保留一条标准化记录
- 极端异常值检查
- 缺失率统计

对 `liquidations` 额外要求：

- 流断连要有状态记录
- 聚合层要能识别空窗口和真实无事件窗口

## 9. 增量刷新策略

当前推荐使用：

- `ohlcv`：按 `timeframe` 增量刷新，带少量 overlap
- `funding_rates`：按最后时间戳增量刷新
- `open_interest`：按最后时间戳增量刷新
- `basis_or_premium`：按最后时间戳增量刷新
- `liquidations`：实时写入原始流，定时聚合

增量状态至少记录：

- 数据集名称
- `exchange`
- `symbol`
- `market_type`
- `timeframe`
- 最后成功时间戳
- 最近写入路径
- 写入行数

## 10. 第一版的验收标准

当这份规范落地后，项目至少要做到：

- 一条命令刷新 `Binance USDT-M` 的主线数据
- 一条命令生成主线因子所需特征
- `basis / funding / OI` 能稳定进入回测链路
- `liquidations` 能落原始流并产出聚合特征
- 任意一份研究结果都能追溯到具体数据源、刷新时间和特征版本