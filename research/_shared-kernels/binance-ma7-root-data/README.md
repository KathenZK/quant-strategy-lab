# Binance MA7 Root Data Kernel

跨资产 MA7 root 研究共用的 direct `1h` / UTC `1d` / funding 数据加载与质量对账、指标、soft cross、成本 funding 和事件序列指标内核。

## 冻结版本

| Version | 文件 | SHA256 | 说明 |
| --- | --- | --- | --- |
| `v1` | [v1/engine.py](v1/engine.py) | `3d7c6d295568b96627a4b6aa4efad0fc7fdc8a53503f9f4fa55922c7069bfa3d` | 五资产 feature-layer 读取、小时连续性、24h 日线重建、动态 funding、SMA7/ATR7/RSI6、soft cross 与 fixed-leverage 成本核算。 |

`v1` 已由消费方按 SHA256 pin，内容永久冻结；任何修复或扩展必须新增 `v2/`。

## 消费方

- [Binance-1D-MA7-Later-Maturity-Meta-Label](../../asset-portfolios/1d-ma7-later-maturity-meta-label/README.md)
- [Binance-1H-MA7-Root-Hazard-Timing](../../asset-portfolios/1h-ma7-root-hazard-timing/README.md)
