"""Backtest reverse-candle RSI tags with follow-through confirmation on V7."""

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


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CONTRACT_PATH = (
    FAMILY_DIR / "specs/hype-1d-ma7-abt-v7-reverse-rsi-followthrough-contract-2026-08-11.md"
)
OUTPUT_PATH = ARTIFACT_DIR / "hype_1d_ma7_abt_v7_reverse_rsi_followthrough_2026-08-11.json"
STALE_PROBE_PATH = SCRIPT_DIR / "audit_hype_1d_ma7_abt_v7_stale_reclaim_probe.py"

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
class FollowConfig:
    name: str
    side_scope: str
    reverse_ratio: float
    max_age_days: int
    min_progress_atr: float
    max_distance_atr: float
    probe_leverage: float
    enabled: bool = True
    min_age_days: int = 1
    lookback_days: int = 10
    long_rsi_threshold: float = 30.0
    short_rsi_threshold: float = 70.0

    def __post_init__(self) -> None:
        if self.side_scope not in ("both", "long_only", "short_only"):
            raise ValueError("unknown side_scope")
        if self.reverse_ratio not in (0.50, 0.60):
            raise ValueError("reverse_ratio outside frozen set")
        if self.max_age_days not in (2, 4):
            raise ValueError("max_age_days outside frozen set")
        if self.min_progress_atr not in (0.00, 0.25, 0.50):
            raise ValueError("min_progress_atr outside frozen set")
        if self.max_distance_atr not in (1.25, 1.50, math.inf):
            raise ValueError("max_distance_atr outside frozen set")
        if self.probe_leverage not in (0.25, 0.50, 1.00):
            raise ValueError("probe_leverage outside frozen set")

    def canonical(self) -> dict[str, Any]:
        row = asdict(self)
        if math.isinf(self.max_distance_atr):
            row["max_distance_atr"] = "INF"
        return row

    def applies_to(self, side: int) -> bool:
        return self.side_scope == "both" or (
            self.side_scope == "long_only" and side > 0
        ) or (self.side_scope == "short_only" and side < 0)


