# Scripts

- [research_hype_15m_multi_horizon_ema_forecast.py](research_hype_15m_multi_horizon_ema_forecast.py)：校验共享内核 SHA，读取并审计标准数据湖，运行四条 EMA sleeve、加权组合、`0.10` 调仓缓冲和 1x 永续买入持有对照，生成报告与 artifacts。

复现：

```bash
uv run python research/hype/15m-multi-horizon-ema-forecast/scripts/research_hype_15m_multi_horizon_ema_forecast.py --run-date 2026-07-14
```

脚本固定引用 [multi-horizon-ema-forecast v1](../../../_shared-kernels/multi-horizon-ema-forecast/README.md)，SHA256 `63d754088ac55b958b5a5536d4ae8f5049d6b6c9c48a0fca7dc89c770d6e31c4`。

## V2 连续目标仓位 observation

- [mhef_v2_engine.py](mhef_v2_engine.py)：家族内 V2 研究内核；多周期连续 forecast、coherence、dead zone、波动率目标、目标带边界追踪、最小调仓量、单 K 限速、next-open 执行与 funding/cost 对账。
- [freeze_hype_15m_mhef_v2_dataset.py](freeze_hype_15m_mhef_v2_dataset.py)：数据质量审计并冻结 train/tune/prefit-validation/复用 OOS 边界。
- [research_hype_15m_mhef_v2_development.py](research_hype_15m_mhef_v2_development.py)：仅在 development 内完成组件消融、逐参数敏感性、信号网格和执行网格，并在验证前写出唯一候选及 hash。
- [validate_hype_15m_mhef_v2_candidate.py](validate_hype_15m_mhef_v2_candidate.py)：只接受冻结候选，一次揭示 prefit validation；包含零/双倍成本、精确目标、buy-and-hold 与 moving-block bootstrap 诊断。
- [diagnose_hype_15m_mhef_v2_candidate_ablation.py](diagnose_hype_15m_mhef_v2_candidate_ablation.py)：验证失败后仅使用原 Train/Tune 对冻结候选做 `71` 组逐槽消融和仓位路径等价检查；只诊断参数角色，不重选候选。

V2 已完成一次验证并判 `NO-GO`；验证脚本的 unread guard 不允许把同一候选重复当作首次揭示。完整复现顺序和结果见 [V2 报告](../notes/hype-15m-mhef-v2-continuous-target-research-2026-07-28.md)。
