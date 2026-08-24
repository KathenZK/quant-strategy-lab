from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from types import ModuleType
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-ma7-separated-trend-transfer"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
SCRIPT_DIR = FAMILY_DIR / "scripts"
RUN_DATE_DEFAULT = "2026-08-10"
COMMON_START = pd.Timestamp("2025-05-31T00:00:00Z")
ASSETS = {
    "BTCUSDT": "btc_usdt_usdt",
    "ETHUSDT": "eth_usdt_usdt",
}
XFER_PATH = SCRIPT_DIR / "research_binance_1d_ma7_separated_trend_transfer.py"
PEHC_ENGINE_PATH = (
    ROOT
    / "research/hype/1d-ma7-asymmetric-body-trend/scripts"
    / "hype_1d_ma7_profit_exit_handoff_continuity_engine.py"
)
ADAPTER_PATH = (
    ROOT
    / "research/hype/1d-ma7-asymmetric-body-trend/scripts"
    / "hype_1d_ma7_v4_fair_adapter.py"
)
V6_CONFIG_SHA256 = (
    "b155a35133224e77266ba0c22fb84ba1657ab89212a700e9f551b3fa3431af00"
)


@dataclass(slots=True)
class TransferContext:
    template: Any
    transfer_book: Any
    transfer_features: Any

    @property
    def original_harness(self) -> ModuleType:
        return self.template.original_harness

    @property
    def confirmation(self) -> ModuleType:
        return self.template.confirmation

    @property
    def formation(self) -> ModuleType:
        return self.template.formation

    @property
    def engine(self) -> ModuleType:
        return self.template.engine

    @property
    def long_config(self) -> Any:
        return self.template.long_config

    @property
    def short_config(self) -> Any:
        return self.template.short_config

    @property
    def book(self) -> Any:
        return self.transfer_book

    @property
    def features(self) -> Any:
        return self.transfer_features


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Zero-tuning BTC/ETH transfer of exact HYPE 1D MA7 ABT V6."
    )
    parser.add_argument("--run-date", default=RUN_DATE_DEFAULT)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


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


def fixed_v6_config(pehc: ModuleType) -> Any:
    config = pehc.PEHCConfig(
        arm_id="PEHC_294",
        expiry_days=8,
        slope_threshold=None,
        chase_cap_atr=math.inf,
        execution="next_utc_open",
        enabled=True,
        entry_enabled=True,
        blocked_origin_indices=(),
        allowed_origin_indices=(),
    )
    digest = pehc.config_sha256(config)
    if digest != V6_CONFIG_SHA256:
        raise RuntimeError(f"V6 config hash drift: {digest}")
    return config


def run_v6(
    pehc: ModuleType,
    context: TransferContext,
    config: Any,
    *,
    start: int,
    end: int,
    retain: bool = False,
    slippage: float = 0.0004,
    signal_lag: int = 0,
    include_funding: bool = True,
) -> Any:
    return pehc.run_variant(
        context,
        config,
        start_index=start,
        terminal_index=end,
        slippage=slippage,
        signal_lag=signal_lag,
        include_funding=include_funding,
        retain=retain,
    )


def metrics(result: Any) -> dict[str, Any]:
    return dict(result.raw.metrics)


def summarize_handoff(events: list[dict[str, Any]]) -> dict[str, int]:
    names = [
        "shadow_start",
        "shadow_expire",
        "shadow_cancel_native_exit",
        "shadow_protective_stop",
        "handoff_opportunity",
        "handoff_delay_scheduled",
        "handoff_accept",
        "handoff_reject_filter",
        "handoff_reject_actual_nonflat",
        "handoff_reject_no_short_config",
    ]
    return {name: sum(row.get("event") == name for row in events) for name in names}


def window_book(xfer: ModuleType, book: Any, start: int, end: int) -> Any:
    return xfer._window_book(book, start, end)


def window_features(xfer: ModuleType, features: Any, start: int, end: int) -> Any:
    return xfer._window_features(features, start, end)


def buy_and_hold(
    xfer: ModuleType,
    context: TransferContext,
    *,
    start: int,
    end: int,
) -> dict[str, Any]:
    return context.engine.buy_and_hold(
        window_book(xfer, context.book, start, end),
        window_features(xfer, context.features, start, end),
    )


