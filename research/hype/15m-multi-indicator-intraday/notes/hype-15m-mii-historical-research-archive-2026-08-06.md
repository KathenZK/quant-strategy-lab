# HYPE-15M-MII 历史研究归档

本文承接主账压缩前的长叙事，只保存版本演化与关键负结论；参数真值仍以对应 spec、诊断、消融和产物为准。

## V1 到 V1.2

- V1 将 RSI7 crossing、MACD 方向、ATR96%、固定 TP/SL 与 1.5x 组合为首个冻结基线；修复不可执行时序后完整 gate `0/62`，证明早期漂亮结果不能作为实盘候选。
- V1base 放宽 RSI 与 ATR 条件，并以 `TP=1.20% / SL=3.60% / hold=16 / 2x` 形成高收益观察；K+2 回撤扩大到 `-36.28%`，只保留诊断身份。
- V1.1 删除 1h confirm、RSI14 band、ADX、H4、ret、churn、cooldown 等未生效表达，与 V1base 逐笔等价。最近 1 周无交易不是代码错误；动态 trailing 止盈失败。
- BTC/ETH 直接迁移没有证明跨资产稳定性，不能继承 HYPE 版本身份。
- V1.2 把固定 TP/SL 改为入场时一次性 ATR96 bracket：`TP=1.25ATR / SL=5ATR / hold=24`。K+1 年化 `311.35%`、DD `-17.74%`；K+2 年化 `154.96%`、DD `-34.81%`。
- V1.2 消融确认 `ATR96>=0.75%` 与 `RVOL96>=1.0` 都有用；去 ATR 后明显恶化，两个同时去掉转负。MACD 方向过滤也不是可随意删除的文档噪音。

## V1.3

- V1.3 只把暴露从 2x 调到固定 2.5x，不改变信号与 bracket。
- K+1 总收益 `549.30%`、年化 `472.15%`、DD `-22.01%`；K+2 总收益 `239.38%`、年化 `212.47%`、DD `-41.89%`。
- ATR 动态 2x–3x 没有形成优于固定暴露且更稳健的新版本。
- “近期不开单”源于信号稀疏与 ATR/RVOL 条件，不是 runner 漏单；ATR96 口径必须只使用信号时可得的闭合 K。
- `min_atr_pct96` 与 RVOL 提频网格显示，单纯放宽阈值会以回撤和延迟脆弱性换频率。

## V1.4 与 V1.4A

- V1.4 只把 `min_rvol96` 从 `1.0` 降到 `0.85`。标准数据湖 K+1 为 232 笔、总收益 `978.36%`、DD `-24.70%`；K+2 总收益 `535.54%`、DD `-38.30%`。
- TP/SL 邻域表明高收益与回撤存在明显交换，不能只按全样本收益选点。
- 亏损环境过滤中，`ATR14/ATR96 <= 1.75` 是唯一 strict DD gate 观察候选；其余时间、趋势和波动过滤未形成稳定改善。
- 动态止损 strict/defensive gate `0/12`，不得继续在同一假设上讲述“自适应止损”优势。
- V1.4A 保留 V1.4 入场，仅改为 `TP=1.40ATR / SL=3ATR`，于 2026-07-10 替代 V1.3 dry-run。Recent API K+1 最近 90d/30d 为 `78.82%/27.09%`；全样本 `584.90% / -32.85% DD / 78.72% win`。
- 共享行情组停摆区间作废；pending parity JSON 缺失只阻塞新 promotion，不改变既有 runner 授权。

## 证据索引

- [V1 全参数消融](../ablations/hype-15m-mii-v1-full-parameter-ablation-2026-06-29.md)
- [V1 live feasibility](../diagnostics/hype-15m-mii-v1-live-feasibility-2026-06-29.md)
- [V1.2 外部复现规格](../specs/hype-15m-mii-v1-2-reproduction-spec-not-live-ready-2026-06-30.md)
- [V1.3 live spec](../live-specs/hype-15m-mii-v1-3-live-parameter-spec-not-live-ready-2026-07-01.md)
- [V1.4 参数规格](../specs/hype-15m-mii-v1-4-parameter-spec-not-live-ready-2026-07-08.md)
- [V1.4A dry-run spec](../live-specs/hype-15m-mii-v1-4a-dry-run-validation-spec-not-live-ready-2026-07-10.md)
- [runner tracking](../runner-tracking/hype-15m-mii-runner-2026-07-10.md)
