# BIN-1H-MA7-RHT P1 非 HYPE Development 诊断

## 结论

P0 容量与数据质量通过，P1 逐小时 hazard timing 明确失败。模型不仅没有跨资产择时能力，OOF 概率在 root 内对成本后收益呈显著反向排序；等待模型 first-hit 相比同一 root 的 `k=0` 立即入场明显更差。因此关闭“跨资产共享 daily MA7 raw-cross prior”，不读取 HYPE、不生成 frozen model。

状态：`HARD-GATE-FAILED / explore / not promoted / not live-ready`。

## 数据与容量

- 市场：Binance USD-M perpetual；BTC/ETH/BNB/SOL/TRX。
- 数据边界：输入严格早于 `2025-05-31 00:00 UTC`，root 严格早于 `2025-05-20 00:00 UTC`。
- 五资产 direct `1h` 均无缺 K；UTC `1d` 与 24 根小时 K 重建最大相对误差为零。
- 完整 raw cross `2,053` 个；满足结果窗口的 eligible roots `2,018` 个，其中 long `1,008`、short `1,010`。
- person-period panel `155,856` 行；`8bps/fill + fee 0.001/fill + actual funding` 正标签率 `33.84%`。
- HYPE rows consumed / files opened 均为 `0`。

## 严格 OOF 结果

外层为 `leave-one-asset-out × 4 expanding-time folds`，内层同时选择 `C` 与 first-hit threshold。20 个 outer fold 中仅 5 个找到满足内层最低门槛的配置，最终只接受 30 个 roots：

- 主压力 `z_8bps`：平均每笔 `−0.0437%`（固定 `0.25x`），PF `0.948`，复合 `−2.03%`，事件序列 MDD `−10.40%`；
- positive assets：`1/5`；positive outer folds：`1/20`；
- root 内 `Spearman(probability, z_8bps)` 中位数 `−0.406`，有可评估样本的 BTC/SOL/TRX 三资产全部为负；
- `asset × 90d` cluster bootstrap：`P(mean>0)=43.48%`；
- `12bps`、funding-off、lag `+1h` 均未形成正 mean 与合格 PF。

## 为什么失败

1. **daily MA7 root prior 不稳定**：把 soft cross 作为共同方向先验，无法跨资产稳定区分趋势起点与均值回归噪声。
2. **逐小时等待方向错误**：同一批 30 个 OOF selected roots 若在 `k=0` 立即入场，平均收益比 first-hit 高 `3.663pp`；配对 cluster bootstrap 的 `P(Δ>0)=0`。
3. **排序不是弱而是反向**：模型概率越高，root 内未来成本后收益总体越低；这不是提高样本量或微调 threshold 可以修复的校准问题。
4. **选择覆盖坍缩**：15/20 outer folds 无合格 inner 配置，ETH/BNB 完全无 OOF 成交；降低门槛只会把合同明确排除的不稳定配置重新引入。
5. **静态特征也无救援价值**：full 相对仅含 root 静态项的 control，cluster bootstrap `P(Δutility>0)=44.49%`。

## 决定

- P1 `HARD-GATE-FAILED`；不保存模型、不解锁 HYPE transfer、不继续增加树模型、asset id、方向 route、threshold、窗口或 maturity 变体。
- 失败同时否定 LMML 与 RHT 的共同假设：从 daily MA7 cross 出发，再等待“成熟时点”不能提供可迁移的经济筛选。
- 按预冻结合同转向 materially new mechanism：原生 `1h` 波动归一化 impulse/breakout 建 root，显式 pullback/reclaim 入场，固定 bracket/timeout；先做透明 rule-based 跨资产验证。

## 证据

- [P0/P1 合同](../specs/binance-1h-ma7-rht-p0-p1-contract-2026-08-10.md)
- [P0 容量与数据质量](../artifacts/p1_development_2026-08-10/p0_data_capacity.json)
- [P1 摘要](../artifacts/p1_development_2026-08-10/p1_summary.json)
- [P1 完整报告](../artifacts/p1_development_2026-08-10/p1_report.json)
- [Root table](../artifacts/p1_development_2026-08-10/p0_roots.parquet)
- [Person-period panel](../artifacts/p1_development_2026-08-10/p0_person_period_panel.parquet)
- [OOF row scores](../artifacts/p1_development_2026-08-10/p1_oof_row_scores.parquet)
- [OOF first-hit decisions](../artifacts/p1_development_2026-08-10/p1_oof_root_decisions.parquet)
- [证据 manifest](../artifacts/p1_development_2026-08-10/manifest.json)
- [研究脚本](../scripts/research_binance_1h_ma7_rht_p1.py)
- [回归测试](../../../../tests/test_binance_1h_ma7_rht_p1.py)
