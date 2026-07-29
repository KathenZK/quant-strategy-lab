from __future__ import annotations

import json
from pathlib import Path

import sds_engine as engine


FAMILY_DIR = Path(__file__).resolve().parents[1]
OUTPUT = FAMILY_DIR / "artifacts/hype_15m_sds_baseline_cost_diagnostic.json"


def main() -> None:
    book = engine.build_book(include_locked_oos=False)
    costed = engine.run_backtest(book, engine.BASELINE_CONFIG)
    original_fee = engine.BASE_FEE
    original_slippage = engine.BASE_SLIPPAGE
    try:
        engine.BASE_FEE = 0.0
        engine.BASE_SLIPPAGE = 0.0
        zero_cost = engine.run_backtest(book, engine.BASELINE_CONFIG)
    finally:
        engine.BASE_FEE = original_fee
        engine.BASE_SLIPPAGE = original_slippage
    payload = {
        "family": "HYPE-15M-Sequential-Drift-State",
        "scope": "prefit only; locked OOS not loaded",
        "costed": costed.metrics,
        "zero_cost": zero_cost.metrics,
        "decision": (
            "zero-cost prefit is still deeply negative; turnover cost amplifies "
            "the failure but does not cause it"
        ),
    }
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
