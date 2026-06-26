# HYPE-5M-Micro-Scalp Scripts

Scripts in this directory are family-scoped research scripts. They are not active package code.

Use `uv run python research/hype/5m-micro-scalp/scripts/<script>.py` from the repository root so paths resolve against the data lake and family artifact directories.

Current scripts:

- `research_hype_5m_micro_scalp_search.py`: strict first search for the original `3-5` trades/day high-win micro-scalp target.
- `research_hype_5m_micro_scalp_relaxed_rounds.py`: round-by-round relaxed-constraint search.
- `research_hype_5m_micro_scalp_candidate_robustness.py`: local neighborhood robustness check for the better relaxed candidates.
