"""Audit delayed impulse-confirmation fallback entries on registered V7."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from types import ModuleType
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CONTRACT_PATH = (
    FAMILY_DIR / "specs/hype-1d-ma7-abt-v7-issue-optimization-omnibus-contract-2026-08-11.md"
)
OUTPUT_PATH = ARTIFACT_DIR / "hype_1d_ma7_abt_v7_delayed_impulse_confirmation_2026-08-11.json"
STALE_RUNNER_PATH = SCRIPT_DIR / "audit_hype_1d_ma7_abt_v7_stale_reclaim_probe.py"
TOP_N_STRESS = 20


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if hasattr(value, "item"):
        return sanitize(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_locked(payload: dict[str, Any]) -> str:
    sidecar = Path(f"{OUTPUT_PATH}.sha256")
    if OUTPUT_PATH.exists() or sidecar.exists():
        raise RuntimeError(f"locked artifact exists: {OUTPUT_PATH.name}")
    encoded = (
        json.dumps(sanitize(payload), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    ).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    with OUTPUT_PATH.open("xb") as handle:
        handle.write(encoded)
    with sidecar.open("x", encoding="utf-8") as handle:
        handle.write(f"{digest}  {OUTPUT_PATH.name}\n")
    return digest


@dataclass(frozen=True, slots=True)
class ImpulseConfig:
    name: str
    side_scope: str
    side_pos20_cap: float
    body_vs_med20_min: float
    body_range_min: float
    progress_atr_min: float
    probe_leverage: float
    enabled: bool = True
    lookback_days: int = 10
    max_age_days: int = 4
    long_rsi_threshold: float = 30.0
    short_rsi_threshold: float = 70.0
    reverse_ratio: float = 0.50

    def __post_init__(self) -> None:
        if self.side_scope not in ("both", "long_only", "short_only"):
            raise ValueError("unknown side_scope")
        if self.side_pos20_cap not in (0.45, 0.55):
            raise ValueError("side_pos20_cap outside frozen set")
        if self.body_vs_med20_min not in (1.50, 2.00, 2.50):
            raise ValueError("body_vs_med20_min outside frozen set")
        if self.body_range_min not in (0.55, 0.65):
            raise ValueError("body_range_min outside frozen set")
        if self.progress_atr_min not in (0.50, 0.80):
            raise ValueError("progress_atr_min outside frozen set")
        if self.probe_leverage not in (0.50, 1.00):
            raise ValueError("probe_leverage outside frozen set")

    def canonical(self) -> dict[str, Any]:
        return asdict(self)

    def applies_to(self, side: int) -> bool:
        return self.side_scope == "both" or (
            self.side_scope == "long_only" and side > 0
        ) or (self.side_scope == "short_only" and side < 0)


class DelayedImpulseSignal:
    """Native V7 entry OR reverse-RSI tag confirmed by a later impulse candle."""

    def __init__(
        self,
        native_signal: Any,
        long_config: Any,
        short_config: Any,
        config: ImpulseConfig,
    ) -> None:
        self.native_signal = native_signal
        self.long_config = long_config
        self.short_config = short_config
        self.config = config
        self.rsi6: Any = None
        self.events: list[dict[str, Any]] = []
        self.active_side = 0
        self.armed_at: int | None = None
        self.tag_close = math.nan
        self.tag_atr = math.nan
        self.cached_index: int | None = None
        self.cached_decisions = {1: False, -1: False}
        self.cached_sources = {1: None, -1: None}

    @staticmethod
    def _finite(*values: float) -> bool:
        return all(math.isfinite(float(value)) for value in values)

    @staticmethod
    def _side_name(side: int) -> str:
        return "long" if side > 0 else "short"

    def _record(self, event: str, index: int, side: int = 0, **extra: Any) -> None:
        row: dict[str, Any] = {"event": event, "signal_index": int(index), **extra}
        if side:
            row["side"] = self._side_name(side)
        self.events.append(row)

    def _clear(self) -> None:
        self.active_side = 0
        self.armed_at = None
        self.tag_close = math.nan
        self.tag_atr = math.nan

    def notify_exit(self, side: int, index: int, reason: str) -> None:
        self._clear()

    def notify_entry(self, side: int, index: int, source: str) -> None:
        self._clear()

    def decision_source(self, side: int) -> str | None:
        return self.cached_sources[int(side)]

    def _native(self, book: Any, features: Any, index: int) -> dict[int, bool]:
        return {
            1: bool(self.native_signal(self.long_config, book, features, index)),
            -1: bool(self.native_signal(self.short_config, book, features, index)),
        }

    def _raw_cross(self, book: Any, features: Any, index: int) -> int:
        if index < 1:
            return 0
        prior_close, prior_ma7, close, ma7 = (
            float(book.close[index - 1]),
            float(features.ma7[index - 1]),
            float(book.close[index]),
            float(features.ma7[index]),
        )
        if not self._finite(prior_close, prior_ma7, close, ma7):
            return 0
        if prior_close <= prior_ma7 and close > ma7:
            return 1
        if prior_close >= prior_ma7 and close < ma7:
            return -1
        return 0

    def _side_pos20(self, side: int, book: Any, index: int) -> float:
        high20 = max(float(x) for x in book.high[max(0, index - 20) : index + 1])
        low20 = min(float(x) for x in book.low[max(0, index - 20) : index + 1])
        close = float(book.close[index])
        if high20 <= low20:
            return math.nan
        pos = (close - low20) / (high20 - low20)
        return pos if side > 0 else 1.0 - pos

    def _tag_pass(self, side: int, book: Any, index: int) -> dict[str, Any]:
        lookback = self.config.lookback_days
        if index < lookback or self.rsi6 is None or not self.config.applies_to(side):
            return {"passed": False, "reason": "scope_or_history"}
        reverse_count = 0
        rsi_values = []
        for offset in range(index - lookback, index):
            day_open = float(book.open[offset])
            day_close = float(book.close[offset])
            if side > 0 and day_close < day_open:
                reverse_count += 1
            elif side < 0 and day_close > day_open:
                reverse_count += 1
            rsi_values.append(float(self.rsi6[offset]))
        reverse_ratio = reverse_count / lookback
        min_rsi = min(rsi_values)
        max_rsi = max(rsi_values)
        rsi_pass = min_rsi <= self.config.long_rsi_threshold if side > 0 else max_rsi >= self.config.short_rsi_threshold
        side_pos20 = self._side_pos20(side, book, index)
        passed = (
            reverse_ratio >= self.config.reverse_ratio
            and rsi_pass
            and math.isfinite(side_pos20)
            and side_pos20 <= self.config.side_pos20_cap
        )
        return {
            "passed": bool(passed),
            "reverse_count": reverse_count,
            "reverse_ratio": reverse_ratio,
            "min_rsi10": min_rsi,
            "max_rsi10": max_rsi,
            "side_pos20": side_pos20,
            "rsi_pass": bool(rsi_pass),
        }

    def _median_body20(self, book: Any, index: int) -> float:
        values = [
            abs(float(book.close[offset]) - float(book.open[offset]))
            for offset in range(max(1, index - 20), index)
        ]
        values = [value for value in values if math.isfinite(value)]
        return float(np.median(values)) if values else math.nan

    def _impulse_pass(self, side: int, book: Any, features: Any, index: int) -> dict[str, Any]:
        open_ = float(book.open[index])
        high = float(book.high[index])
        low = float(book.low[index])
        close = float(book.close[index])
        ma7 = float(features.ma7[index])
        median_body = self._median_body20(book, index)
        if not self._finite(open_, high, low, close, ma7, median_body, self.tag_close, self.tag_atr) or self.tag_atr <= 0.0:
            return {"passed": False, "reason": "nonfinite"}
        body = abs(close - open_)
        range_ = max(high - low, 1e-12)
        body_vs_med20 = body / median_body if median_body > 0.0 else math.nan
        body_range = body / range_
        side_body_atr = side * (close - open_) / self.tag_atr
        progress_atr = side * (close - self.tag_close) / self.tag_atr
        side_pass = side * (close - ma7) > 0.0
        passed = (
            side_pass
            and side_body_atr > 0.0
            and body_vs_med20 >= self.config.body_vs_med20_min
            and body_range >= self.config.body_range_min
            and progress_atr >= self.config.progress_atr_min
        )
        return {
            "passed": bool(passed),
            "body_vs_med20": body_vs_med20,
            "body_range": body_range,
            "side_body_atr": side_body_atr,
            "progress_atr": progress_atr,
            "side_pass": bool(side_pass),
        }

    def _update_tag(self, book: Any, features: Any, index: int) -> dict[int, bool]:
        decisions = {1: False, -1: False}
        raw_side = self._raw_cross(book, features, index)
        if raw_side and self.config.enabled:
            stats = self._tag_pass(raw_side, book, index)
            if bool(stats.get("passed")):
                self.active_side = raw_side
                self.armed_at = int(index)
                self.tag_close = float(book.close[index])
                self.tag_atr = float(features.atr7[index])
                self._record("delayed_impulse_arm", index, raw_side, **stats)
            else:
                self._record("delayed_impulse_tag_reject", index, raw_side, **stats)
        if not self.active_side or self.armed_at is None:
            return decisions
        side = self.active_side
        age = int(index - self.armed_at)
        if age > self.config.max_age_days:
            self._record("delayed_impulse_expire", index, side, age=age)
            self._clear()
            return decisions
        close = float(book.close[index])
        ma7 = float(features.ma7[index])
        if self._finite(close, ma7) and side * (close - ma7) <= 0.0:
            self._record("delayed_impulse_recross", index, side, age=age)
            self._clear()
            return decisions
        if age < 1:
            return decisions
        impulse = self._impulse_pass(side, book, features, index)
        if bool(impulse.get("passed")):
            decisions[side] = True
            self._record(
                "delayed_impulse_confirm",
                index,
                side,
                armed_at_index=self.armed_at,
                age=age,
                **impulse,
            )
            self._clear()
        return decisions

    def _evaluate(self, book: Any, features: Any, index: int) -> None:
        self.cached_index = int(index)
        self.cached_decisions = {1: False, -1: False}
        self.cached_sources = {1: None, -1: None}
        native = self._native(book, features, index)
        if native[1] or native[-1]:
            side = 1 if native[1] else -1
            self.cached_decisions = native
            self.cached_sources[side] = "native"
            self._clear()
            return
        impulse = self._update_tag(book, features, index)
        if impulse[1] or impulse[-1]:
            side = 1 if impulse[1] else -1
            self.cached_decisions = impulse
            self.cached_sources[side] = "stale_reclaim"

    def __call__(self, config: Any, book: Any, features: Any, index: int) -> bool:
        if self.cached_index != index:
            self._evaluate(book, features, index)
        return bool(self.cached_decisions[int(config.side)])


def candidate_grid() -> list[ImpulseConfig]:
    rows = []
    for scope in ("both", "long_only", "short_only"):
        for side_pos20_cap in (0.45, 0.55):
            for body_mult in (1.50, 2.00, 2.50):
                for body_range in (0.55, 0.65):
                    for progress in (0.50, 0.80):
                        for leverage in (0.50, 1.00):
                            rows.append(
                                ImpulseConfig(
                                    name=(
                                        f"DI_{scope}_P20{side_pos20_cap:.2f}_B{body_mult:.2f}_"
                                        f"R{body_range:.2f}_G{progress:.2f}_L{leverage:.2f}"
                                    ).replace(".", "p"),
                                    side_scope=scope,
                                    side_pos20_cap=side_pos20_cap,
                                    body_vs_med20_min=body_mult,
                                    body_range_min=body_range,
                                    progress_atr_min=progress,
                                    probe_leverage=leverage,
                                )
                            )
    if len(rows) != 144:
        raise RuntimeError("delayed impulse grid drift")
    return rows


def patch_signal(stale: ModuleType, config: ImpulseConfig, rsi6: Any) -> None:
    class BoundDelayedImpulseSignal(DelayedImpulseSignal):
        def __init__(self, native_signal: Any, long_config: Any, short_config: Any, ignored: Any) -> None:
            super().__init__(native_signal, long_config, short_config, config)
            self.rsi6 = rsi6

    stale.StaleReclaimSignal = BoundDelayedImpulseSignal


def run_once(stale: ModuleType, base: ModuleType, transition: ModuleType, full_ablation: ModuleType, context: Any, config: ImpulseConfig, **kwargs: Any) -> dict[str, Any]:
    patch_signal(stale, config, transition._BASE.wilder_rsi6(context.book.close))
    result = stale.run_raw(base, transition, full_ablation, context, config, **kwargs)
    row = stale.normalize(
        base,
        full_ablation,
        context,
        result,
        days=kwargs["window"][1] - kwargs["window"][0],
        slippage=kwargs["slippage"],
        include_funding=kwargs["include_funding"],
    )
    for event in (
        "delayed_impulse_arm",
        "delayed_impulse_confirm",
        "delayed_impulse_expire",
        "delayed_impulse_recross",
        "delayed_impulse_tag_reject",
    ):
        row["activation_counts"][event] = sum(
            item.get("event") == event for item in result.signal_events
        )
    return row


def run_stress(stale: ModuleType, base: ModuleType, transition: ModuleType, full_ablation: ModuleType, context: Any, config: ImpulseConfig) -> dict[str, Any]:
    stress = {}
    for key, window, slippage, include_funding, signal_lag in [
        ("base_full", stale.FULL, stale.BASE_SLIPPAGE, True, 0),
        ("slippage_8bps", stale.FULL, stale.STRESS_SLIPPAGE, True, 0),
        ("funding_off", stale.FULL, stale.BASE_SLIPPAGE, False, 0),
        ("lag_1d", stale.FULL, stale.BASE_SLIPPAGE, True, 1),
    ]:
        stress[key] = run_once(
            stale,
            base,
            transition,
            full_ablation,
            context,
            config,
            window=window,
            slippage=slippage,
            include_funding=include_funding,
            signal_lag=signal_lag,
            retain=False,
        )
    for block_index, window in enumerate(stale.BLOCKS):
        stress[f"block_{block_index:02d}"] = run_once(
            stale,
            base,
            transition,
            full_ablation,
            context,
            config,
            window=window,
            slippage=stale.BASE_SLIPPAGE,
            include_funding=True,
            signal_lag=0,
            retain=False,
        )
    terminal = stale.FULL[1]
    for label, span in stale.RECENT_SLICES.items():
        left = max(0, terminal - span)
        stress[f"recent_{label}"] = run_once(
            stale,
            base,
            transition,
            full_ablation,
            context,
            config,
            window=(left, terminal),
            slippage=stale.BASE_SLIPPAGE,
            include_funding=True,
            signal_lag=0,
            retain=False,
        )
    return stress


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if not args.run:
        raise SystemExit("use --run to execute")

    stale = load_module(STALE_RUNNER_PATH, "di_stale_runner")
    base = load_module(stale.BASE_ABLATION_PATH, "di_base")
    transition = load_module(base.TRANSITION_PATH, "di_transition")
    full_ablation = load_module(base.FULL_ABLATION_PATH, "di_full_ablation")
    v7_audit = load_module(base.V7_AUDIT_PATH, "di_v7_context")
    base2 = v7_audit.load_module(v7_audit.BASE_2X_AUDIT_PATH, "di_base2")
    _, _, _, _, context, _ = v7_audit.load_runtime(base2)

    control_config = ImpulseConfig(
        name="CTRL_EXACT_V7",
        side_scope="both",
        side_pos20_cap=0.45,
        body_vs_med20_min=1.50,
        body_range_min=0.55,
        progress_atr_min=0.50,
        probe_leverage=1.00,
        enabled=False,
    )
    control = run_once(
        stale,
        base,
        transition,
        full_ablation,
        context,
        control_config,
        window=stale.FULL,
        slippage=stale.BASE_SLIPPAGE,
        include_funding=True,
        signal_lag=0,
        retain=False,
    )
    if not (
        math.isclose(control["net_return_pct"], stale.EXPECTED_V7_RETURN, abs_tol=0.05)
        and math.isclose(control["chronological_1h_mdd_pct"], stale.EXPECTED_V7_1H_MDD, abs_tol=0.02)
        and int(control["closed_trades"]) == stale.EXPECTED_V7_TRADES
    ):
        raise RuntimeError(f"V7 anchor drift: {control}")

    ranking = []
    configs = candidate_grid()
    for index, config in enumerate(configs, 1):
        print(f"[base {index:03d}/{len(configs)}] {config.name}")
        row = run_once(
            stale,
            base,
            transition,
            full_ablation,
            context,
            config,
            window=stale.FULL,
            slippage=stale.BASE_SLIPPAGE,
            include_funding=True,
            signal_lag=0,
            retain=False,
        )
        ranking.append(
            {
                "config": config.canonical(),
                "base_full": row,
                "base_verdict": stale.base_verdict(row, control),
            }
        )
    ranking.sort(
        key=lambda row: (
            row["base_verdict"]["full_dual_better"],
            row["base_full"]["net_return_pct"],
            row["base_verdict"]["mdd_delta_vs_v7_pp"],
        ),
        reverse=True,
    )
    selected_names: list[str] = []
    for row in ranking:
        if row["base_verdict"]["full_dual_better"]:
            selected_names.append(row["config"]["name"])
    for row in ranking:
        name = row["config"]["name"]
        if name not in selected_names:
            selected_names.append(name)
        if len(selected_names) >= TOP_N_STRESS:
            break
    by_name = {config.name: config for config in configs}
    stressed = {}
    for index, name in enumerate(selected_names, 1):
        print(f"[stress {index:02d}/{len(selected_names)}] {name}")
        stress = run_stress(stale, base, transition, full_ablation, context, by_name[name])
        stressed[name] = {
            "config": by_name[name].canonical(),
            "stress": stress,
            "verdict": stale.stress_verdict(stress, control),
        }
    payload = {
        "schema": "hype-1d-ma7-abt-v7-delayed-impulse-confirmation-v1",
        "status": "COMPLETED_POST_REVEAL_DIAGNOSTIC",
        "research_state": "V7 unchanged / delayed impulse confirmation diagnostic only / not promoted / not live-ready",
        "contract": str(CONTRACT_PATH.relative_to(FAMILY_DIR)),
        "control": {"config": control_config.canonical(), "base_full": control},
        "grid_size": len(configs),
        "base_ranking": ranking,
        "stress_evaluated": selected_names,
        "stressed": stressed,
        "pins": {
            "contract_sha256": sha256(CONTRACT_PATH),
            "audit_script_sha256": sha256(Path(__file__).resolve()),
            "stale_runner_sha256": sha256(STALE_RUNNER_PATH),
        },
        "registered": False,
        "promoted": False,
        "live_ready": False,
        "exact_v7_changed": False,
        "clean_oos_claim": False,
    }
    digest = write_locked(payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "artifact": str(OUTPUT_PATH),
                "artifact_sha256": digest,
                "top5": [
                    {
                        "name": row["config"]["name"],
                        "ret": round(row["base_full"]["net_return_pct"], 2),
                        "mdd": round(row["base_full"]["chronological_1h_mdd_pct"], 2),
                        "trades": row["base_full"]["closed_trades"],
                        "arms": row["base_full"]["activation_counts"].get("delayed_impulse_arm", 0),
                        "confirms": row["base_full"]["activation_counts"].get("delayed_impulse_confirm", 0),
                        "dual": row["base_verdict"]["full_dual_better"],
                    }
                    for row in ranking[:5]
                ],
                "stress_decisions": {
                    name: row["verdict"]["decision"] for name, row in stressed.items()
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
