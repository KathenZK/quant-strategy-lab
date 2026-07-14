from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import random
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/sol/1h-volatility-compression-breakout"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DIAGNOSTIC_DIR = FAMILY_DIR / "diagnostics"
ENGINE_PATH = (
    ROOT / "research/_shared-kernels/1h-adaptive-regime-search/v2/engine.py"
)
ENGINE_SHA256 = "70c22ea97a7c1c678f677e4c87ac5468d2bb233144e3e2545f02b26c7e959c38"
DATA_PATH = ARTIFACT_DIR / "sol_binance_1h_closed_klines_2y.parquet"
QUALITY_PATH = ARTIFACT_DIR / "sol_binance_1h_data_quality_2y.json"
FUNDING_PATH = (
    ROOT
    / "data/normalized/funding/exchange=binance/market_type=perp"
    / "symbol=sol_usdt_usdt/funding.parquet"
)

DATE_TAG = "2026-07-13"
SUMMARY_JSON = ARTIFACT_DIR / f"sol_1h_vcb_search_{DATE_TAG}.json"
RANKING_CSV = ARTIFACT_DIR / f"sol_1h_vcb_search_ranking_{DATE_TAG}.csv"
SLICES_CSV = ARTIFACT_DIR / f"sol_1h_vcb_search_slices_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"sol_1h_vcb_search_selected_trades_{DATE_TAG}.csv"
REPORT_MD = DIAGNOSTIC_DIR / f"sol-1h-vcb-search-{DATE_TAG}.md"

TRAIN_START = pd.Timestamp("2024-08-27T07:00:00Z")
TRAIN_END = pd.Timestamp("2025-09-10T20:06:00Z")
PREFIT_END = pd.Timestamp("2026-04-03T05:00:00Z")
REUSED_HOLDOUT_END = pd.Timestamp("2026-07-03T05:00:00Z")
FULL_END = pd.Timestamp("2026-07-13T07:00:00Z")

TARGET_ANNUAL_MULTIPLE = 10.0
TARGET_WIN_RATE = 0.80
TARGET_MAX_DD = -0.20

STANDARD_SLICES = (
    ("last_1d", pd.Timedelta(days=1)),
    ("last_7d", pd.Timedelta(days=7)),
    ("last_1m", pd.Timedelta(days=30)),
    ("last_3m", pd.Timedelta(days=91)),
    ("last_6m", pd.Timedelta(days=182)),
    ("last_1y", pd.Timedelta(days=365)),
)


@dataclass(frozen=True, slots=True)
class EntryConfig:
    compression_bars: int
    box_window: int
    confirm_window: int
    width_z_max: float
    atr_ratio_max: float
    min_rvol: float
    close_location: float
    regime_mode: str
    side_mode: str
    max_aligned_funding_bps: float


@dataclass(slots=True)
class Candidate:
    name: str
    entry: EntryConfig
    exit_config: Any
    trades: list[Any]
    score: float
    metrics: dict[str, dict[str, float]]
    signal_count: int
    event_count: int
    prefit_pass: bool