def window_audit(
    xfer: ModuleType,
    pehc: ModuleType,
    context: TransferContext,
    config: Any,
    *,
    start: int,
    end: int,
    retain: bool,
) -> dict[str, Any]:
    base = run_v6(pehc, context, config, start=start, end=end, retain=retain)
    stress = run_v6(
        pehc,
        context,
        config,
        start=start,
        end=end,
        slippage=context.engine.STRESS_SLIPPAGE,
    )
    delayed = run_v6(
        pehc,
        context,
        config,
        start=start,
        end=end,
        signal_lag=1,
    )
    no_funding = run_v6(
        pehc,
        context,
        config,
        start=start,
        end=end,
        include_funding=False,
    )
    benchmark = buy_and_hold(xfer, context, start=start, end=end)
    return {
        "base": metrics(base),
        "stress_8bps": metrics(stress),
        "one_day_extra_delay": metrics(delayed),
        "funding_off": metrics(no_funding),
        "buy_and_hold": benchmark,
        "excess_return_pct": metrics(base)["net_return_pct"]
        - benchmark["net_return_pct"],
        "activation_counts": dict(base.activation_counts),
        "handoff_event_counts": summarize_handoff(base.handoff_events),
        "recent_slices": context.engine.recent_slices(base.raw) if retain else [],
        "_result": base,
    }


