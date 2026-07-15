from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from as6s_engine import (
    BASE_SLIPPAGE,
    PREFIT_END,
    REUSED_END,
    SYMBOLS,
    StrategyConfig,
    load_funding,
    load_symbol_frame,
    metrics,
    simulate_opportunities,
)


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
PREFIT_PATH = FAMILY_DIR / "artifacts/binance_15m_as6s_prefit_search_2026-07-14.json"
OUTPUT = FAMILY_DIR / "artifacts/binance_15m_as6s_reused_holdout_2026-07-14.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def diagnostic_classification(base: dict[str, float], stress: dict[str, float], k2: dict[str, float]) -> str:
    if base["trades"] < 5:
        return "insufficient_reused_evidence"
    common = (
        base["max_dd"] > -0.20
        and stress["max_dd"] > -0.20
        and k2["max_dd"] > -0.20
        and base["total_return"] > 0.0
        and stress["total_return"] > 0.0
        and k2["total_return"] > 0.0
    )
    if common and base["trades"] >= 8 and base["win_rate"] >= 0.80:
        return "strong_survivor"
    if common and base["trades"] >= 5 and base["win_rate"] >= 0.70:
        return "conditional_survivor"
    return "eliminated"


def main() -> None:
    payload = json.loads(PREFIT_PATH.read_text(encoding="utf-8"))
    if payload.get("stage") != "prefit_only_reused_holdout_unread_for_this_family":
        raise RuntimeError("prefit artifact has an unexpected stage marker")
    if payload.get("selection_end_exclusive") != PREFIT_END.isoformat():
        raise RuntimeError("prefit cutoff mismatch")
    if payload.get("search", {}).get("trials_per_symbol_mechanism") != 1500:
        raise RuntimeError("refusing to reveal holdout before the 1500-trial search is frozen")
    frozen = payload.get("selected_best_per_mechanism", [])
    if len(frozen) != 18:
        raise RuntimeError(f"expected 18 frozen configs, got {len(frozen)}")

    results: dict[str, dict[str, Any]] = {symbol: {} for symbol in SYMBOLS}
    for symbol in SYMBOLS:
        frame = load_symbol_frame(symbol, end=REUSED_END)
        funding = load_funding(symbol, end=REUSED_END)
        for raw in (item for item in frozen if item["symbol"] == symbol):
            cfg = StrategyConfig.from_dict(raw)
            base = simulate_opportunities(
                frame, funding, cfg, end=REUSED_END, slippage=BASE_SLIPPAGE
            )
            stress = simulate_opportunities(
                frame, funding, cfg, end=REUSED_END, slippage=0.0008
            )
            k2 = simulate_opportunities(
                frame,
                funding,
                cfg,
                end=REUSED_END,
                slippage=BASE_SLIPPAGE,
                entry_delay_bars=2,
            )
            windows = {
                "reused_base": metrics(base, start=PREFIT_END, end=REUSED_END),
                "reused_8bps": metrics(stress, start=PREFIT_END, end=REUSED_END),
                "reused_k_plus_2": metrics(k2, start=PREFIT_END, end=REUSED_END),
                "through_reused_base": metrics(
                    base, start=frame["ts"].iloc[0], end=REUSED_END
                ),
                "through_reused_8bps": metrics(
                    stress, start=frame["ts"].iloc[0], end=REUSED_END
                ),
                "through_reused_k_plus_2": metrics(
                    k2, start=frame["ts"].iloc[0], end=REUSED_END
                ),
            }
            results[symbol][cfg.mechanism] = {
                "config": cfg.to_dict(),
                "prefit_rank": next(
                    row
                    for row in payload["mechanism_prefit_ranking"][symbol]
                    if row["config_id"] == cfg.config_id
                ),
                "diagnostic_classification": diagnostic_classification(
                    windows["reused_base"],
                    windows["reused_8bps"],
                    windows["reused_k_plus_2"],
                ),
                **windows,
            }
        print(f"revealed {symbol}", flush=True)

    output = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "family": "Binance-15M-Asset-Specific-Six-Strategy-Selector",
        "stage": "reused_holdout_revealed_elimination_only",
        "prefit_artifact": str(PREFIT_PATH.relative_to(ROOT)),
        "prefit_sha256": sha256(PREFIT_PATH),
        "reused_window": [PREFIT_END.isoformat(), REUSED_END.isoformat()],
        "classification_policy": {
            "strong_survivor": "base trades>=8, win_rate>=80%, positive base/8bps/K+2, all DD<20%",
            "conditional_survivor": "base trades>=5, win_rate>=70%, positive base/8bps/K+2, all DD<20%",
            "insufficient_reused_evidence": "base trades<5; not eligible for the account candidate pool",
            "eliminated": "all other outcomes",
            "role": "diagnostic elimination only; never select a lower-ranked config using reused results",
        },
        "results": results,
    }
    OUTPUT.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        json.dumps({"output": str(OUTPUT), "sha256": sha256(OUTPUT)}, indent=2),
        flush=True,
    )


if __name__ == "__main__":
    main()