def load_engine() -> Any:
    actual_hash = hashlib.sha256(ENGINE_PATH.read_bytes()).hexdigest()
    if actual_hash != ENGINE_SHA256:
        raise RuntimeError(
            f"Search engine drift: expected {ENGINE_SHA256}, got {actual_hash}"
        )
    spec = importlib.util.spec_from_file_location("sol_1h_vcb_engine", ENGINE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load engine: {ENGINE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SOLUSDT 1h volatility-compression breakout search."
    )
    parser.add_argument("--entry-configs", type=int, default=800)
    parser.add_argument("--exits-per-entry", type=int, default=12)
    parser.add_argument("--keep", type=int, default=500)
    parser.add_argument("--seed", type=int, default=20260713)
    parser.add_argument("--progress-every", type=int, default=100)
    return parser.parse_args()


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    if not DATA_PATH.exists() or not QUALITY_PATH.exists() or not FUNDING_PATH.exists():
        raise FileNotFoundError(
            "Run scripts/fetch_sol_1h_vcb_data.py before the search."
        )
    frame = pd.read_parquet(DATA_PATH)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = (
        frame.drop_duplicates("ts", keep="last")
        .sort_values("ts")
        .reset_index(drop=True)
    )
    quality = json.loads(QUALITY_PATH.read_text(encoding="utf-8"))
    audit = quality["data_quality"]
    blockers = (
        int(audit["missing_bars"])
        + int(audit["duplicate_normalized"])
        + sum(int(value) for value in audit["critical_nulls"].values())
        + sum(int(value) for value in audit["ohlcv_violations"].values())
        + sum(int(value) for value in audit["raw_normalized_mismatch"].values())
    )
    if blockers:
        raise RuntimeError(f"Data-quality blockers: {blockers}")
    if frame["ts"].iloc[-1] + pd.Timedelta(hours=1) != FULL_END:
        raise RuntimeError(
            f"Unexpected dataset end: {frame['ts'].iloc[-1]} vs {FULL_END}"
        )
    funding = pd.read_parquet(FUNDING_PATH)
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    funding = (
        funding.drop_duplicates("ts", keep="last")
        .sort_values("ts")
        .reset_index(drop=True)
    )
    if funding.empty or funding["funding_rate"].isna().any():
        raise RuntimeError("Funding history missing or contains nulls")
    return frame, funding, quality


def random_entry_config(rng: random.Random) -> EntryConfig:
    return EntryConfig(
        compression_bars=rng.choice((3, 6, 12, 24)),
        box_window=rng.choice((12, 24, 48, 72)),
        confirm_window=rng.choice((6, 12, 24, 48)),
        width_z_max=rng.choice((-1.5, -1.0, -0.5, 0.0)),
        atr_ratio_max=rng.choice((0.70, 0.85, 1.00, 1.15)),
        min_rvol=rng.choice((0.5, 1.0, 1.5, 2.0)),
        close_location=rng.choice((0.60, 0.70, 0.80)),
        regime_mode=rng.choice(("none", "h4", "h12")),
        side_mode=rng.choice(("both", "long", "short")),
        max_aligned_funding_bps=rng.choice((1.0, 2.0, 10_000.0)),
    )


def random_exit_config(
    engine: Any, rng: random.Random, template: Any, index: int
) -> Any:
    exit_kind = rng.choices(("trailing", "fixed"), weights=(0.72, 0.28), k=1)[0]
    sizing_kind = rng.choices(("risk", "fixed"), weights=(0.75, 0.25), k=1)[0]
    return replace(
        template,
        name=f"SOL_1H_VCB_R{index:06d}",
        style="volatility_compression_breakout",
        side_mode="both",
        exit_kind=exit_kind,
        tp_atr=rng.choice((1.5, 2.0, 3.0, 4.0, 6.0)),
        sl_atr=rng.choice((1.0, 1.5, 2.0, 2.5, 3.0)),
        trail_activation_atr=rng.choice((0.75, 1.0, 1.5, 2.0)),
        trail_atr=rng.choice((0.75, 1.0, 1.5, 2.0)),
        max_hold_bars=rng.choice((24, 48, 72, 120, 168)),
        cooldown_bars=rng.choice((0, 6, 12, 24)),
        entry_delay_bars=1,
        sizing_kind=sizing_kind,
        fixed_leverage=rng.choice((1.0, 1.5, 2.0)),
        risk_fraction=rng.choice((0.003, 0.005, 0.0075, 0.01)),
        max_leverage=rng.choice((1.0, 1.5, 2.0, 3.0)),
    )


def consecutive_true(mask: np.ndarray, bars: int) -> np.ndarray:
    values = pd.Series(mask.astype("int8")).rolling(bars).sum().to_numpy()
    return values >= bars


def build_signal(
    engine: Any, frame: pd.DataFrame, cfg: EntryConfig
) -> tuple[np.ndarray, int]:
    close = frame["close"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    width_z = frame["bb_width_z48"].to_numpy("float64")
    atr_ratio = frame["atr_ratio"].to_numpy("float64")
    rvol = frame["rvol48"].to_numpy("float64")
    close_pos = frame["close_pos"].to_numpy("float64")
    funding = frame["last_funding_rate"].to_numpy("float64") * 10_000.0
    compression = (
        np.isfinite(width_z)
        & np.isfinite(atr_ratio)
        & (width_z <= cfg.width_z_max)
        & (atr_ratio <= cfg.atr_ratio_max)
    )
    armed = consecutive_true(compression, cfg.compression_bars)
    box_high_series = (
        pd.Series(high)
        .rolling(cfg.box_window, min_periods=cfg.box_window)
        .max()
        .to_numpy()
    )
    box_low_series = (
        pd.Series(low)
        .rolling(cfg.box_window, min_periods=cfg.box_window)
        .min()
        .to_numpy()
    )
    signal = np.zeros(len(frame), dtype=np.int8)
    active = False
    expires_at = -1
    box_high = math.nan
    box_low = math.nan
    event_count = 0

    for bar_i in range(1, len(frame)):
        if armed[bar_i]:
            active = True
            expires_at = bar_i + cfg.confirm_window
            box_high = float(box_high_series[bar_i])
            box_low = float(box_low_series[bar_i])
            event_count += 1
            continue
        if not active:
            continue
        if bar_i > expires_at:
            active = False
            continue
        if not (
            np.isfinite(box_high)
            and np.isfinite(box_low)
            and np.isfinite(rvol[bar_i])
            and rvol[bar_i] >= cfg.min_rvol
        ):
            continue
        long_break = (
            cfg.side_mode in {"long", "both"}
            and close[bar_i] > box_high
            and close[bar_i - 1] <= box_high
            and close_pos[bar_i] >= cfg.close_location
        )
        short_break = (
            cfg.side_mode in {"short", "both"}
            and close[bar_i] < box_low
            and close[bar_i - 1] >= box_low
            and close_pos[bar_i] <= 1.0 - cfg.close_location
        )
        side = 1 if long_break else -1 if short_break else 0
        if side == 0:
            continue
        if cfg.regime_mode != "none":
            spread = float(frame[f"{cfg.regime_mode}_spread"].iloc[bar_i])
            if not np.isfinite(spread) or side * spread < 0.0:
                continue
        if side * funding[bar_i] > cfg.max_aligned_funding_bps:
            continue
        signal[bar_i] = side
        active = False
    return signal, event_count


def window_metrics(engine: Any, trades: list[Any]) -> dict[str, dict[str, float]]:
    return {
        "train": engine.metrics(trades, TRAIN_START, TRAIN_END),
        "validation": engine.metrics(trades, TRAIN_END, PREFIT_END),
        "prefit": engine.metrics(trades, TRAIN_START, PREFIT_END),
        "reused_holdout": engine.metrics(
            trades, PREFIT_END, REUSED_HOLDOUT_END
        ),
        "fresh_forward": engine.metrics(
            trades, REUSED_HOLDOUT_END, FULL_END
        ),
        "current_full": engine.metrics(trades, TRAIN_START, FULL_END),
    }


def tail_metrics(trades: list[Any]) -> dict[str, float]:
    selected = [
        trade for trade in trades if TRAIN_START <= trade.entry_ts < PREFIT_END
    ]
    if not selected:
        return {
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "payoff": 0.0,
            "max_loss": 0.0,
        }
    returns = np.array([trade.equity_ret for trade in selected])
    wins = returns[returns > 0.0]
    losses = returns[returns <= 0.0]
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = float(losses.mean()) if len(losses) else 0.0
    return {
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "payoff": avg_win / abs(avg_loss) if avg_loss < 0.0 else math.inf,
        "max_loss": float(returns.min()),
    }


def score_candidate(
    engine: Any, trades: list[Any]
) -> tuple[float, dict[str, dict[str, float]], bool]:
    metrics = window_metrics(engine, trades)
    train = metrics["train"]
    validation = metrics["validation"]
    prefit = metrics["prefit"]
    if (
        train["trades"] < 15
        or validation["trades"] < 8
        or prefit["trades"] < 30
        or train["total_return"] <= 0.0
        or validation["total_return"] <= 0.0
        or min(train["max_dd"], validation["max_dd"], prefit["max_dd"])
        <= TARGET_MAX_DD
    ):
        return -1e9, metrics, False
    tails = tail_metrics(trades)
    min_ann = min(train["annual_multiple"], validation["annual_multiple"])
    score = (
        1.0 * math.log(max(prefit["annual_multiple"], 1e-9))
        + 1.3 * math.log(max(min_ann, 1e-9))
        + 0.25 * min(prefit["profit_factor"], 5.0)
        + 0.25 * min(tails["payoff"], 3.0)
        + 0.15 * min(prefit["trades"] / 50.0, 2.0)
        - 7.0 * max(0.0, -0.08 - tails["max_loss"])
    )
    hard_pass = bool(
        prefit["annual_multiple"] >= TARGET_ANNUAL_MULTIPLE
        and prefit["win_rate"] >= TARGET_WIN_RATE
        and prefit["max_dd"] > TARGET_MAX_DD
        and validation["annual_multiple"] > 1.0
        and validation["win_rate"] >= TARGET_WIN_RATE
        and validation["max_dd"] > TARGET_MAX_DD
    )
    if hard_pass:
        score += 10.0
    return float(score), metrics, hard_pass


def retain(
    retained: list[Candidate], candidate: Candidate, keep: int
) -> list[Candidate]:
    retained.append(candidate)
    if len(retained) > keep * 3:
        retained = sorted(
            retained,
            key=lambda item: (item.prefit_pass, item.score),
            reverse=True,
        )[:keep]
    return retained


def candidate_row(candidate: Candidate) -> dict[str, Any]:
    row: dict[str, Any] = {
        "name": candidate.name,
        "score": candidate.score,
        "signal_count": candidate.signal_count,
        "event_count": candidate.event_count,
        "prefit_pass": candidate.prefit_pass,
        **{f"entry_{key}": value for key, value in asdict(candidate.entry).items()},
        **{
            f"exit_{key}": value
            for key, value in asdict(candidate.exit_config).items()
        },
        **{f"tail_{key}": value for key, value in tail_metrics(candidate.trades).items()},
    }
    for window, metric in candidate.metrics.items():
        row.update({f"{window}_{key}": value for key, value in metric.items()})
    return row


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, float):
        return None if not math.isfinite(value) else value
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def pct(value: float) -> str:
    return "inf" if not np.isfinite(value) else f"{value:.2%}"


def mult(value: float) -> str:
    return "inf" if not np.isfinite(value) else f"{value:.4f}x"


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)
    engine = load_engine()
    frame, funding, quality = load_data()
    frame = engine.add_features(frame, funding)
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    template = engine.curated_configs()[0]

    entries: list[EntryConfig] = []
    seen_entries: set[EntryConfig] = set()
    while len(entries) < args.entry_configs:
        entry = random_entry_config(rng)
        if entry not in seen_entries:
            seen_entries.add(entry)
            entries.append(entry)

    retained: list[Candidate] = []
    generated = 0
    eligible = 0
    hard_passes = 0
    signal_cache: dict[EntryConfig, tuple[np.ndarray, int]] = {}
    for entry_index, entry in enumerate(entries, start=1):
        signal, event_count = build_signal(engine, frame, entry)
        signal_cache[entry] = (signal, event_count)
        signal_count = int(np.count_nonzero(signal))
        if signal_count < 20:
            continue
        for _ in range(args.exits_per_entry):
            generated += 1
            exit_cfg = random_exit_config(engine, rng, template, generated)
            trades = engine.simulate_trades(
                frame,
                signal,
                exit_cfg,
                funding_times,
                funding_cumulative,
            )
            score, metrics, hard_pass = score_candidate(engine, trades)
            if score <= -1e8:
                continue
            eligible += 1
            hard_passes += int(hard_pass)
            candidate = Candidate(
                exit_cfg.name,
                entry,
                exit_cfg,
                trades,
                score,
                metrics,
                signal_count,
                event_count,
                hard_pass,
            )
            retained = retain(retained, candidate, args.keep)
        if entry_index % args.progress_every == 0:
            best = (
                max(retained, key=lambda item: (item.prefit_pass, item.score))
                if retained
                else None
            )
            print(
                f"entries={entry_index}/{len(entries)} generated={generated} "
                f"eligible={eligible} hard_pass={hard_passes} "
                f"best={best.name if best else 'none'} "
                f"score={best.score if best else float('nan'):.3f}",
                flush=True,
            )
    retained = sorted(
        retained,
        key=lambda item: (item.prefit_pass, item.score),
        reverse=True,
    )[: args.keep]
    if not retained:
        raise RuntimeError("No VCB candidates survived prefit gates")
    selected = retained[0]
    pd.DataFrame([candidate_row(item) for item in retained]).to_csv(
        RANKING_CSV, index=False
    )
    slices = [
        {
            "window": name,
            **engine.metrics(selected.trades, FULL_END - delta, FULL_END),
        }
        for name, delta in STANDARD_SLICES
    ]
    pd.DataFrame(slices).to_csv(SLICES_CSV, index=False)
    pd.DataFrame(engine.trade_rows(selected.trades)).to_csv(TRADES_CSV, index=False)

    scenarios: list[dict[str, Any]] = []
    original_slippage = engine.SLIPPAGE_PER_FILL
    for name, delay, slippage in (
        ("base_k1_4bps", 1, 0.0004),
        ("delay_k2_4bps", 2, 0.0004),
        ("base_k1_8bps", 1, 0.0008),
    ):
        engine.SLIPPAGE_PER_FILL = slippage
        cfg = replace(selected.exit_config, entry_delay_bars=delay)
        trades = engine.simulate_trades(
            frame,
            signal_cache[selected.entry][0],
            cfg,
            funding_times,
            funding_cumulative,
        )
        scenarios.append(
            {
                "scenario": name,
                "metrics": window_metrics(engine, trades),
            }
        )
    engine.SLIPPAGE_PER_FILL = original_slippage

    payload = {
        "family": "SOL-1H-Volatility-Compression-Breakout",
        "family_id": "SOL-1H-VCB",
        "status": "explore_not_promoted_not_live_ready",
        "selection_policy": {
            "uses": "train_validation_prefit_only",
            "reused_holdout": "audit_after_freeze_not_used_for_selection",
            "fresh_forward": "2026-07-03_to_2026-07-13_observation_only",
        },
        "targets": {
            "annual_multiple": TARGET_ANNUAL_MULTIPLE,
            "win_rate": TARGET_WIN_RATE,
            "max_drawdown_strictly_greater_than": TARGET_MAX_DD,
        },
        "costs": {
            "fee_per_fill": engine.FEE_PER_FILL,
            "slippage_per_fill": original_slippage,
            "funding": "actual_binance_history_per_trade",
        },
        "data_quality": quality,
        "splits": {
            "train_start": TRAIN_START,
            "train_end": TRAIN_END,
            "prefit_end": PREFIT_END,
            "reused_holdout_end": REUSED_HOLDOUT_END,
            "full_end": FULL_END,
        },
        "counts": {
            "entry_configs": len(entries),
            "generated_candidates": generated,
            "eligible_candidates": eligible,
            "prefit_hard_pass_observations": hard_passes,
            "retained_candidates": len(retained),
        },
        "selected": candidate_row(selected),
        "top_20": [candidate_row(item) for item in retained[:20]],
        "slices": slices,
        "scenarios": scenarios,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.write_text(
        json.dumps(json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    metrics = selected.metrics
    tails = tail_metrics(selected.trades)
    lines = [
        "# SOL-1H-Volatility-Compression-Breakout 首轮搜索 - 2026-07-13",
        "",
        "## 结论",
        "",
        (
            "至少一个 prefit candidate 命中 `10x / 80% / <20% DD`；由于 reused holdout 已揭盲且 fresh forward 仅约 10 天，本轮仍不得 promotion。"
            if hard_passes
            else "没有 prefit candidate 命中 `10x / 80% / <20% DD`，本轮结论为 `explore / not promoted / not live-ready`。"
        ),
        "",
        f"- entry configs `{len(entries)}`；generated `{generated}`；eligible `{eligible}`；prefit hard pass `{hard_passes}`；retained `{len(retained)}`。",
        "- 机制：多 K 波动压缩 arm、冻结区间、有限窗口方向突破确认、下一根 open 入场、ATR fixed/trailing exit、fixed/risk sizing。",
        "",
        "## 数据质量",
        "",
        f"- Binance USD-M Futures `SOLUSDT` perpetual `1h`：`{quality['data_quality']['rows_closed_normalized']}` 根闭合 K。",
        f"- UTC：`{quality['data_quality']['first_ts']}` 至 `{quality['data_quality']['last_ts']}`。",
        f"- missing `{quality['data_quality']['missing_bars']}`，duplicate `{quality['data_quality']['duplicate_normalized']}`，blocker `{quality['data_quality']['blocker_count']}`。",
        "- fee `0.001`/fill，slippage `4 bps`/fill，逐笔计入真实 Binance funding。",
        "",
        "## 防泄漏切分",
        "",
        f"- train：`{TRAIN_START.isoformat()}` 至 `{TRAIN_END.isoformat()}`。",
        f"- validation：`{TRAIN_END.isoformat()}` 至 `{PREFIT_END.isoformat()}`。",
        f"- reused holdout：`{PREFIT_END.isoformat()}` 至 `{REUSED_HOLDOUT_END.isoformat()}`；已被旧 SOL 家族研究揭盲，只审计。",
        f"- fresh forward：`{REUSED_HOLDOUT_END.isoformat()}` 至 `{FULL_END.isoformat()}`；约 10 天，仅观察，不足以 promotion。",
        "",
        "## Prefit-only 选中观察",
        "",
        f"- id：`{selected.name}`；score `{selected.score:.3f}`；signals `{selected.signal_count}`；compression events `{selected.event_count}`。",
        f"- train：annual `{mult(metrics['train']['annual_multiple'])}`，DD `{pct(metrics['train']['max_dd'])}`，win `{pct(metrics['train']['win_rate'])}`，trades `{int(metrics['train']['trades'])}`。",
        f"- validation：annual `{mult(metrics['validation']['annual_multiple'])}`，DD `{pct(metrics['validation']['max_dd'])}`，win `{pct(metrics['validation']['win_rate'])}`，trades `{int(metrics['validation']['trades'])}`。",
        f"- prefit：annual `{mult(metrics['prefit']['annual_multiple'])}`，DD `{pct(metrics['prefit']['max_dd'])}`，win `{pct(metrics['prefit']['win_rate'])}`，trades `{int(metrics['prefit']['trades'])}`。",
        f"- reused holdout：annual `{mult(metrics['reused_holdout']['annual_multiple'])}`，return `{pct(metrics['reused_holdout']['total_return'])}`，DD `{pct(metrics['reused_holdout']['max_dd'])}`，win `{pct(metrics['reused_holdout']['win_rate'])}`，trades `{int(metrics['reused_holdout']['trades'])}`。",
        f"- fresh forward：return `{pct(metrics['fresh_forward']['total_return'])}`，DD `{pct(metrics['fresh_forward']['max_dd'])}`，win `{pct(metrics['fresh_forward']['win_rate'])}`，trades `{int(metrics['fresh_forward']['trades'])}`。",
        f"- current full：annual `{mult(metrics['current_full']['annual_multiple'])}`，DD `{pct(metrics['current_full']['max_dd'])}`，win `{pct(metrics['current_full']['win_rate'])}`，trades `{int(metrics['current_full']['trades'])}`。",
        f"- prefit payoff `{tails['payoff']:.3f}`，avg win `{pct(tails['avg_win'])}`，avg loss `{pct(tails['avg_loss'])}`，max trade loss `{pct(tails['max_loss'])}`。",
        "",
        "## 标准近期分片（锚定数据集末端，仅审计）",
        "",
        "| Window | Annual | Return | DD | Win | Trades | PF |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in slices:
        lines.append(
            f"| `{row['window']}` | `{mult(row['annual_multiple'])}` | "
            f"`{pct(row['total_return'])}` | `{pct(row['max_dd'])}` | "
            f"`{pct(row['win_rate'])}` | `{int(row['trades'])}` | "
            f"`{row['profit_factor']:.3f}` |"
        )
    lines.extend(
        [
            "",
            "## 延迟与成本",
            "",
            "| Scenario | Prefit ann | Prefit DD | Holdout ann | Fresh return | Full ann | Full DD |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for scenario in scenarios:
        item = scenario["metrics"]
        lines.append(
            f"| `{scenario['scenario']}` | "
            f"`{mult(item['prefit']['annual_multiple'])}` | "
            f"`{pct(item['prefit']['max_dd'])}` | "
            f"`{mult(item['reused_holdout']['annual_multiple'])}` | "
            f"`{pct(item['fresh_forward']['total_return'])}` | "
            f"`{mult(item['current_full']['annual_multiple'])}` | "
            f"`{pct(item['current_full']['max_dd'])}` |"
        )
    lines.extend(
        [
            "",
            "## 研究边界",
            "",
            "- 本 family 与 SOL-1H-Adaptive-Regime 独立，不继承其 V1/V2 版本号。",
            "- reused holdout 不参与选择；fresh forward 仅约 10 天，样本不足。",
            "- 首轮搜索只能形成 explore 结论，不登记版本，不进入 dry-run/live。",
            "",
            "## 机器证据",
            "",
            f"- `artifacts/{SUMMARY_JSON.name}`",
            f"- `artifacts/{RANKING_CSV.name}`",
            f"- `artifacts/{SLICES_CSV.name}`",
            f"- `artifacts/{TRADES_CSV.name}`",
            "",
            "复现：",
            "",
            "```bash",
            "uv run python research/sol/1h-volatility-compression-breakout/scripts/research_sol_1h_vcb_search.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(
        f"selected={selected.name} score={selected.score:.3f} "
        f"prefit_ann={metrics['prefit']['annual_multiple']:.4f} "
        f"holdout_ann={metrics['reused_holdout']['annual_multiple']:.4f} "
        f"fresh_return={metrics['fresh_forward']['total_return']:.4f} "
        f"full_ann={metrics['current_full']['annual_multiple']:.4f}",
        flush=True,
    )
    print(f"wrote {REPORT_MD}", flush=True)


if __name__ == "__main__":
    main()
