# HYPE-5M-Micro-Scalp Scripts

Scripts in this directory are family-scoped research scripts. They are not active package code.

Use `uv run python research/hype/5m-micro-scalp/scripts/<script>.py` from the repository root so paths resolve against the data lake and family artifact directories.

Current scripts:

- `research_hype_5m_micro_scalp_search.py`: strict first search for the original `3-5` trades/day high-win micro-scalp target.
- `research_hype_5m_micro_scalp_relaxed_rounds.py`: round-by-round relaxed-constraint search.
- `research_hype_5m_micro_scalp_candidate_robustness.py`: local neighborhood robustness check for the better relaxed candidates.
- `research_hype_5m_micro_scalp_v1_full_ablation.py`: `HYPE-5M-Micro-Scalp-V1` baseline reproduction and one-at-a-time full parameter ablation.
- `research_hype_5m_micro_scalp_v1_simplified_combo_search.py`: fixes dormant V1 fields under `vwap_revert` and searches combinations of the effective parameters.
- `research_hype_5m_micro_scalp_v1_simplified_candidate_robustness.py`: local neighborhood robustness sweep for the simplified combo leads and preferred audit observation.
- `research_hype_5m_micro_scalp_v1_1_ablation_and_tuning.py`: records `HYPE-5M-Micro-Scalp-V1.1`, runs full one-at-a-time parameter ablation, and micro-tunes the effective fields.
- `research_hype_5m_micro_scalp_v1_2_registration_and_leverage_retest.py`：将 `V1.1_tune_grid_004895` 登记为 V1.2，并按 fee `0.001`/fill、slippage `4 bps`/fill 对 V1.1/V1.2 做 `1x/2x/3x` 账户敞口复测。
- `research_hype_5m_micro_scalp_v1_3_simplified_ablation.py`：将 V1.2 不生效参数剔除并登记为 V1.3；跑基线回测、V1.2 逐笔等价验证，以及对 `18` 个有效字段做 one-at-a-time 全参数消融。
- `research_hype_5m_micro_scalp_v1_3_atr_dynamic_tp.py`：在 V1.3 信号不变前提下，将固定 `tp_bps=110` 替换为信号 K ATR 动态止盈（固定 `sl_bps=400`），与基线及多种 `tp_atr_mult` 对比回测。
- `research_hype_5m_micro_scalp_v1_3_atr_dynamic_leverage.py`：V1.3 信号与固定 TP/SL 不变，对比固定 `1x/2x/3x` 与按信号 K `atr_pct_bps` 线性变化的 `1x-3x` / `2x-3x` 动态杠杆。
