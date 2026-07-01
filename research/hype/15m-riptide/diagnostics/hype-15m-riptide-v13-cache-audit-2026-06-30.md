# HYPE-15M-Riptide-V13 缓存口径复现审计

## 结论

`HYPE-15M-Riptide-V13` 是 Binance HYPEUSDT 永续 `15m` 趋势背景下 RSI 回调 + RV regime 门 + ATR bracket 策略。按 `/Users/ZK/Downloads/SPEC-v13-RIPTIDE.md` 逐条实现后，本地 cache CSV 口径能复现出相近的交易画像和 WF 收益形状，但固定切点第一验收仍未逐笔/汇总完全对齐。本轮结论是 `diagnostic / reproduction-pending`，不能直接开始 sim-paper 计时。

- 固定 `cut_hi=104.7` 对照：`207.52%` 总收益、`-25.76%` 最大回撤、`419` 笔、胜率 `29.36%`、PF `1.46`、单笔 `29.0bp`。规格验收为 `+252.7% / MDD -26.9% / 431 笔 / 胜率 29.7% / PF 1.49 / 单笔 +31.5bp`。
- 150d 滚动逐 bar `cut_hi`：`123.42%` 总收益、`-13.21%` 最大回撤、`258` 笔、单笔 `33.2bp`。
- `train150/test21/step21` walk-forward：拼接 OOS `108.49%`、`-13.21%` 最大回撤、`255` 笔、正窗 `11/11`、最差窗 `1.07%`。规格锚为 `+100.4% / MDD -12.6% / 正窗 9-10 / 最差窗 -0.2%`。

## 数据口径

- 输入：`/Users/ZK/OpenCode/quant-strategy-lab/data/cache/hypeusdt_15m_fapi.csv`；覆盖 `2025-05-30T10:30:00+00:00` 至 `2026-06-25T13:45:00+00:00`，`37550` 根 `15m` bar，缺口 `0`，重复 `0`，OHLCV 硬违规 `0`。
- 本轮没有标准 raw/normalized parquet 对齐，也没有 Binance funding 序列；资金费按 `0` 处理。按仓库 data-first 规则，这只能算 cache 复现审计，不是可 promotion 证据。
- 1h RV 由本地 `15m` bar 聚合而来，只保留完整 4 根 `15m` 的 1h bar，再用 `known_at = 1h_open + 1h` 因果映射到 15m。

## 实现核对

- 信号在 `k` 收盘计算，成交在 `k+1` 开盘；出场可从入场当根 high/low 开始检查。
- EMA 使用 `alpha=2/(n+1), adjust=False, min_periods=n`；RSI/ATR 使用 Wilder RMA。
- 止损优先于止盈；保本 stop 只在 bar 收盘后 ratchet，保护下一根；无 flip exit。
- 成本使用规格的 taker `6bps/边`，往返 `12bps`；另做 `18/24bps` 成本压力测试。
- 固定切点成本压力：RT `18bps` 后总收益 `139.29%`、RT `24bps` 后总收益 `86.17%`、Binance 默认成本 RT `28bps` 后总收益 `57.47%`。
- Binance 默认成本 RT `28bps` 全部重算：固定切点 `57.47%`、150d rolling `47.99%`、WF `38.75%`。

## 固定切点出场画像

- 止损 `175`，保本 `118`，止盈 `75`，时停 `51`，强制结尾 `0`。

## 初步判断

这份规范的 live-executable 设计比许多旧回测更严谨，WF 结果也支持它不是纯样本内幻觉；但固定切点对照仍差 `12` 笔和约 `45pp` 总收益，不能按规格要求视为验收通过。最可能的差异来源包括：原始研发数据与本地 cache CSV 不同、1h RV 使用了真实 1h K 线而非 15m 聚合、RSI/ATR warmup 细节不同、时停 bars_held 计数差异，或规格里的验收数字来自另一份实现。下一步应先补标准 data lake 与 funding，再逐笔对账；在逐笔时间戳和方向对齐前，不应开始 sim-paper 计时。

## 产物

- 复现脚本：`research/hype/15m-riptide/scripts/research_hype_15m_riptide_v13_cache_audit.py`
- JSON 摘要：`research/hype/15m-riptide/artifacts/hype_15m_riptide_v13_cache_audit_2026-06-30.json`
- 交易明细：`research/hype/15m-riptide/artifacts/hype_15m_riptide_v13_cache_audit_trades_2026-06-30.csv`
- WF 窗口：`research/hype/15m-riptide/artifacts/hype_15m_riptide_v13_cache_audit_wf_windows_2026-06-30.csv`
