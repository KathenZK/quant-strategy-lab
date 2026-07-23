# Bollinger-Keltner Squeeze Breakout Kernel

跨 HYPE `15m`、`1h`、`4h`、`1d` 家族复用的 Bollinger-inside-Keltner
squeeze、release、压缩区间突破、15m 子柱执行与 funding 回测内核。

## 冻结版本

| Version | 文件 | SHA256 | 说明 |
| --- | --- | --- | --- |
| `v1` | [v1/engine.py](v1/engine.py) | `1640f7a451b0768c1c8395ea10b135b7e30d0a61e3b6006e7178cac415da841e` | `BB(20,2)` / `KC(20,1.5)`，连续 3 根 squeeze，3 根 release-breakout 窗口，中轨/3ATR/40bar 退出；K1/K2、零成本、事件研究。 |

`v1` 一旦由消费方按 SHA256 pin，内容永久冻结；修复或扩展必须新建 `v2/`。

## 消费方

- [HYPE-15M-Bollinger-Keltner-Squeeze-Breakout](../../hype/15m-bollinger-keltner-squeeze-breakout/README.md)
- [HYPE-1H-Bollinger-Keltner-Squeeze-Breakout](../../hype/1h-bollinger-keltner-squeeze-breakout/README.md)
- [HYPE-4H-Bollinger-Keltner-Squeeze-Breakout](../../hype/4h-bollinger-keltner-squeeze-breakout/README.md)
- [HYPE-1D-Bollinger-Keltner-Squeeze-Breakout](../../hype/1d-bollinger-keltner-squeeze-breakout/README.md)