class ReverseRsiFollowSignal:
    def __init__(
        self,
        native_signal: Any,
        long_config: Any,
        short_config: Any,
        config: FollowConfig,
    ) -> None:
        self.native_signal = native_signal
        self.long_config = long_config
        self.short_config = short_config
        self.config = config
        self.events: list[dict[str, Any]] = []
        self.rsi6: Any = None
        self.active_side = 0
        self.armed_at: int | None = None
        self.tag_close = math.nan
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
        values = (
            float(book.close[index - 1]),
            float(features.ma7[index - 1]),
            float(book.close[index]),
            float(features.ma7[index]),
        )
        if not self._finite(*values):
            return 0
        prior_close, prior_ma7, close, ma7 = values
        if prior_close <= prior_ma7 and close > ma7:
            return 1
        if prior_close >= prior_ma7 and close < ma7:
            return -1
        return 0

    def _tag_pass(self, side: int, book: Any, features: Any, index: int) -> dict[str, Any]:
        lookback = self.config.lookback_days
        if index < lookback or self.rsi6 is None:
            return {"passed": False, "reason": "insufficient_history"}
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
        passed = reverse_ratio >= self.config.reverse_ratio and rsi_pass and self.config.applies_to(side)
        return {
            "passed": bool(passed),
            "reverse_count": reverse_count,
            "reverse_ratio": reverse_ratio,
            "min_rsi10": min_rsi,
            "max_rsi10": max_rsi,
            "rsi_pass": bool(rsi_pass),
        }

    def _criteria(self, side: int, book: Any, features: Any, index: int) -> dict[str, Any]:
        close = float(book.close[index])
        ma7 = float(features.ma7[index])
        atr7 = float(features.atr7[index])
        if not self._finite(close, ma7, atr7, self.tag_close) or atr7 <= 0.0:
            return {"finite": False}
        distance_atr = side * (close - ma7) / atr7
        progress_atr = side * (close - self.tag_close) / atr7
        return {
            "finite": True,
            "distance_atr": distance_atr,
            "progress_atr": progress_atr,
            "side_pass": bool(side * (close - ma7) > 0.0),
            "distance_cap_pass": bool(distance_atr <= self.config.max_distance_atr),
            "progress_pass": bool(progress_atr >= self.config.min_progress_atr),
        }

    def _update_tag(self, book: Any, features: Any, index: int) -> dict[int, bool]:
        decisions = {1: False, -1: False}
        raw_side = self._raw_cross(book, features, index)
        if raw_side and self.config.enabled:
            stats = self._tag_pass(raw_side, book, features, index)
            if bool(stats.get("passed")):
                self.active_side = raw_side
                self.armed_at = int(index)
                self.tag_close = float(book.close[index])
                self._record("stale_episode_arm", index, raw_side, **stats)
            else:
                self._record("followthrough_tag_reject", index, raw_side, **stats)
        if not self.active_side or self.armed_at is None:
            return decisions
        side = self.active_side
        age = int(index - self.armed_at)
        if age > self.config.max_age_days:
            self._record("stale_episode_expire", index, side, age=age)
            self._clear()
            return decisions
        criteria = self._criteria(side, book, features, index)
        if not criteria.get("finite"):
            return decisions
        if not bool(criteria["side_pass"]):
            self._record("stale_episode_recross", index, side, age=age)
            self._clear()
            return decisions
        if age < self.config.min_age_days:
            return decisions
        if bool(criteria["distance_cap_pass"]) and bool(criteria["progress_pass"]):
            decisions[side] = True
            self._record(
                "stale_episode_confirm",
                index,
                side,
                armed_at_index=self.armed_at,
                age=age,
                **criteria,
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
            self._record("native_entry_signal", index, side)
            self._clear()
            return
        episode = self._update_tag(book, features, index)
        if episode[1] or episode[-1]:
            side = 1 if episode[1] else -1
            self.cached_decisions = episode
            self.cached_sources[side] = "stale_reclaim"

    def __call__(self, config: Any, book: Any, features: Any, index: int) -> bool:
        if self.cached_index != index:
            self._evaluate(book, features, index)
        return bool(self.cached_decisions[int(config.side)])


def candidate_grid() -> list[FollowConfig]:
    rows: list[FollowConfig] = []
    for scope in ("both", "long_only", "short_only"):
        for ratio in (0.50, 0.60):
            for max_age in (2, 4):
                for progress in (0.00, 0.25, 0.50):
                    for max_distance in (1.25, 1.50, math.inf):
                        for leverage in (1.00, 0.50, 0.25):
                            rat = f"{ratio:.2f}".replace(".", "p")
                            prog = f"{progress:.2f}".replace(".", "p")
                            dist = "INF" if math.isinf(max_distance) else f"{max_distance:.2f}".replace(".", "p")
                            lev = f"{leverage:.2f}".replace(".", "p")
                            rows.append(
                                FollowConfig(
                                    name=f"FT_{scope}_R{rat}_A{max_age}_P{prog}_D{dist}_L{lev}",
                                    side_scope=scope,
                                    reverse_ratio=ratio,
                                    max_age_days=max_age,
                                    min_progress_atr=progress,
                                    max_distance_atr=max_distance,
                                    probe_leverage=leverage,
                                )
                            )
    if len(rows) != 324:
        raise RuntimeError("follow-through grid cardinality drift")
    return rows


def patch_signal(stale: ModuleType, config: FollowConfig, rsi6: Any) -> None:
    class BoundFollowSignal(ReverseRsiFollowSignal):
        def __init__(self, native_signal: Any, long_config: Any, short_config: Any, ignored: Any) -> None:
            super().__init__(native_signal, long_config, short_config, config)
            self.rsi6 = rsi6

    stale.StaleReclaimSignal = BoundFollowSignal


def run_once(stale: ModuleType, base: ModuleType, transition: ModuleType, full_ablation: ModuleType, context: Any, config: FollowConfig, **kwargs: Any) -> dict[str, Any]:
    patch_signal(stale, config, transition._BASE.wilder_rsi6(context.book.close))
    return stale.run_once(base, transition, full_ablation, context, config, **kwargs)


def run_stress(stale: ModuleType, base: ModuleType, transition: ModuleType, full_ablation: ModuleType, context: Any, config: FollowConfig) -> dict[str, Any]:
    patch_signal(stale, config, transition._BASE.wilder_rsi6(context.book.close))
    return stale.run_stress(base, transition, full_ablation, context, config)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if not args.run:
        raise SystemExit("use --run to execute the frozen diagnostic")

    stale = load_module(STALE_PROBE_PATH, "follow_stale_runner")
    base = load_module(stale.BASE_ABLATION_PATH, "follow_base_ablation")
    v7_audit = load_module(base.V7_AUDIT_PATH, "follow_context")
    base2 = v7_audit.load_module(v7_audit.BASE_2X_AUDIT_PATH, "follow_base2")
    _, _, _, _, context, _ = v7_audit.load_runtime(base2)
    transition = load_module(base.TRANSITION_PATH, "follow_transition")
    full_ablation = load_module(base.FULL_ABLATION_PATH, "follow_full_ablation")

    control_config = FollowConfig(
        name="CTRL_EXACT_V7",
        side_scope="both",
        reverse_ratio=0.50,
        max_age_days=2,
        min_progress_atr=0.00,
        max_distance_atr=1.25,
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

    configs = candidate_grid()
    base_ranking = []
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
        base_ranking.append(
            {
                "config": config.canonical(),
                "base_full": row,
                "base_verdict": stale.base_verdict(row, control),
            }
        )
    base_ranking.sort(
        key=lambda row: (
            row["base_verdict"]["full_dual_better"],
            row["base_full"]["net_return_pct"],
            row["base_verdict"]["mdd_delta_vs_v7_pp"],
        ),
        reverse=True,
    )
    selected_names: list[str] = []
    for row in base_ranking:
        if row["base_verdict"]["full_dual_better"]:
            selected_names.append(row["config"]["name"])
    for row in base_ranking:
        name = row["config"]["name"]
        if name not in selected_names:
            selected_names.append(name)
        if len(selected_names) >= TOP_N_STRESS:
            break
    config_by_name = {config.name: config for config in configs}
    stressed: dict[str, Any] = {}
    for index, name in enumerate(selected_names, 1):
        print(f"[stress {index:02d}/{len(selected_names)}] {name}")
        row = run_stress(stale, base, transition, full_ablation, context, config_by_name[name])
        row["config"] = config_by_name[name].canonical()
        row["verdict"] = stale.stress_verdict(row["stress"], control)
        stressed[name] = row
    payload = {
        "schema": "hype-1d-ma7-abt-v7-reverse-rsi-followthrough-v1",
        "status": "COMPLETED_POST_REVEAL_DIAGNOSTIC",
        "research_state": "V7 unchanged / reverse RSI follow-through diagnostic only / not promoted / not live-ready",
        "contract": str(CONTRACT_PATH.relative_to(FAMILY_DIR)),
        "control": {"config": control_config.canonical(), "base_full": control},
        "grid_size": len(configs),
        "stress_evaluated": selected_names,
        "market": "Binance USD-M HYPEUSDT perpetual",
        "timeframes": {"decision": "1d UTC", "risk_replay": "1h"},
        "data_range": {
            "start": str(context.book.ts[0]),
            "end": str(context.book.ts[431]),
            "terminal_ts": str(context.book.terminal_ts),
            "daily_bars": 432,
        },
        "cost_model": {
            "fee_per_fill": float(context.engine.FEE),
            "base_slippage_per_fill": stale.BASE_SLIPPAGE,
            "stress_slippage_per_fill": stale.STRESS_SLIPPAGE,
            "funding": "actual Binance funding events when include_funding=true",
        },
        "base_ranking": base_ranking,
        "stressed": stressed,
        "pins": {
            "contract_sha256": sha256(CONTRACT_PATH),
            "audit_script_sha256": sha256(Path(__file__).resolve()),
            "stale_probe_runner_sha256": sha256(STALE_PROBE_PATH),
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
                "top5_base": [
                    {
                        "name": row["config"]["name"],
                        "ret": row["base_full"]["net_return_pct"],
                        "mdd": row["base_full"]["chronological_1h_mdd_pct"],
                        "trades": row["base_full"]["closed_trades"],
                        "arms": row["base_full"]["activation_counts"].get("stale_episode_arm", 0),
                        "confirms": row["base_full"]["activation_counts"].get("stale_episode_confirm", 0),
                        "dual": row["base_verdict"]["full_dual_better"],
                    }
                    for row in base_ranking[:5]
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
