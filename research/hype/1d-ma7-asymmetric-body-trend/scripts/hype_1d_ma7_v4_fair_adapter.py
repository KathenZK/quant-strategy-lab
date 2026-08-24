"""Pinned, read-only fair-window adapter for registered HYPE MA7 ABT V4.

The adapter deliberately reuses the original-trend harness only for its frozen
market inputs.  V4 itself remains the authoritative ``MA_ONLY`` compiled
variant from the registered V3 reversal-confirmation audit chain.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from functools import lru_cache
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from types import ModuleType
from typing import Any, Callable

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"

ORIGINAL_HARNESS_PATH = SCRIPT_DIR / "research_hype_1d_ma7_original_trend.py"
ORIGINAL_HARNESS_SHA256 = (
    "961c9acdd888c2edd3b3cd88818b34dbe02cc15308bd1919f5e789d16a126087"
)
ORIGINAL_ENGINE_PATH = SCRIPT_DIR / "hype_1d_ma7_original_trend_engine.py"
ORIGINAL_ENGINE_SHA256 = (
    "4e2bcfda0dd693968687f3cff1ca845df892e88d0eb5c82029333e828274f403"
)
CONFIRMATION_PATH = (
    SCRIPT_DIR / "audit_hype_1d_ma7_abt_v3_forced_reversal_confirmation.py"
)
CONFIRMATION_SHA256 = (
    "8dda2472da22f89761d3231da7d12e9a3bb9b4c67444c0436be4fd6d70d64543"
)
FORMATION_PATH = SCRIPT_DIR / "audit_hype_v1_trailing_stop_short_reversal.py"
FORMATION_SHA256 = (
    "35185bbdba87732a806ef3d5e0ff9fc9da9e314e8369695646e7b3f07cbb1166"
)
SEARCH_PATH = SCRIPT_DIR / "search_hype_1d_ma7_separated_trend.py"
SEARCH_SHA256 = (
    "c376f8bd1bae814b0ba53687380ee1060cf3cc3095ae815ebb0311ed1aef59e1"
)
BASE_PATH = SCRIPT_DIR / "research_hype_1d_ma7_asymmetric_body_trend.py"
BASE_SHA256 = (
    "05d76943a671d1463f8950f1f6e317d8653831fd0f72ea825a039caa1fb2a386"
)
SELECTED_SUMMARY_PATH = (
    ARTIFACT_DIR / "hype_1d_ma7_separated_summary_2026-08-04.json"
)
SELECTED_SUMMARY_SHA256 = (
    "ba6245f5ca1811cac9566abc78b09fdf24e846fd70a0f9265aaa8dd9360c97ae"
)

EXPECTED_BOOK_COUNT = 432
EXPECTED_TERMINAL_TS = pd.Timestamp("2026-08-06T00:00:00Z")
EXPECTED_HOURLY_SHA256 = (
    "e3598920ec9b4f6b9ddc5a7b186bf5153bd8d4ece35de1a3bbb188cd7de893ce"
)
EXPECTED_FUNDING_SHA256 = (
    "78b529b9d9433801c31aeb830be04d3686bc63da7b4b55926cb28b1254a685a6"
)
EXPECTED_FULL_EQUITY = 4.988406741729143
EXPECTED_FULL_MDD_PCT = -26.813853621046835
EXPECTED_FULL_TRADES = 17
BASE_SLIPPAGE = 0.0004


@dataclass(frozen=True, slots=True)
class V4FairContext:
    """Cached frozen inputs and the exact registered V4 callable."""

    original_harness: ModuleType
    confirmation: ModuleType
    formation: ModuleType
    engine: ModuleType
    market: Any
    long_config: Any
    short_config: Any
    backtest: Callable[..., Any]
    pins: tuple[tuple[str, str], ...]

    @property
    def book(self) -> Any:
        return self.market.book

    @property
    def features(self) -> Any:
        return self.market.features


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_hash(path: Path, expected: str) -> None:
    actual = _sha256(path)
    if actual != expected:
        raise RuntimeError(f"{path.name} drift: expected {expected}, got {actual}")


def _load_pinned(path: Path, expected: str, name: str) -> ModuleType:
    _assert_hash(path, expected)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import pinned module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _assert_declared_pin(
    owner: ModuleType,
    path_field: str,
    hash_field: str,
    expected_path: Path,
    expected_hash: str,
) -> None:
    declared_path = Path(getattr(owner, path_field)).resolve()
    declared_hash = str(getattr(owner, hash_field))
    if declared_path != expected_path.resolve():
        raise RuntimeError(
            f"{owner.__name__}.{path_field} drift: "
            f"expected {expected_path}, got {declared_path}"
        )
    if declared_hash != expected_hash:
        raise RuntimeError(
            f"{owner.__name__}.{hash_field} drift: "
            f"expected {expected_hash}, got {declared_hash}"
        )
    _assert_hash(expected_path, expected_hash)


def _assert_market_contract(market: Any) -> None:
    if market.book.count != EXPECTED_BOOK_COUNT:
        raise RuntimeError(
            f"frozen book count drift: expected {EXPECTED_BOOK_COUNT}, "
            f"got {market.book.count}"
        )
    terminal = pd.Timestamp(market.book.terminal_ts)
    if terminal != EXPECTED_TERMINAL_TS:
        raise RuntimeError(
            f"frozen terminal drift: expected {EXPECTED_TERMINAL_TS}, got {terminal}"
        )
    checks = {
        "hourly_sha256": EXPECTED_HOURLY_SHA256,
        "phase_input_hourly_sha256": EXPECTED_HOURLY_SHA256,
        "funding_sha256": EXPECTED_FUNDING_SHA256,
    }
    for field, expected in checks.items():
        actual = market.audit.get(field)
        if actual != expected:
            raise RuntimeError(
                f"frozen input {field} drift: expected {expected}, got {actual}"
            )


@lru_cache(maxsize=1)
def load_context() -> V4FairContext:
    """Load and cache the complete pinned V4 fair-window dependency chain."""

    original = _load_pinned(
        ORIGINAL_HARNESS_PATH,
        ORIGINAL_HARNESS_SHA256,
        "hype_ma7_v4_fair_original_harness",
    )
    _assert_declared_pin(
        original,
        "ENGINE_PATH",
        "ENGINE_SHA256",
        ORIGINAL_ENGINE_PATH,
        ORIGINAL_ENGINE_SHA256,
    )
    _assert_declared_pin(
        original,
        "SEARCH_PATH",
        "SEARCH_SHA256",
        SEARCH_PATH,
        SEARCH_SHA256,
    )
    _assert_declared_pin(
        original,
        "BASE_PATH",
        "BASE_SHA256",
        BASE_PATH,
        BASE_SHA256,
    )
    market = original.load_market(0)
    _assert_market_contract(market)

    confirmation = _load_pinned(
        CONFIRMATION_PATH,
        CONFIRMATION_SHA256,
        "hype_ma7_v4_fair_confirmation",
    )
    _assert_declared_pin(
        confirmation,
        "FORMATION_PATH",
        "FORMATION_SHA256",
        FORMATION_PATH,
        FORMATION_SHA256,
    )
    formation = confirmation.load_pinned(
        FORMATION_PATH,
        FORMATION_SHA256,
        "hype_ma7_v4_fair_formation",
    )
    _assert_declared_pin(
        formation,
        "ENGINE_PATH",
        "ENGINE_SHA256",
        SEARCH_PATH,
        SEARCH_SHA256,
    )
    _assert_declared_pin(
        formation,
        "BASE_PATH",
        "BASE_SHA256",
        BASE_PATH,
        BASE_SHA256,
    )
    _assert_declared_pin(
        formation,
        "SUMMARY_PATH",
        "SUMMARY_SHA256",
        SELECTED_SUMMARY_PATH,
        SELECTED_SUMMARY_SHA256,
    )
    engine = formation.load_pinned(
        SEARCH_PATH,
        SEARCH_SHA256,
        "hype_ma7_v4_fair_search",
    )
    selected = formation.read_pinned_json(
        SELECTED_SUMMARY_PATH,
        SELECTED_SUMMARY_SHA256,
    )["historically_profitable_all_checks"][0]
    if selected.get("label") != "post_reveal_combined_observation_041":
        raise RuntimeError(f"selected V1 identity drift: {selected.get('label')}")

    long_config = engine.Config(**selected["long_config"])
    short_config = replace(
        engine.Config(**selected["short_config"]),
        exit_buffer_atr=0.75,
    )
    backtest = confirmation.build_filtered_backtest(
        formation,
        engine,
        confirmation.MA_ONLY,
    )
    pins = (
        ("original_harness", ORIGINAL_HARNESS_SHA256),
        ("original_engine", ORIGINAL_ENGINE_SHA256),
        ("confirmation", CONFIRMATION_SHA256),
        ("formation", FORMATION_SHA256),
        ("search", SEARCH_SHA256),
        ("base", BASE_SHA256),
        ("selected_summary", SELECTED_SUMMARY_SHA256),
        ("hourly", EXPECTED_HOURLY_SHA256),
        ("funding", EXPECTED_FUNDING_SHA256),
    )
    return V4FairContext(
        original_harness=original,
        confirmation=confirmation,
        formation=formation,
        engine=engine,
        market=market,
        long_config=long_config,
        short_config=short_config,
        backtest=backtest,
        pins=pins,
    )


def run_v4(
    start_index: int,
    terminal_index: int,
    slippage: float = BASE_SLIPPAGE,
    signal_lag: int = 0,
    retain: bool = False,
) -> Any:
    """Run only exact ``MA_ONLY`` V4 on the cached frozen market context."""

    context = load_context()
    return context.backtest(
        context.book,
        context.features,
        long_config=context.long_config,
        short_config=context.short_config,
        start_index=start_index,
        terminal_index=terminal_index,
        slippage=slippage,
        signal_lag=signal_lag,
        include_funding=True,
        retain=retain,
    )


def verify_full_baseline(*, retain: bool = False) -> Any:
    """Explicitly run and verify the sole registered V4 full-window anchor."""

    context = load_context()
    result = run_v4(0, context.book.count, retain=retain)
    equity = float(result.metrics["equity_multiple"])
    if not math.isclose(
        equity,
        EXPECTED_FULL_EQUITY,
        rel_tol=1e-12,
        abs_tol=1e-12,
    ):
        raise RuntimeError(
            f"V4 full equity drift: expected {EXPECTED_FULL_EQUITY}, got {equity}"
        )
    max_drawdown = float(result.metrics["max_drawdown_pct"])
    if not math.isclose(
        max_drawdown,
        EXPECTED_FULL_MDD_PCT,
        rel_tol=1e-12,
        abs_tol=1e-12,
    ):
        raise RuntimeError(
            "V4 full MDD drift: "
            f"expected {EXPECTED_FULL_MDD_PCT}, got {max_drawdown}"
        )
    metric_trades = int(result.metrics["closed_trades"])
    actual_trades = len(result.trades)
    if metric_trades != EXPECTED_FULL_TRADES or actual_trades != EXPECTED_FULL_TRADES:
        raise RuntimeError(
            "V4 full trade-count drift: "
            f"expected {EXPECTED_FULL_TRADES}, "
            f"metrics={metric_trades}, retained={actual_trades}"
        )
    return result


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if not args.self_test:
        parser.error("this read-only adapter only exposes the --self-test command")
    result = verify_full_baseline()
    print(
        json.dumps(
            {
                "equity_multiple": result.metrics["equity_multiple"],
                "max_drawdown_pct": result.metrics["max_drawdown_pct"],
                "closed_trades": result.metrics["closed_trades"],
                "terminal_ts": load_context().book.terminal_ts.isoformat(),
                "context_cache": load_context.cache_info()._asdict(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    _main()
