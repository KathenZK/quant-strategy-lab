# Multi-Horizon EMA Forecast Kernel

跨 HYPE `15m` 与 `1h` 家族复用的多参数 EMA forecast 构建、连续目标仓位回测、成本/资金费结算与 recent-slice 报告内核。

## 冻结版本

| Version | 文件 | SHA256 | 说明 |
| --- | --- | --- | --- |
| `v1` | [v1/engine.py](v1/engine.py) | `63d754088ac55b958b5a5536d4ae8f5049d6b6c9c48a0fca7dc89c770d6e31c4` | EMA `8/32`、`16/64`、`32/128`、`64/256` 波动率归一化 forecast；权重 `0.2/0.3/0.3/0.2`；K+1 open 连续仓位；手续费、滑点与 funding。 |

`v1` 已由消费方按 SHA256 pin，内容永久冻结。任何逻辑修复或扩展必须新建 `v2/`。

## 消费方

- [HYPE-15M-Multi-Horizon-EMA-Forecast](../../hype/15m-multi-horizon-ema-forecast/README.md)
- [HYPE-1H-Multi-Horizon-EMA-Forecast](../../hype/1h-multi-horizon-ema-forecast/README.md)
- [HYPE-1D-Multi-Horizon-EMA-Forecast](../../hype/1d-multi-horizon-ema-forecast/README.md)（复用执行/成本/funding 模块；日线 EWMAC 特征在消费方适配）
- [BTC-1D-Classic-CTA-Trend](../../btc/1d-classic-cta-trend/README.md)（复用 EMA / 执行 / 成本 / funding 模块；日线 EWMAC 与波动率缩放在消费方适配）

产物与结论分别保存在消费方家族目录；本目录不保存跨家族实验输出。
