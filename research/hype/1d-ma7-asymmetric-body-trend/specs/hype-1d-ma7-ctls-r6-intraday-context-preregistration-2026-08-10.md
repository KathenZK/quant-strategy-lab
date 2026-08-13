# CTLS-R6日内路径与BTC上下文预注册合同

> 冻结时间：2026-08-10。R6是状态准确率路线的最终机制级尝试；此前未访问CTLS LES/PnL。

## 不变项

复用R4稳定趋势段标签、R3 5折forward训练、31模型、R5的EMA/base hysteresis/duration共4,464项以及全部方向门。标签、交易规则、窗口和随机种子不变。

## 新增因果X

每个UTC日收盘后，从该日已闭合24根HYPE 1h计算：全日/前6h/后6h收益、1h realized volatility、up/down semivol、24点线性斜率/ATR7、close location、正收益小时占比、前后半日动量差、日内最大回撤/反弹、volume总量/集中度/1日与3日变化；从event-time funding计算当日sum/abs-sum/last及变化。

从冻结BTCUSDT perpetual 1h文件同窗计算：全日/前6h/后6h收益、realized vol、range、线性斜率、volume变化；再计算HYPE-BTC日收益差与过去5日相关性。BTC数据只截到HYPE日收盘，不得使用下一小时。

所有新增rolling只向后；任何日缺24根HYPE/BTC、时间错位、非有限OHLCV或数据SHA漂移均fail closed。BTC输入固定为`data/features/btcusdt_1h_stop_path_v1/btcusdt_perp_1h.parquet`，其SHA由manifest在搜索前锁定。

## 停止规则

R6仍须同时满足balanced accuracy>=0.55、三类recall各>=0.40、flip<=0.15、至少4/5折>=0.50。通过才允许阶段研究；0项通过则确认当前432日样本不足以稳定识别完整趋势状态，停止PnL/LES/杠杆，不再新开同历史参数或模型搜索。

