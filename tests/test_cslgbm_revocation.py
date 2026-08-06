from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FAMILY = ROOT / "research/asset-portfolios/1h-cross-sectional-lightgbm-selector"


def test_repository_routes_expose_formula_invalidation() -> None:
    research_index = (ROOT / "research/README.md").read_text(encoding="utf-8")
    portfolio_index = (ROOT / "research/asset-portfolios/README.md").read_text(
        encoding="utf-8"
    )
    family_readme = (FAMILY / "README.md").read_text(encoding="utf-8")
    assert "formula-invalidated / HARD-GATE-FAILED" in research_index
    assert "旧绩效因空头公式错误全部撤销" in portfolio_index
    assert "V1 OOS artifact 撤销清单" in family_readme
