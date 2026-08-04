# HYPE-15M-Multi-Timeframe-Probe-Pyramiding

- Full family name：`HYPE-15M-Multi-Timeframe-Probe-Pyramiding`（alias：`HYPE-15M-MTPP`）
- 市场/周期：Binance USD-M `HYPEUSDT` perpetual；完整周/日 K 定假设，`4h/1h/15m` 择时，`15m` 执行。
- 机制：日周方向只负责允许试单；RSI/KDJ 回踩恢复寻找位置；先试仓，只有真实浮盈与新回踩恢复共同确认后才滚仓，退出由结构止损、迟滞保护和半 MFE 回吐控制。
- 当前状态：`explore / diagnostic-only / not promoted / not live-ready`；尚无策略版本。

## 边界

- 独立于 `HYPE-15M-MDTP`、`HYPE-1H-PKTSC`、`HYPE-D15-HTO` 与 `HYPE-15M-MII`；不继承它们的参数、证据或状态。
- 本轮不预测趋势延续概率，也不让 RSI/KDJ 负责判断趋势寿命；指标只用于把主观“找个较好位置”固定成可复现的试单/加仓触发。
- 历史 HYPE 已被多条研究查看，只称 historical causal diagnostic；`2026-08-02` 起 prospective OOS 不读取。

## 入口

- 主账：[hype-15m-mtpp-core-ledger.md](hype-15m-mtpp-core-ledger.md)
- 决策记录：[decision-log.md](decision-log.md)
- 冻结合同：[初始研究合同](specs/hype-15m-mtpp-initial-research-contract-2026-08-03.md)
- 初始验证：[交易员式试单—确认—滚仓研究](diagnostics/hype-15m-mtpp-initial-research-2026-08-03.md)
- 复现入口：[scripts/README.md](scripts/README.md)
- 产物说明：[artifacts/README.md](artifacts/README.md)
