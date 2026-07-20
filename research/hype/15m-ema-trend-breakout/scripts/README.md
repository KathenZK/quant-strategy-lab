# HYPE-EMA-TB 脚本入口

本目录保存 `HYPE-EMA-Trend-Breakout` 的历史复现与专项诊断脚本，不是 runner。

共享 [EMA Trend-Breakout v2 内核](../../../_shared-kernels/ema-trend-breakout/README.md) 已完成 V39.2/V40 legacy parity，冻结 SHA256 为 `36e5d10c0d281701c46446344dd50af7a7589ec03285be3289e82362e1c2917a`。

当前 HYPE 脚本尚未正式消费该内核：大量专项脚本由家族原始实现整文件复制后加入不同 overlay，且目录内存在用户未提交实验。为避免破坏历史复现，本轮不批量改 import、不修改冻结内核。迁移前必须逐脚本：

1. 建立信号、交易签名、逐根 equity acceptance fixture。
2. 区分纯配置变体、出场 overlay 与真正引擎分叉。
3. 对等价部分改为显式 `v2/engine.py` 路径与 SHA256 pin。
4. 对无法等价的 overlay 保留家族脚本，并在对应诊断中说明分叉边界。

BTC 消费方已完成显式 pin，可参考 [BTC scripts README](../../../btc/15m-ema-trend-breakout/scripts/README.md)；不得直接复制 BTC 的 fixed-allocation / explicit-cost 配置覆盖 HYPE legacy 口径。
