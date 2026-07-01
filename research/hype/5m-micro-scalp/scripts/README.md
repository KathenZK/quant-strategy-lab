# HYPE-5M-Micro-Scalp Scripts

Scripts in this directory are family-scoped research scripts. They are not active package code.

Use `uv run python research/hype/5m-micro-scalp/scripts/<script>.py` from the repository root so paths resolve against the data lake and family artifact directories.

Current scripts:

- `research_hype_5m_micro_scalp_search.py`: strict first search for the original `3-5` trades/day high-win micro-scalp target.
- `research_hype_5m_micro_scalp_relaxed_rounds.py`: round-by-round relaxed-constraint search.
- `research_hype_5m_micro_scalp_candidate_robustness.py`: local neighborhood robustness check for the better relaxed candidates.
- `research_hype_5m_micro_scalp_v1_full_ablation.py`: `HYPE-5M-Micro-Scalp-V1` baseline reproduction and one-at-a-time full parameter ablation.
- `research_hype_5m_micro_scalp_v1_simplified_combo_search.py`: fixes dormant V1 fields under `vwap_revert` and searches combinations of the effective parameters.
- `research_hype_5m_micro_scalp_v1_simplified_candidate_robustness.py`: local neighborhood robustness sweep for the simplified combo leads and preferred paper-audit observation.
- `research_hype_5m_micro_scalp_v1_1_ablation_and_tuning.py`: records `HYPE-5M-Micro-Scalp-V1.1`, runs full one-at-a-time parameter ablation, and micro-tunes the effective fields.