def rolling_rows(
    pehc: ModuleType,
    symbol: str,
    context: TransferContext,
    config: Any,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    while start + 180 <= context.book.count:
        end = start + 180
        result = run_v6(pehc, context, config, start=start, end=end)
        rows.append(
            {
                "symbol": symbol,
                "window_index": start // 60,
                **metrics(result),
                "handoff_accept": int(
                    summarize_handoff(result.handoff_events)["handoff_accept"]
                ),
            }
        )
        start += 60
    return rows


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: clean_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(item) for item in value]
    if isinstance(value, np.generic):
        return clean_json(value.item())
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def main() -> None:
    args = parse_args()
    xfer = load_module(XFER_PATH, "binance_ma7_st_xfer_v6_data")
    pehc = load_module(PEHC_ENGINE_PATH, "hype_ma7_abt_v6_pehc_transfer")
    adapter = load_module(ADAPTER_PATH, "hype_ma7_abt_v6_adapter_transfer")
    config = fixed_v6_config(pehc)
    if args.self_test:
        template = adapter.load_context()
        assert template.long_config.side == 1
        assert template.short_config.side == -1
        assert pehc.config_sha256(config) == V6_CONFIG_SHA256
        print("self-test: PASS")
        return

    template = adapter.load_context()
    payload: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "Binance-1D-MA7-Separated-Trend-Transfer",
        "diagnostic": "HYPE-1D-MA7-ABT-V6 zero-tuning BTC/ETH transfer",
        "status": "explore / diagnostic-only / not promoted / not live-ready",
        "selection": (
            "zero target-asset tuning; exact registered HYPE-1D-MA7-ABT-V6 "
            "PEHC_294 with inherited V5/OAPP and V4 MA_ONLY state machine"
        ),
        "source": {
            "v6_config_sha256": V6_CONFIG_SHA256,
            "pehc_engine": str(PEHC_ENGINE_PATH.relative_to(ROOT)),
            "pehc_engine_sha256": sha256(PEHC_ENGINE_PATH),
            "v4_adapter": str(ADAPTER_PATH.relative_to(ROOT)),
            "v4_adapter_sha256": sha256(ADAPTER_PATH),
            "data_adapter": str(XFER_PATH.relative_to(ROOT)),
            "data_adapter_sha256": sha256(XFER_PATH),
            "template_pins": dict(template.pins),
        },
        "costs": {
            "fee_per_fill": template.engine.FEE,
            "base_slippage_per_fill": template.engine.BASE_SLIPPAGE,
            "stress_slippage_per_fill": template.engine.STRESS_SLIPPAGE,
            "funding": (
                "actual Binance event timestamps/rates loaded by the existing "
                "BTC/ETH transfer adapter; charged only while held"
            ),
        },
        "assets": {},
    }
    metric_rows: list[dict[str, Any]] = []
    recent_rows: list[dict[str, Any]] = []
    phase_rows: list[dict[str, Any]] = []
    rolling: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    path_rows: list[dict[str, Any]] = []

    for symbol, slug in ASSETS.items():
        hourly, funding, quality = xfer.load_and_audit(symbol, slug)
        books = {
            phase: xfer.build_book(symbol, hourly, quality, phase_hours=phase)
            for phase in (0, 12)
        }
        features = {
            phase: template.engine.build_features(book, hourly, funding)
            for phase, book in books.items()
        }
        contexts = {
            phase: TransferContext(template, books[phase], features[phase])
            for phase in books
        }
        context = contexts[0]
        common_start = int(context.book.ts.searchsorted(COMMON_START, side="left"))
        if (
            common_start >= context.book.count
            or pd.Timestamp(context.book.ts[common_start]) != COMMON_START
        ):
            raise RuntimeError(f"{symbol}: common start unavailable")
        windows = {
            "full": (0, context.book.count),
            "hype_common": (common_start, context.book.count),
        }
        asset_payload: dict[str, Any] = {
            "slug": slug,
            "quality": quality,
            "books": {str(phase): book.quality for phase, book in books.items()},
            "windows": {},
            "phase_12h_full": {},
        }
        for label, (start, end) in windows.items():
            audit = window_audit(
                xfer,
                pehc,
                context,
                config,
                start=start,
                end=end,
                retain=True,
            )
            result = audit.pop("_result")
            asset_payload["windows"][label] = audit
            for key in ("base", "stress_8bps", "one_day_extra_delay", "funding_off"):
                metric_rows.append(
                    {
                        "symbol": symbol,
                        "window": label,
                        "variant": key,
                        **audit[key],
                    }
                )
            metric_rows.append(
                {
                    "symbol": symbol,
                    "window": label,
                    "variant": "buy_and_hold",
                    **audit["buy_and_hold"],
                }
            )
            for row in audit["recent_slices"]:
                recent_rows.append({"symbol": symbol, "window": label, **row})
            if label == "full":
                for trade in result.raw.trades:
                    trade_rows.append({"symbol": symbol, **trade})
                for row in result.raw.path:
                    path_rows.append({"symbol": symbol, **row})
        phase_context = contexts[12]
        phase_result = run_v6(
            pehc,
            phase_context,
            config,
            start=0,
            end=phase_context.book.count,
        )
        phase_bh = buy_and_hold(
            xfer,
            phase_context,
            start=0,
            end=phase_context.book.count,
        )
        asset_payload["phase_12h_full"] = {
            "base": metrics(phase_result),
            "buy_and_hold": phase_bh,
            "excess_return_pct": metrics(phase_result)["net_return_pct"]
            - phase_bh["net_return_pct"],
            "handoff_event_counts": summarize_handoff(phase_result.handoff_events),
        }
        phase_rows.append(
            {
                "symbol": symbol,
                "phase_hours": 0,
                **asset_payload["windows"]["full"]["base"],
            }
        )
        phase_rows.append(
            {
                "symbol": symbol,
                "phase_hours": 12,
                **asset_payload["phase_12h_full"]["base"],
            }
        )
        rolling.extend(rolling_rows(pehc, symbol, context, config))
        payload["assets"][symbol] = asset_payload

    stem = f"binance_1d_ma7_abt_v6_transfer_btc_eth_{args.run_date}"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACT_DIR / f"{stem}.json").write_text(
        json.dumps(clean_json(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    pd.DataFrame(metric_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_metrics.csv",
        index=False,
    )
    pd.DataFrame(recent_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_recent.csv",
        index=False,
    )
    pd.DataFrame(phase_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_phase.csv",
        index=False,
    )
    pd.DataFrame(rolling).to_csv(
        ARTIFACT_DIR / f"{stem}_rolling_180d.csv",
        index=False,
    )
    pd.DataFrame(trade_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_trades.csv",
        index=False,
    )
    pd.DataFrame(path_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_path.csv",
        index=False,
    )
    print(json.dumps(clean_json(payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
