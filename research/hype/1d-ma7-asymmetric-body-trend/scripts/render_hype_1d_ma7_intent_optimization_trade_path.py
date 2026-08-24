"""Render an audited, self-contained HYPE 1D MA7 comparison trade path.

The renderer is deliberately data-only: callers must pass the retained candidate
and exact-V4 paths, trades, metrics, and the candidate state trace produced by
the same frozen run.  It never loads market data or reconstructs trades.  All
cross-object checks run before the output file is opened, so an inconsistent
bundle fails closed without leaving a partial HTML artifact.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from enum import Enum
import hashlib
import html
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence


DAY_MS = 86_400_000
SCHEMA_VERSION = 1
STRATEGY_KEYS = ("candidate", "exact_v4")
REQUIRED_PATH_FIELDS = (
    "ts",
    "open",
    "high",
    "low",
    "close",
    "ma7",
    "atr7",
    "rsi6",
    "slope_atr",
    "upper_band",
    "lower_band",
    "equity",
    "side",
    "armed_side",
    "terminal",
)
REQUIRED_TRADE_FIELDS = (
    "side",
    "entry_ts",
    "exit_ts",
    "entry_price",
    "exit_price",
    "net_return",
    "exit_reason",
)
REQUIRED_METRIC_FIELDS = (
    "equity_multiple",
    "net_return_pct",
    "max_drawdown_pct",
    "closed_trades",
    "long_trades",
    "short_trades",
)
REQUIRED_TRACE_FIELDS = (
    "index",
    "ts",
    "side",
    "armed_side",
    "armed_age",
    "armed_origin",
    "armed_overbought_qualified",
    "slope_loss_run",
    "short_rsi_run",
    "pending_reason",
    "relation",
    "slope_atr",
    "rsi6",
    "complete",
)


def _plain(value: Any, *, field: str) -> Any:
    """Convert common research values to strict JSON primitives."""

    if is_dataclass(value):
        return _plain(asdict(value), field=field)
    if isinstance(value, Enum):
        return _plain(value.value, field=field)
    if isinstance(value, Mapping):
        return {
            str(key): _plain(item, field=f"{field}.{key}")
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [
            _plain(item, field=f"{field}[{index}]")
            for index, item in enumerate(value)
        ]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return _iso_utc(value, field=field)
    if hasattr(value, "item") and callable(value.item):
        try:
            return _plain(value.item(), field=field)
        except (TypeError, ValueError):
            pass
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{field} must be finite, got {value!r}")
        return value
    raise TypeError(f"{field} is not JSON-compatible: {type(value).__name__}")


def _as_mapping(value: Any, *, field: str) -> dict[str, Any]:
    plain = _plain(value, field=field)
    if not isinstance(plain, dict):
        raise TypeError(f"{field} must be a mapping")
    return plain


def _require_fields(row: Mapping[str, Any], fields: Sequence[str], *, label: str) -> None:
    missing = sorted(set(fields) - set(row))
    if missing:
        raise ValueError(f"{label} is missing required fields: {missing}")


def _parse_utc(value: Any, *, field: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        text = value.strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError(f"{field} is not ISO-8601: {value!r}") from exc
    else:
        raise TypeError(f"{field} must be an ISO-8601 string or datetime")
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError(f"{field} must be explicitly UTC")
    return parsed.astimezone(UTC)


def _iso_utc(value: Any, *, field: str) -> str:
    return _parse_utc(value, field=field).isoformat().replace("+00:00", "Z")


def _timestamp_ms(value: Any, *, field: str) -> int:
    return round(_parse_utc(value, field=field).timestamp() * 1_000)


def _number(value: Any, *, field: str, allow_none: bool = False) -> float | None:
    if value is None and allow_none:
        return None
    if isinstance(value, bool):
        raise TypeError(f"{field} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{field} must be numeric") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


def _integer(value: Any, *, field: str, minimum: int | None = None) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{field} must be an integer")
    try:
        integer = int(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{field} must be an integer") from exc
    try:
        equal = float(value) == integer
    except (TypeError, ValueError):
        equal = False
    if not equal:
        raise ValueError(f"{field} must be an exact integer")
    if minimum is not None and integer < minimum:
        raise ValueError(f"{field} must be >= {minimum}")
    return integer


def _side(value: Any, *, field: str) -> int:
    side = _integer(value, field=field)
    if side not in {-1, 0, 1}:
        raise ValueError(f"{field} must be -1, 0, or 1")
    return side


def _close(left: float | None, right: float | None, *, tolerance: float = 1e-10) -> bool:
    if left is None or right is None:
        return left is right
    return math.isclose(left, right, rel_tol=tolerance, abs_tol=tolerance)


def _normalize_path(rows: Sequence[Mapping[str, Any]], *, label: str) -> list[dict[str, Any]]:
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)) or not rows:
        raise ValueError(f"{label} path must be a non-empty sequence")
    normalized: list[dict[str, Any]] = []
    previous_ms: int | None = None
    terminal_count = 0
    for index, raw in enumerate(rows):
        row = _as_mapping(raw, field=f"{label}_path[{index}]")
        _require_fields(row, REQUIRED_PATH_FIELDS, label=f"{label}_path[{index}]")
        ts = _iso_utc(row["ts"], field=f"{label}_path[{index}].ts")
        timestamp = _timestamp_ms(ts, field=f"{label}_path[{index}].ts")
        if previous_ms is not None and timestamp <= previous_ms:
            raise ValueError(f"{label} path timestamps must be strictly increasing")
        if previous_ms is not None and timestamp - previous_ms != DAY_MS:
            raise ValueError(f"{label} path must be a contiguous UTC daily sequence")
        previous_ms = timestamp
        terminal = row["terminal"]
        if not isinstance(terminal, bool):
            raise TypeError(f"{label}_path[{index}].terminal must be boolean")
        terminal_count += int(terminal)
        if terminal and index != len(rows) - 1:
            raise ValueError(f"{label} terminal row must be last")

        open_price = _number(row["open"], field=f"{label}_path[{index}].open")
        high = _number(row["high"], field=f"{label}_path[{index}].high")
        low = _number(row["low"], field=f"{label}_path[{index}].low")
        close = _number(row["close"], field=f"{label}_path[{index}].close")
        assert open_price is not None and high is not None and low is not None
        assert close is not None
        if min(open_price, high, low, close) <= 0.0:
            raise ValueError(f"{label}_path[{index}] OHLC must be positive")
        if low > min(open_price, close) or high < max(open_price, close) or low > high:
            raise ValueError(f"{label}_path[{index}] has invalid OHLC geometry")

        ma7 = _number(row["ma7"], field=f"{label}_path[{index}].ma7", allow_none=True)
        atr7 = _number(row["atr7"], field=f"{label}_path[{index}].atr7", allow_none=True)
        rsi6 = _number(row["rsi6"], field=f"{label}_path[{index}].rsi6", allow_none=True)
        slope = _number(
            row["slope_atr"],
            field=f"{label}_path[{index}].slope_atr",
            allow_none=True,
        )
        upper = _number(
            row["upper_band"],
            field=f"{label}_path[{index}].upper_band",
            allow_none=True,
        )
        lower = _number(
            row["lower_band"],
            field=f"{label}_path[{index}].lower_band",
            allow_none=True,
        )
        equity = _number(row["equity"], field=f"{label}_path[{index}].equity")
        assert equity is not None
        if equity < 0.0:
            raise ValueError(f"{label}_path[{index}].equity must be non-negative")
        if atr7 is not None and atr7 < 0.0:
            raise ValueError(f"{label}_path[{index}].atr7 must be non-negative")
        if rsi6 is not None and not 0.0 <= rsi6 <= 100.0:
            raise ValueError(f"{label}_path[{index}].rsi6 must be within [0, 100]")
        if (upper is None) != (lower is None):
            raise ValueError(f"{label}_path[{index}] must retain both ATR bands or neither")
        if upper is not None:
            if ma7 is None or lower is None or not lower <= ma7 <= upper:
                raise ValueError(f"{label}_path[{index}] ATR bands do not bracket SMA7")
        side = _side(row["side"], field=f"{label}_path[{index}].side")
        armed_side = _side(
            row["armed_side"], field=f"{label}_path[{index}].armed_side"
        )
        if terminal and (side != 0 or armed_side != 0):
            raise ValueError(f"{label} terminal path state must be flat and unarmed")
        normalized.append(
            {
                "t": timestamp,
                "ts": ts,
                "o": open_price,
                "h": high,
                "l": low,
                "c": close,
                "ma7": ma7,
                "atr7": atr7,
                "rsi6": rsi6,
                "slopeAtr": slope,
                "upperBand": upper,
                "lowerBand": lower,
                "equity": equity,
                "side": side,
                "armedSide": armed_side,
                "pendingReason": str(row.get("pending_reason") or "") or None,
                "terminal": terminal,
            }
        )
    if terminal_count != 1:
        raise ValueError(f"{label} path must contain exactly one terminal row")
    if len(normalized) < 2:
        raise ValueError(f"{label} path must contain history plus a terminal row")
    return normalized


def _normalize_exact_v4_path(
    rows: Sequence[Mapping[str, Any]],
    *,
    candidate_path: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], str]:
    """Normalize either canonical rows or the exact V4 legacy ledger schema.

    Exact registered V4 deliberately comes from a different, pinned engine. Its
    retained path stores only ledger state and no market columns. Market fields
    are copied from the already-validated, same-window candidate path after
    strict row-count/timestamp/terminal checks; strategy-specific slope, bands,
    and detailed state remain explicitly unavailable.
    """

    if not rows:
        raise ValueError("exact_v4 path must be non-empty")
    first = rows[0]
    if not isinstance(first, Mapping):
        raise TypeError("exact_v4 path rows must be mappings")
    if set(REQUIRED_PATH_FIELDS).issubset(first):
        return _normalize_path(rows, label="exact_v4"), "canonical"
    legacy_required = {
        "ts",
        "pre_action_equity",
        "post_action_equity",
        "close_equity",
        "favorable_equity",
        "adverse_equity",
        "position",
        "action",
    }
    if not legacy_required.issubset(first):
        missing = sorted(legacy_required - set(first))
        raise ValueError(f"exact_v4 legacy path is missing required fields: {missing}")
    if len(rows) != len(candidate_path):
        raise ValueError("candidate and exact V4 paths cover different row counts")
    adapted: list[dict[str, Any]] = []
    terminal_actions = 0
    for index, (raw, candidate) in enumerate(zip(rows, candidate_path)):
        if not isinstance(raw, Mapping):
            raise TypeError(f"exact_v4_path[{index}] must be a mapping")
        missing = sorted(legacy_required - set(raw))
        if missing:
            raise ValueError(f"exact_v4_path[{index}] is missing required fields: {missing}")
        ts = _iso_utc(raw["ts"], field=f"exact_v4_path[{index}].ts")
        if ts != candidate["ts"]:
            raise ValueError(f"candidate and exact V4 timestamp differs at row {index}")
        action = str(raw["action"])
        terminal = action.startswith("terminal")
        terminal_actions += int(terminal)
        if terminal != (index == len(rows) - 1):
            raise ValueError("exact V4 terminal action must occur exactly on the last row")
        ledger = {
            name: _number(raw[name], field=f"exact_v4_path[{index}].{name}")
            for name in (
                "pre_action_equity",
                "post_action_equity",
                "close_equity",
                "favorable_equity",
                "adverse_equity",
            )
        }
        adapted.append(
            {
                "ts": ts,
                "open": candidate["o"],
                "high": candidate["h"],
                "low": candidate["l"],
                "close": candidate["c"],
                "ma7": candidate["ma7"],
                "atr7": candidate["atr7"],
                "rsi6": candidate["rsi6"],
                "slope_atr": None,
                "upper_band": None,
                "lower_band": None,
                "equity": ledger["close_equity"],
                "side": raw["position"],
                "armed_side": 0,
                "pending_reason": "",
                "terminal": terminal,
                "source_action": action,
                **ledger,
            }
        )
    if terminal_actions != 1:
        raise ValueError("exact V4 path must retain exactly one terminal action")
    normalized = _normalize_path(adapted, label="exact_v4")
    for point, source in zip(normalized, adapted):
        point.update(
            {
                "sourceAction": source["source_action"],
                "preActionEquity": source["pre_action_equity"],
                "postActionEquity": source["post_action_equity"],
                "favorableEquity": source["favorable_equity"],
                "adverseEquity": source["adverse_equity"],
            }
        )
    return normalized, "exact_v4_legacy_ledger+shared_market_from_candidate"


def _normalize_trade(raw: Mapping[str, Any], *, label: str, index: int) -> dict[str, Any]:
    row = _as_mapping(raw, field=f"{label}_trades[{index}]")
    _require_fields(row, REQUIRED_TRADE_FIELDS, label=f"{label}_trades[{index}]")
    if label == "candidate":
        _require_fields(
            row,
            ("trade_id", "net_pnl", "entry_reason"),
            label=f"{label}_trades[{index}]",
        )
    supplied_id = row.get("trade_id")
    trade_id = (
        str(supplied_id).strip()
        if supplied_id not in (None, "")
        else f"EXACT-V4-{index + 1:03d}"
        if label == "exact_v4"
        else ""
    )
    if not trade_id:
        raise ValueError(f"{label}_trades[{index}].trade_id must be non-empty")
    side = str(row["side"]).strip().lower()
    if side not in {"long", "short"}:
        raise ValueError(f"{label}_trades[{index}].side must be long or short")
    entry_ts = _iso_utc(row["entry_ts"], field=f"{label}_trades[{index}].entry_ts")
    exit_ts = _iso_utc(row["exit_ts"], field=f"{label}_trades[{index}].exit_ts")
    entry_t = _timestamp_ms(entry_ts, field=f"{label}_trades[{index}].entry_ts")
    exit_t = _timestamp_ms(exit_ts, field=f"{label}_trades[{index}].exit_ts")
    if entry_t > exit_t:
        raise ValueError(f"{label} trade {trade_id} exits before it enters")
    entry = _number(row["entry_price"], field=f"{label}_trades[{index}].entry_price")
    exit_price = _number(row["exit_price"], field=f"{label}_trades[{index}].exit_price")
    net_return = _number(row["net_return"], field=f"{label}_trades[{index}].net_return")
    net_pnl = _number(
        row.get("net_pnl"),
        field=f"{label}_trades[{index}].net_pnl",
        allow_none=label == "exact_v4",
    )
    assert entry is not None and exit_price is not None
    assert net_return is not None
    if entry <= 0.0 or exit_price <= 0.0:
        raise ValueError(f"{label} trade {trade_id} prices must be positive")
    optional_returns: dict[str, float | None] = {}
    for source, target in (
        ("gross_return", "grossReturnPct"),
        ("mfe_return", "mfePct"),
        ("mae_return", "maePct"),
        ("giveback_return", "givebackPct"),
    ):
        value = _number(
            row.get(source),
            field=f"{label}_trades[{index}].{source}",
            allow_none=True,
        )
        optional_returns[target] = None if value is None else value * 100.0
    signal_ts = row.get("entry_signal_ts")
    return {
        "id": trade_id,
        "idSource": "retained" if supplied_id not in (None, "") else "renderer_sequence",
        "side": side,
        "entryT": entry_t,
        "exitT": exit_t,
        "entryTs": entry_ts,
        "exitTs": exit_ts,
        "signalTs": (
            None
            if signal_ts in (None, "")
            else _iso_utc(signal_ts, field=f"{label}_trades[{index}].entry_signal_ts")
        ),
        "entry": entry,
        "exit": exit_price,
        "entryReason": str(row.get("entry_reason") or "not_retained_by_exact_v4"),
        "entryReasonAvailable": row.get("entry_reason") not in (None, ""),
        "exitReason": str(row["exit_reason"]),
        "netReturnPct": net_return * 100.0,
        "netPnl": net_pnl,
        "durationDays": (exit_t - entry_t) / DAY_MS,
        **optional_returns,
        "link": {
            "entryT": entry_t,
            "entryPrice": entry,
            "exitT": exit_t,
            "exitPrice": exit_price,
            "renderable": True,
        },
    }


def _normalize_trades(
    rows: Sequence[Mapping[str, Any]], *, label: str
) -> list[dict[str, Any]]:
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise TypeError(f"{label} trades must be a sequence")
    trades = [
        _normalize_trade(row, label=label, index=index)
        for index, row in enumerate(rows)
    ]
    identifiers = [trade["id"] for trade in trades]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError(f"{label} trade IDs must be unique")
    for index, trade in enumerate(trades):
        if index and trade["entryT"] < trades[index - 1]["entryT"]:
            raise ValueError(f"{label} trades must be chronological")
        if index and trade["entryT"] < trades[index - 1]["exitT"]:
            raise ValueError(f"{label} trades overlap")
    return trades


def _normalize_metrics(raw: Mapping[str, Any], *, label: str) -> dict[str, Any]:
    row = _as_mapping(raw, field=f"{label}_metrics")
    _require_fields(row, REQUIRED_METRIC_FIELDS, label=f"{label}_metrics")
    output: dict[str, Any] = {}
    numeric_names = (
        "equity_multiple",
        "net_return_pct",
        "max_drawdown_pct",
        "sharpe",
        "profit_factor",
        "win_rate",
        "exposure_pct",
        "cost",
        "funding_payment",
    )
    for name in numeric_names:
        value = _number(
            row.get(name), field=f"{label}_metrics.{name}", allow_none=True
        )
        output[name] = value
    for name in ("closed_trades", "long_trades", "short_trades"):
        output[name] = _integer(
            row[name], field=f"{label}_metrics.{name}", minimum=0
        )
    output["label"] = str(row.get("label") or label)
    return output


def _validate_metrics(
    metrics: Mapping[str, Any],
    trades: Sequence[Mapping[str, Any]],
    path: Sequence[Mapping[str, Any]],
    *,
    label: str,
) -> None:
    long_count = sum(trade["side"] == "long" for trade in trades)
    short_count = len(trades) - long_count
    expected = (len(trades), long_count, short_count)
    actual = (
        metrics["closed_trades"],
        metrics["long_trades"],
        metrics["short_trades"],
    )
    if actual != expected:
        raise ValueError(f"{label} metric/trade counts differ: {actual} != {expected}")
    final_equity = float(path[-1]["equity"])
    if not _close(final_equity, metrics["equity_multiple"], tolerance=1e-9):
        raise ValueError(f"{label} terminal equity and metric equity differ")
    expected_return = (final_equity - 1.0) * 100.0
    if not _close(expected_return, metrics["net_return_pct"], tolerance=1e-8):
        raise ValueError(f"{label} equity and net-return metric differ")


def _validate_trade_transitions(
    path: Sequence[Mapping[str, Any]],
    trades: Sequence[Mapping[str, Any]],
    *,
    label: str,
) -> None:
    expected_entries: list[tuple[int, str, float]] = []
    expected_exits: list[tuple[int, str, float]] = []
    prior_side = 0
    for point in path:
        side = int(point["side"])
        if side != prior_side:
            price = float(point["o"])
            if prior_side:
                expected_exits.append(
                    (int(point["t"]), "long" if prior_side > 0 else "short", price)
                )
            if side:
                expected_entries.append(
                    (int(point["t"]), "long" if side > 0 else "short", price)
                )
        prior_side = side
    actual_entries = [
        (int(trade["entryT"]), str(trade["side"]), float(trade["entry"]))
        for trade in trades
    ]
    actual_exits = [
        (int(trade["exitT"]), str(trade["side"]), float(trade["exit"]))
        for trade in trades
    ]
    for name, expected, actual in (
        ("entries", expected_entries, actual_entries),
        ("exits", expected_exits, actual_exits),
    ):
        if len(expected) != len(actual):
            raise ValueError(
                f"{label} path/trade {name} count differs: {len(expected)} != {len(actual)}"
            )
        for index, (left, right) in enumerate(zip(expected, actual)):
            same_side = left[1] == right[1]
            if label == "exact_v4":
                same_time = left[0] <= right[0] < left[0] + DAY_MS
                same_price = (
                    True
                    if right[0] != left[0]
                    else _close(left[2], right[2], tolerance=1e-9)
                )
            else:
                same_time = left[0] == right[0]
                same_price = _close(left[2], right[2], tolerance=1e-9)
            if not (same_side and same_time and same_price):
                raise ValueError(
                    f"{label} path/trade {name}[{index}] differ: {left} != {right}"
                )


def _normalize_trace(raw: Mapping[str, Any]) -> dict[str, Any]:
    trace = _as_mapping(raw, field="state_trace")
    for field in ("rows", "events", "activation_counts", "terminal"):
        if field not in trace:
            raise ValueError(f"state_trace is missing required field: {field}")
    raw_rows = trace["rows"]
    if not isinstance(raw_rows, list) or not raw_rows:
        raise ValueError("state_trace.rows must be a non-empty list")
    rows: list[dict[str, Any]] = []
    previous_t: int | None = None
    for index, raw_row in enumerate(raw_rows):
        row = _as_mapping(raw_row, field=f"state_trace.rows[{index}]")
        _require_fields(row, REQUIRED_TRACE_FIELDS, label=f"state_trace.rows[{index}]")
        ts = _iso_utc(row["ts"], field=f"state_trace.rows[{index}].ts")
        timestamp = _timestamp_ms(ts, field=f"state_trace.rows[{index}].ts")
        if previous_t is not None and timestamp - previous_t != DAY_MS:
            raise ValueError("state_trace rows must be a contiguous UTC daily sequence")
        previous_t = timestamp
        side = _side(row["side"], field=f"state_trace.rows[{index}].side")
        armed_side = _side(
            row["armed_side"], field=f"state_trace.rows[{index}].armed_side"
        )
        armed_age = _integer(
            row["armed_age"], field=f"state_trace.rows[{index}].armed_age", minimum=0
        )
        slope_loss_run = _integer(
            row["slope_loss_run"],
            field=f"state_trace.rows[{index}].slope_loss_run",
            minimum=0,
        )
        short_rsi_run = _integer(
            row["short_rsi_run"],
            field=f"state_trace.rows[{index}].short_rsi_run",
            minimum=0,
        )
        qualified = row["armed_overbought_qualified"]
        complete = row["complete"]
        if not isinstance(qualified, bool) or not isinstance(complete, bool):
            raise TypeError("state trace qualified/complete flags must be boolean")
        origin = row["armed_origin"]
        if origin is not None:
            origin = str(origin).strip() or None
        if armed_side == 0 and (armed_age != 0 or origin is not None or qualified):
            raise ValueError("unarmed trace rows must clear age/origin/qualification")
        if armed_side != 0 and origin is None:
            raise ValueError("armed trace rows must retain their origin")
        relation = row["relation"]
        if relation is not None:
            relation = _side(relation, field=f"state_trace.rows[{index}].relation")
        slope = _number(
            row["slope_atr"],
            field=f"state_trace.rows[{index}].slope_atr",
            allow_none=True,
        )
        rsi = _number(
            row["rsi6"], field=f"state_trace.rows[{index}].rsi6", allow_none=True
        )
        if rsi is not None and not 0.0 <= rsi <= 100.0:
            raise ValueError("state_trace rsi6 must be within [0, 100]")
        rows.append(
            {
                "index": _integer(
                    row["index"], field=f"state_trace.rows[{index}].index", minimum=0
                ),
                "t": timestamp,
                "ts": ts,
                "side": side,
                "armedSide": armed_side,
                "armedAge": armed_age,
                "armedOrigin": origin,
                "armedOverboughtQualified": qualified,
                "slopeLossRun": slope_loss_run,
                "shortRsiRun": short_rsi_run,
                "pendingReason": str(row.get("pending_reason") or "") or None,
                "pendingFromSide": row.get("pending_from_side"),
                "pendingTargetSide": row.get("pending_target_side"),
                "pendingFills": row.get("pending_fills"),
                "openFillReason": str(row.get("open_fill_reason") or "") or None,
                "relation": relation,
                "slopeAtr": slope,
                "rsi6": rsi,
                "complete": complete,
            }
        )
    counts = _as_mapping(trace["activation_counts"], field="state_trace.activation_counts")
    counts = {
        str(key): _integer(value, field=f"state_trace.activation_counts.{key}", minimum=0)
        for key, value in counts.items()
    }
    events = _plain(trace["events"], field="state_trace.events")
    if not isinstance(events, list) or not all(isinstance(event, dict) for event in events):
        raise TypeError("state_trace.events must be a list of mappings")
    for index, event in enumerate(events):
        if "ts" not in event or "event" not in event:
            raise ValueError(f"state_trace.events[{index}] is incomplete")
        event["ts"] = _iso_utc(event["ts"], field=f"state_trace.events[{index}].ts")
    terminal = _as_mapping(trace["terminal"], field="state_trace.terminal")
    for field in ("ts", "open", "state_before", "state_after"):
        if field not in terminal:
            raise ValueError(f"state_trace.terminal is missing {field}")
    terminal["ts"] = _iso_utc(terminal["ts"], field="state_trace.terminal.ts")
    terminal["open"] = _number(terminal["open"], field="state_trace.terminal.open")
    return {
        "startIndex": _integer(trace.get("start_index", 0), field="state_trace.start_index", minimum=0),
        "activeStart": _integer(trace.get("active_start", 0), field="state_trace.active_start", minimum=0),
        "terminalIndex": _integer(
            trace.get("terminal_index", len(rows)),
            field="state_trace.terminal_index",
            minimum=1,
        ),
        "rows": rows,
        "events": events,
        "activationCounts": counts,
        "terminal": terminal,
    }


def _merge_candidate_trace(
    candidate_path: list[dict[str, Any]], trace: dict[str, Any]
) -> None:
    daily = candidate_path[:-1]
    rows = trace["rows"]
    if len(daily) != len(rows):
        raise ValueError(
            f"candidate path/state-trace row count differs: {len(daily)} != {len(rows)}"
        )
    for index, (point, state) in enumerate(zip(daily, rows)):
        if point["t"] != state["t"]:
            raise ValueError(f"candidate path/state-trace timestamp differs at row {index}")
        for field in ("side", "armedSide"):
            if point[field] != state[field]:
                raise ValueError(f"candidate path/state-trace {field} differs at row {index}")
        for field in ("slopeAtr", "rsi6"):
            if not _close(point[field], state[field], tolerance=1e-10):
                raise ValueError(f"candidate path/state-trace {field} differs at row {index}")
        path_pending = point["pendingReason"] or None
        trace_pending = state["pendingReason"] or None
        if path_pending != trace_pending:
            raise ValueError(
                f"candidate path/state-trace pending reason differs at row {index}"
            )
        point.update(
            {
                "armedAge": state["armedAge"],
                "armedOrigin": state["armedOrigin"],
                "armedOverboughtQualified": state[
                    "armedOverboughtQualified"
                ],
                "slopeLossRun": state["slopeLossRun"],
                "shortRsiRun": state["shortRsiRun"],
                "relation": state["relation"],
                "openFillReason": state["openFillReason"],
            }
        )
    terminal = candidate_path[-1]
    if terminal["ts"] != trace["terminal"]["ts"] or not _close(
        terminal["o"], trace["terminal"]["open"], tolerance=1e-10
    ):
        raise ValueError("candidate path/state-trace terminal boundary differs")
    state_after = trace["terminal"].get("state_after")
    if not isinstance(state_after, dict):
        raise TypeError("state_trace.terminal.state_after must be a mapping")
    if int(state_after.get("side", 99)) != 0 or int(state_after.get("armed_side", 99)) != 0:
        raise ValueError("state trace must finish flat and unarmed")
    terminal.update(
        {
            "armedAge": 0,
            "armedOrigin": None,
            "armedOverboughtQualified": False,
            "slopeLossRun": 0,
            "shortRsiRun": 0,
            "relation": None,
            "openFillReason": "terminal_flatten",
        }
    )


def _decorate_v4_path(path: list[dict[str, Any]]) -> None:
    """Make unavailable exact-V4 state counters explicit rather than inferred."""

    for point in path:
        point.update(
            {
                "armedAge": None,
                "armedOrigin": None,
                "armedOverboughtQualified": None,
                "slopeLossRun": None,
                "shortRsiRun": None,
                "relation": (
                    None
                    if point["ma7"] is None
                    else 1
                    if point["c"] > point["ma7"]
                    else -1
                    if point["c"] < point["ma7"]
                    else 0
                ),
                "openFillReason": None,
            }
        )


def _validate_shared_market(
    candidate: Sequence[Mapping[str, Any]], v4: Sequence[Mapping[str, Any]]
) -> None:
    if len(candidate) != len(v4):
        raise ValueError("candidate and exact V4 paths cover different row counts")
    shared_fields = ("t", "o", "h", "l", "c", "ma7", "atr7", "rsi6", "terminal")
    for index, (left, right) in enumerate(zip(candidate, v4)):
        for field in shared_fields:
            if field in {"t", "terminal"}:
                equal = left[field] == right[field]
            else:
                equal = _close(left[field], right[field], tolerance=1e-10)
            if not equal:
                raise ValueError(
                    f"candidate and exact V4 market field {field} differs at row {index}"
                )


def _strategy_payload(
    path: list[dict[str, Any]],
    trades: list[dict[str, Any]],
    metrics: dict[str, Any],
    *,
    display_name: str,
    source_schema: str,
) -> dict[str, Any]:
    return {
        "displayName": display_name,
        "sourceSchema": source_schema,
        "path": path,
        "trades": trades,
        "metrics": {
            "label": metrics["label"],
            "equityMultiple": metrics["equity_multiple"],
            "returnPct": metrics["net_return_pct"],
            "mddPct": metrics["max_drawdown_pct"],
            "sharpe": metrics["sharpe"],
            "profitFactor": metrics["profit_factor"],
            "winRatePct": (
                None if metrics["win_rate"] is None else metrics["win_rate"] * 100.0
            ),
            "exposurePct": metrics["exposure_pct"],
            "trades": metrics["closed_trades"],
            "longTrades": metrics["long_trades"],
            "shortTrades": metrics["short_trades"],
            "cost": metrics["cost"],
            "fundingPayment": metrics["funding_payment"],
        },
    }


def build_trade_path_payload(
    *,
    candidate_path: Sequence[Mapping[str, Any]],
    v4_path: Sequence[Mapping[str, Any]],
    candidate_trades: Sequence[Mapping[str, Any]],
    v4_trades: Sequence[Mapping[str, Any]],
    candidate_metrics: Mapping[str, Any],
    v4_metrics: Mapping[str, Any],
    state_trace: Mapping[str, Any],
    title: str = "HYPE 1D MA7 Intent Optimization：完整交易路径",
    meta: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate retained results and build the strict embedded payload."""

    title = str(title).strip()
    if not title:
        raise ValueError("title must be non-empty")
    candidate_points = _normalize_path(candidate_path, label="candidate")
    v4_points, v4_source_schema = _normalize_exact_v4_path(
        v4_path, candidate_path=candidate_points
    )
    candidate_trade_rows = _normalize_trades(candidate_trades, label="candidate")
    v4_trade_rows = _normalize_trades(v4_trades, label="exact_v4")
    candidate_metric_row = _normalize_metrics(candidate_metrics, label="candidate")
    v4_metric_row = _normalize_metrics(v4_metrics, label="exact_v4")
    trace = _normalize_trace(state_trace)

    _validate_shared_market(candidate_points, v4_points)
    _merge_candidate_trace(candidate_points, trace)
    _decorate_v4_path(v4_points)
    for label, path, trades, metrics in (
        ("candidate", candidate_points, candidate_trade_rows, candidate_metric_row),
        ("exact_v4", v4_points, v4_trade_rows, v4_metric_row),
    ):
        _validate_metrics(metrics, trades, path, label=label)
        _validate_trade_transitions(path, trades, label=label)

    metadata = {} if meta is None else _as_mapping(meta, field="meta")
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "title": title,
        "subtitle": (
            "UTC daily · researcher-exposed retrospective research · "
            "explore / diagnostic-only · not promoted / not live-ready · "
            "candidate vs exact registered V4"
        ),
        "status": {
            "researchState": "explore",
            "promotion": "not promoted",
            "liveReadiness": "not live-ready",
            "timezone": "UTC",
            "comparator": "exact registered V4",
        },
        "meta": metadata,
        "strategies": {
            "candidate": _strategy_payload(
                candidate_points,
                candidate_trade_rows,
                candidate_metric_row,
                display_name="Candidate",
                source_schema="candidate_retained_path+full_state_trace",
            ),
            "exact_v4": _strategy_payload(
                v4_points,
                v4_trade_rows,
                v4_metric_row,
                display_name="Exact registered V4",
                source_schema=v4_source_schema,
            ),
        },
        "comparison": {
            "candidateMinusV4ReturnPp": (
                candidate_metric_row["net_return_pct"]
                - v4_metric_row["net_return_pct"]
            ),
            "candidateMinusV4MddPp": (
                candidate_metric_row["max_drawdown_pct"]
                - v4_metric_row["max_drawdown_pct"]
            ),
        },
        "candidateStateTrace": {
            "activationCounts": trace["activationCounts"],
            "events": trace["events"],
            "terminal": trace["terminal"],
            "startIndex": trace["startIndex"],
            "activeStart": trace["activeStart"],
            "terminalIndex": trace["terminalIndex"],
        },
        "audit": {
            "sharedMarketRows": len(candidate_points),
            "candidateTradeLinks": len(candidate_trade_rows),
            "exactV4TradeLinks": len(v4_trade_rows),
            "allTradeLinksRenderable": all(
                trade["link"]["renderable"]
                for key in STRATEGY_KEYS
                for trade in (
                    candidate_trade_rows if key == "candidate" else v4_trade_rows
                )
            ),
            "pathTradeTraceConsistency": "PASS",
            "exactV4SourceSchema": v4_source_schema,
            "exactV4MarketSource": (
                "shared_market_from_candidate"
                if "shared_market_from_candidate" in v4_source_schema
                else "retained_in_v4_path"
            ),
        },
    }
    # Re-serialize here so nested metadata/events cannot smuggle NaN into HTML.
    json.dumps(payload, ensure_ascii=False, allow_nan=False)
    return payload


def _json_for_script(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    return (
        serialized.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


HTML_TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<title>HYPE 1D MA7 Intent Optimization Trade Path</title>
<style>
:root{color-scheme:dark;--bg:#070a0e;--panel:#0c1117;--panel2:#101821;--line:#26313c;
--grid:#1b252e;--text:#edf2f6;--muted:#8b9aa8;--up:#2fd1a2;--down:#f06478;
--ma:#f4c95d;--band:#778a9e;--candidate:#65d5ff;--v4:#a996ff;--equity:#a8e866;
--slope:#4fc3f7;--rsi:#c69cff;--armed:#ffb55c;--qualified:#ffe05d;--counter:#61d6b3}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);
font:13px/1.45 ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace}
.shell{max-width:1900px;margin:0 auto;padding:22px}header{display:grid;grid-template-columns:1fr auto;
gap:18px;align-items:end;margin-bottom:15px}h1{margin:0 0 7px;font:650 24px/1.2 system-ui,sans-serif}
.subtitle,.hint,.meta{color:var(--muted);font-size:12px}.status{margin-top:8px;display:flex;flex-wrap:wrap;gap:7px}
.tag{border:1px solid var(--line);padding:3px 7px;background:var(--panel)}.tag.warn{color:#ffcc69}
.metrics{display:flex;flex-wrap:wrap;gap:7px;justify-content:flex-end}.metric{min-width:110px;padding:8px 10px;
border:1px solid var(--line);background:var(--panel)}.metric span{display:block;color:var(--muted);font-size:11px}
.metric b{display:block;margin-top:2px;font-size:15px}.toolbar{display:flex;flex-wrap:wrap;gap:8px 16px;
align-items:center;padding:10px 12px;border:1px solid var(--line);background:var(--panel2)}button,select{color:var(--text);
border:1px solid #344452;background:#141d26;padding:6px 9px;font:inherit;cursor:pointer}button:hover,select:hover{border-color:#75889a}
label{color:var(--muted);user-select:none}input{vertical-align:-2px}.detail{min-height:34px;padding:8px 12px;
border:1px solid var(--line);border-top:0;background:#0b1016;color:#c5d0da;white-space:nowrap;overflow:auto}
.chart{position:relative;border:1px solid var(--line);border-top:0;background:var(--panel);overflow:hidden}canvas{width:100%;display:block}
#priceChart{height:520px;cursor:crosshair}#slopeChart{height:145px;border-top:1px solid var(--line)}
#rsiChart{height:145px;border-top:1px solid var(--line)}#stateChart{height:185px;border-top:1px solid var(--line)}
#equityChart{height:190px;border-top:1px solid var(--line)}.hint{padding:8px 12px;border:1px solid var(--line);border-top:0}
.table-wrap{margin-top:18px;border:1px solid var(--line);overflow:auto;max-height:560px}table{width:100%;border-collapse:collapse;min-width:1500px}
th,td{padding:7px 9px;border-bottom:1px solid var(--grid);text-align:right;white-space:nowrap}th{position:sticky;top:0;z-index:1;
background:var(--panel2);color:var(--muted)}th:nth-child(-n+5),td:nth-child(-n+5),th:nth-child(10),td:nth-child(10),th:nth-child(11),td:nth-child(11){text-align:left}
tbody tr{cursor:pointer}tbody tr:hover,tbody tr.active{background:#16212a}.positive,.long{color:var(--up)}.negative,.short{color:var(--down)}
#tooltip{position:fixed;display:none;z-index:10;pointer-events:none;max-width:520px;padding:9px 11px;border:1px solid #526576;
background:rgba(7,10,14,.97);box-shadow:0 10px 30px rgba(0,0,0,.45);white-space:pre-line;font-size:12px}
.meta{margin-top:9px}.legend{display:inline-flex;gap:10px}.swatch{display:inline-block;width:13px;height:3px;margin-right:4px;vertical-align:3px}
@media(max-width:900px){.shell{padding:10px}header{grid-template-columns:1fr}.metrics{justify-content:flex-start}#priceChart{height:430px}}
</style>
</head>
<body>
<main class="shell">
<header><div><h1 id="title"></h1><div class="subtitle" id="subtitle"></div><div class="status" id="status"></div><div class="meta" id="meta"></div></div>
<div class="metrics" id="metrics"></div></header>
<div class="toolbar">
<label>路径 <select id="strategySelect"><option value="candidate">Candidate</option><option value="exact_v4">Exact registered V4</option></select></label>
<button type="button" id="reset">完整范围</button><button type="button" id="zoomIn">放大</button><button type="button" id="zoomOut">缩小</button>
<label><input type="checkbox" id="showMa" checked> SMA7</label><label><input type="checkbox" id="showBands" checked> 实际 ATR bands</label>
<label><input type="checkbox" id="showTrades" checked> entry-exit 连线</label><label><input type="checkbox" id="showLabels"> 交易编号</label>
<label><input type="checkbox" id="compareEquity" checked> 对比权益</label>
<span class="legend"><span><i class="swatch" style="background:var(--up)"></i>long</span><span><i class="swatch" style="background:var(--down)"></i>short</span></span>
</div>
<div class="detail" id="stateDetail">悬停查看完整状态</div>
<section class="chart" aria-label="完整交易路径图">
<canvas id="priceChart" role="img" aria-label="HYPEUSDT 日K、SMA7、ATR bands 与逐笔交易连线"></canvas>
<canvas id="slopeChart" role="img" aria-label="ATR 归一化 MA7 slope"></canvas>
<canvas id="rsiChart" role="img" aria-label="RSI6"></canvas>
<canvas id="stateChart" role="img" aria-label="position、armed 状态及连续计数器"></canvas>
<canvas id="equityChart" role="img" aria-label="candidate 与 exact V4 权益"></canvas>
</section>
<div class="hint">UTC · 滚轮缩放 · 价格图拖拽平移 · 双击恢复 · 悬停核对 OHLC/指标/armed provenance/counters · 点击逐笔记录定位</div>
<div class="table-wrap"><table><thead><tr><th>编号</th><th>方向</th><th>信号 UTC</th><th>入场 UTC</th><th>出场 UTC</th>
<th>入场价</th><th>出场价</th><th>持有日</th><th>净收益</th><th>入场原因</th><th>退出原因</th><th>MFE</th><th>MAE</th><th>回吐</th><th>净 PnL</th></tr></thead>
<tbody id="tradeRows"></tbody></table></div>
</main><div id="tooltip" role="tooltip"></div>
<script>
/*PAYLOAD_START*/const DATA=__PAYLOAD__;/*PAYLOAD_END*/
const DAY=86400000,C={bg:"#0c1117",bg2:"#090e13",grid:"#1b252e",muted:"#8b9aa8",up:"#2fd1a2",down:"#f06478",ma:"#f4c95d",band:"#778a9e",candidate:"#65d5ff",v4:"#a996ff",equity:"#a8e866",slope:"#4fc3f7",rsi:"#c69cff",armed:"#ffb55c",qualified:"#ffe05d",counter:"#61d6b3"};
const $=id=>document.getElementById(id),canvases=[$("priceChart"),$("slopeChart"),$("rsiChart"),$("stateChart"),$("equityChart")],tooltip=$("tooltip"),rows=$("tradeRows");
let strategyKey="candidate",hoverT=null,activeTrade=null,dragging=false,dragX=0,dragStart=0;
const all=DATA.strategies,domainMin=all.candidate.path[0].t,domainMax=all.candidate.path.at(-1).t;
let viewStart=domainMin,viewEnd=domainMax;
function active(){return all[strategyKey]}function otherKey(){return strategyKey==="candidate"?"exact_v4":"candidate"}
function daily(strategy=active()){return strategy.path.filter(p=>!p.terminal)}function trades(){return active().trades}
function clamp(v,lo,hi){return Math.max(lo,Math.min(hi,v))}function signed(v,d=2){return(v>=0?"+":"")+Number(v).toFixed(d)}
function fmt(v,d=2){return v==null?"—":Number(v).toFixed(d)}function dt(t){return new Date(t).toISOString().replace(".000Z","Z").replace("T"," ")}
function day(t){return new Date(t).toISOString().slice(0,10)}function esc(v){return String(v??"—").replace(/[&<>"']/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch]))}
function setup(canvas){const r=canvas.getBoundingClientRect(),d=window.devicePixelRatio||1;canvas.width=Math.round(r.width*d);canvas.height=Math.round(r.height*d);const ctx=canvas.getContext("2d");ctx.setTransform(d,0,0,d,0,0);return{ctx,w:r.width,h:r.height}}
function xs(t,l,w){return l+(t-viewStart)/(viewEnd-viewStart)*w}function visible(strategy=active()){return daily(strategy).filter(p=>p.t>=viewStart-DAY&&p.t<=viewEnd+DAY)}
function ticks(lo,hi,n=5){const span=Math.max(1e-9,hi-lo),raw=span/n,p=10**Math.floor(Math.log10(raw)),q=raw/p,step=(q<1.5?1:q<3?2:q<7?5:10)*p,out=[];for(let v=Math.ceil(lo/step)*step;v<=hi+step*.1;v+=step)out.push(v);return out}
function axes(ctx,m,w,h,lo,hi,y,time=true){ctx.font="11px ui-monospace";for(const v of ticks(lo,hi)){const yy=y(v);ctx.strokeStyle=C.grid;ctx.beginPath();ctx.moveTo(m.l,yy);ctx.lineTo(m.l+w,yy);ctx.stroke();ctx.fillStyle=C.muted;ctx.textAlign="right";ctx.fillText(Math.abs(v)<10?v.toFixed(2):v.toFixed(1),m.l-7,yy+4)}if(time)for(let i=0;i<=7;i++){const t=viewStart+(viewEnd-viewStart)*i/7,x=xs(t,m.l,w);ctx.strokeStyle=C.grid;ctx.beginPath();ctx.moveTo(x,m.t);ctx.lineTo(x,m.t+h);ctx.stroke();ctx.fillStyle=C.muted;ctx.textAlign=i===0?"left":i===7?"right":"center";ctx.fillText(day(t),x,m.t+h+18)}}
function line(ctx,points,key,color,y,l,w,dash=[]){ctx.strokeStyle=color;ctx.lineWidth=1.5;ctx.setLineDash(dash);ctx.beginPath();let on=false;for(const p of points){if(p[key]==null){on=false;continue}const x=xs(p.t+DAY/2,l,w),yy=y(p[key]);if(!on){ctx.moveTo(x,yy);on=true}else ctx.lineTo(x,yy)}ctx.stroke();ctx.setLineDash([])}
function cross(ctx,m,w,h){if(hoverT==null)return;const x=xs(hoverT+DAY/2,m.l,w);ctx.strokeStyle=C.muted;ctx.globalAlpha=.7;ctx.setLineDash([3,3]);ctx.beginPath();ctx.moveTo(x,m.t);ctx.lineTo(x,m.t+h);ctx.stroke();ctx.setLineDash([]);ctx.globalAlpha=1}
function marker(ctx,x,y,side,entry,color,size){ctx.fillStyle=color;ctx.strokeStyle=C.bg2;ctx.lineWidth=1.4;ctx.beginPath();if(entry){if(side==="long"){ctx.moveTo(x,y-size);ctx.lineTo(x-size,y+size);ctx.lineTo(x+size,y+size)}else{ctx.moveTo(x,y+size);ctx.lineTo(x-size,y-size);ctx.lineTo(x+size,y-size)}ctx.closePath()}else ctx.arc(x,y,size-1,0,Math.PI*2);ctx.fill();ctx.stroke()}
function drawPrice(){const{ctx,w,h}=setup($("priceChart"));ctx.fillStyle=C.bg;ctx.fillRect(0,0,w,h);const m={l:72,r:22,t:22,b:34},pw=w-m.l-m.r,ph=h-m.t-m.b,points=visible();if(!points.length)return;let lo=Math.min(...points.map(p=>p.l)),hi=Math.max(...points.map(p=>p.h));for(const p of points){if($("showBands").checked&&p.lowerBand!=null)lo=Math.min(lo,p.lowerBand);if($("showBands").checked&&p.upperBand!=null)hi=Math.max(hi,p.upperBand)}const inView=trades().filter(t=>t.exitT>=viewStart&&t.entryT<=viewEnd);for(const t of inView){lo=Math.min(lo,t.entry,t.exit);hi=Math.max(hi,t.entry,t.exit)}const pad=(hi-lo)*.07||1;lo-=pad;hi+=pad;const y=v=>m.t+(hi-v)/(hi-lo)*ph;axes(ctx,m,pw,ph,lo,hi,y,true);const bw=clamp(pw/Math.max(1,(viewEnd-viewStart)/DAY)*.62,1,13);for(const p of points){const x=xs(p.t+DAY/2,m.l,pw),color=p.c>=p.o?C.up:C.down;ctx.strokeStyle=color;ctx.beginPath();ctx.moveTo(x,y(p.h));ctx.lineTo(x,y(p.l));ctx.stroke();ctx.fillStyle=color;ctx.fillRect(x-bw/2,y(Math.max(p.o,p.c)),bw,Math.max(1,y(Math.min(p.o,p.c))-y(Math.max(p.o,p.c))))}if($("showBands").checked){line(ctx,points,"upperBand",C.band,y,m.l,pw,[4,4]);line(ctx,points,"lowerBand",C.band,y,m.l,pw,[4,4])}if($("showMa").checked)line(ctx,points,"ma7",C.ma,y,m.l,pw);if($("showTrades").checked)for(const t of inView){const hot=activeTrade===t.id,color=t.side==="long"?C.up:C.down,x1=xs(t.entryT,m.l,pw),x2=xs(t.exitT,m.l,pw),y1=y(t.entry),y2=y(t.exit);ctx.strokeStyle=color;ctx.globalAlpha=hot?1:.72;ctx.lineWidth=hot?3:1.5;ctx.setLineDash(t.netReturnPct>=0?[]:[5,4]);ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();ctx.setLineDash([]);ctx.globalAlpha=1;marker(ctx,x1,y1,t.side,true,color,hot?8:6);marker(ctx,x2,y2,t.side,false,color,hot?8:6);if($("showLabels").checked||hot){ctx.fillStyle=color;ctx.textAlign="center";ctx.font="10px ui-monospace";ctx.fillText(t.id,x1,y1+(t.side==="long"?18:-12))}}cross(ctx,m,pw,ph);ctx.fillStyle=C.muted;ctx.textAlign="left";ctx.font="11px ui-monospace";ctx.fillText(`PRICE · HYPEUSDT · ${active().displayName}`,m.l,14)}
function drawSeries(canvasId,key,color,label,forced){const{ctx,w,h}=setup($(canvasId));ctx.fillStyle=C.bg2;ctx.fillRect(0,0,w,h);const m={l:72,r:22,t:18,b:30},pw=w-m.l-m.r,ph=h-m.t-m.b,points=visible(),values=points.map(p=>p[key]).filter(v=>v!=null);if(!values.length){ctx.fillStyle=C.muted;ctx.fillText(`${label} · unavailable for this path`,m.l,24);return}let lo=forced?forced[0]:Math.min(0,...values),hi=forced?forced[1]:Math.max(0,...values);if(!forced){const pad=(hi-lo)*.12||.02;lo-=pad;hi+=pad}const y=v=>m.t+(hi-v)/(hi-lo)*ph;axes(ctx,m,pw,ph,lo,hi,y,false);if(lo<0&&hi>0){ctx.strokeStyle=C.grid;ctx.beginPath();ctx.moveTo(m.l,y(0));ctx.lineTo(m.l+pw,y(0));ctx.stroke()}if(key==="rsi6")for(const v of[30,70]){ctx.strokeStyle=v===30?C.up:C.down;ctx.globalAlpha=.6;ctx.setLineDash([4,4]);ctx.beginPath();ctx.moveTo(m.l,y(v));ctx.lineTo(m.l+pw,y(v));ctx.stroke();ctx.setLineDash([]);ctx.globalAlpha=1}line(ctx,points,key,color,y,m.l,pw);cross(ctx,m,pw,ph);ctx.fillStyle=C.muted;ctx.textAlign="left";ctx.font="11px ui-monospace";ctx.fillText(label,m.l,12)}
function originCode(value){if(!value)return"";return value.split("_").map(v=>v[0]).join("").slice(0,3).toUpperCase()}
function drawState(){const{ctx,w,h}=setup($("stateChart"));ctx.fillStyle=C.bg;ctx.fillRect(0,0,w,h);const m={l:112,r:22,t:15,b:30},pw=w-m.l-m.r,points=visible(),lanes=[26,55],bar=Math.max(1,pw/Math.max(1,(viewEnd-viewStart)/DAY));for(const [label,y] of [["POSITION",lanes[0]],["ARMED / ORIGIN",lanes[1]],["ARMED AGE",89],["SLOPE LOSS RUN",118],["SHORT RSI RUN",147]]){ctx.fillStyle=C.muted;ctx.textAlign="right";ctx.font="10px ui-monospace";ctx.fillText(label,m.l-8,y+4);ctx.strokeStyle=C.grid;ctx.beginPath();ctx.moveTo(m.l,y+10);ctx.lineTo(m.l+pw,y+10);ctx.stroke()}for(const p of points){const x=xs(p.t,m.l,pw),x2=xs(p.t+DAY,m.l,pw),width=Math.max(1,x2-x);if(p.side){ctx.fillStyle=p.side>0?C.up:C.down;ctx.globalAlpha=.62;ctx.fillRect(x,lanes[0]-8,width,16)}if(p.armedSide){ctx.fillStyle=C.armed;ctx.globalAlpha=.74;ctx.fillRect(x,lanes[1]-8,width,16);if(p.armedOverboughtQualified){ctx.strokeStyle=C.qualified;ctx.globalAlpha=1;ctx.lineWidth=2;ctx.strokeRect(x+.5,lanes[1]-7.5,Math.max(0,width-1),15)}if(width>13){ctx.fillStyle=C.bg;ctx.globalAlpha=1;ctx.font="8px ui-monospace";ctx.textAlign="center";ctx.fillText(originCode(p.armedOrigin),x+width/2,lanes[1]+3)}}ctx.globalAlpha=1}const drawCounter=(key,y,color)=>{const vals=points.map(p=>p[key]).filter(v=>v!=null),max=Math.max(1,...vals);ctx.strokeStyle=color;ctx.lineWidth=1.5;ctx.beginPath();let started=false;for(const p of points){if(p[key]==null){started=false;continue}const x=xs(p.t+DAY/2,m.l,pw),yy=y-Math.min(1,p[key]/max)*13;if(!started){ctx.moveTo(x,yy);started=true}else ctx.lineTo(x,yy)}ctx.stroke();ctx.fillStyle=color;ctx.textAlign="left";ctx.fillText(`max ${max}`,m.l+pw-45,y+4)};drawCounter("armedAge",89,C.armed);drawCounter("slopeLossRun",118,C.slope);drawCounter("shortRsiRun",147,C.rsi);cross(ctx,{l:m.l,t:m.t},pw,h-m.t-m.b);ctx.fillStyle=C.muted;ctx.textAlign="left";ctx.fillText(strategyKey==="candidate"?"Candidate trace · yellow outline = overbought-qualified":"Exact V4 · age/origin/qualified/counters unavailable by contract",m.l,h-8)}
function equityLine(ctx,strategy,color,y,m,pw,alpha,width){const points=strategy.path.filter(p=>p.t>=viewStart-DAY&&p.t<=viewEnd+DAY);ctx.strokeStyle=color;ctx.globalAlpha=alpha;ctx.lineWidth=width;ctx.beginPath();points.forEach((p,i)=>{const x=xs(p.t,m.l,pw);if(i)ctx.lineTo(x,y(p.equity));else ctx.moveTo(x,y(p.equity))});ctx.stroke();ctx.globalAlpha=1}
function drawEquity(){const{ctx,w,h}=setup($("equityChart"));ctx.fillStyle=C.bg2;ctx.fillRect(0,0,w,h);const m={l:72,r:22,t:20,b:34},pw=w-m.l-m.r,ph=h-m.t-m.b,series=[...active().path.filter(p=>p.t>=viewStart-DAY&&p.t<=viewEnd+DAY)];if($("compareEquity").checked)series.push(...all[otherKey()].path.filter(p=>p.t>=viewStart-DAY&&p.t<=viewEnd+DAY));let lo=Math.min(...series.map(p=>p.equity)),hi=Math.max(...series.map(p=>p.equity)),pad=(hi-lo)*.08||.1;lo=Math.max(0,lo-pad);hi+=pad;const y=v=>m.t+(hi-v)/(hi-lo)*ph;axes(ctx,m,pw,ph,lo,hi,y,true);if($("compareEquity").checked)equityLine(ctx,all[otherKey()],otherKey()==="candidate"?C.candidate:C.v4,y,m,pw,.45,1.3);equityLine(ctx,active(),strategyKey==="candidate"?C.candidate:C.v4,y,m,pw,1,2.2);cross(ctx,m,pw,ph);ctx.fillStyle=C.muted;ctx.textAlign="left";ctx.font="11px ui-monospace";ctx.fillText(`EQUITY MULTIPLE · active ${active().displayName}${$("compareEquity").checked?" · ghost comparator":""}`,m.l,13)}
function metrics(){const m=active().metrics,d=DATA.comparison;$("metrics").innerHTML=[["路径",active().displayName],["净收益",signed(m.returnPct)+"%"],["MDD",fmt(m.mddPct)+"%"],["权益",fmt(m.equityMultiple,3)+"x"],["交易",`${m.trades} (${m.longTrades}L/${m.shortTrades}S)`],["胜率",m.winRatePct==null?"—":fmt(m.winRatePct)+"%"],["vs V4 收益",signed(d.candidateMinusV4ReturnPp)+"pp"],["vs V4 MDD",signed(d.candidateMinusV4MddPp)+"pp"]].map(([k,v])=>`<div class="metric"><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join("")}
function stateDetail(point){if(!point){$("stateDetail").textContent="悬停查看完整状态";return}const pos=point.side>0?"LONG":point.side<0?"SHORT":"FLAT",armed=point.armedSide>0?"LONG":point.armedSide<0?"SHORT":"FLAT";$("stateDetail").textContent=`${dt(point.t)} UTC | position=${pos} | armed=${armed} | armed_age=${point.armedAge??"—"} | origin=${point.armedOrigin??"—"} | overbought_qualified=${point.armedOverboughtQualified??"—"} | slope_loss_run=${point.slopeLossRun??"—"} | short_rsi_run=${point.shortRsiRun??"—"} | pending=${point.pendingReason??"—"}`}
function table(){rows.innerHTML=trades().map(t=>`<tr data-id="${esc(t.id)}"><td>${esc(t.id)}</td><td class="${t.side}">${t.side}</td><td>${t.signalTs?esc(t.signalTs):"—"}</td><td>${dt(t.entryT)}</td><td>${dt(t.exitT)}</td><td>${fmt(t.entry,4)}</td><td>${fmt(t.exit,4)}</td><td>${fmt(t.durationDays,1)}</td><td class="${t.netReturnPct>=0?"positive":"negative"}">${signed(t.netReturnPct)}%</td><td>${esc(t.entryReason)}</td><td>${esc(t.exitReason)}</td><td>${t.mfePct==null?"—":signed(t.mfePct)+"%"}</td><td>${t.maePct==null?"—":signed(t.maePct)+"%"}</td><td>${t.givebackPct==null?"—":fmt(t.givebackPct)+"%"}</td><td class="${t.netPnl==null?"":t.netPnl>=0?"positive":"negative"}">${t.netPnl==null?"—":signed(t.netPnl,4)}</td></tr>`).join("");for(const row of rows.querySelectorAll("tr")){row.onmouseenter=()=>{activeTrade=row.dataset.id;draw()};row.onmouseleave=()=>{activeTrade=null;draw()};row.onclick=()=>focusTrade(row.dataset.id)}}
function focusTrade(id){const trade=trades().find(t=>t.id===id);if(!trade)return;const span=Math.max(21*DAY,(trade.exitT-trade.entryT)*2.2),mid=(trade.entryT+trade.exitT)/2;viewStart=clamp(mid-span/2,domainMin,Math.max(domainMin,domainMax-span));viewEnd=Math.min(domainMax,viewStart+span);activeTrade=id;draw();$("priceChart").scrollIntoView({behavior:"smooth",block:"center"})}
function draw(){metrics();drawPrice();drawSeries("slopeChart","slopeAtr",C.slope,"MA7 SLOPE · ATR/day",null);drawSeries("rsiChart","rsi6",C.rsi,"RSI6 · 30 / 70",[0,100]);drawState();drawEquity();for(const row of rows.querySelectorAll("tr"))row.classList.toggle("active",row.dataset.id===activeTrade);const p=hoverT==null?null:daily().find(x=>x.t===hoverT);stateDetail(p)}
function reset(){viewStart=domainMin;viewEnd=domainMax;activeTrade=null;hoverT=null;draw()}function zoom(f,anchor=(viewStart+viewEnd)/2){const current=viewEnd-viewStart,next=clamp(current*f,14*DAY,domainMax-domainMin),ratio=(anchor-viewStart)/current;viewStart=anchor-next*ratio;viewEnd=viewStart+next;if(viewStart<domainMin){viewEnd+=domainMin-viewStart;viewStart=domainMin}if(viewEnd>domainMax){viewStart-=viewEnd-domainMax;viewEnd=domainMax}draw()}
function nearest(t){const points=daily();let best=points[0],distance=Math.abs(points[0].t-t);for(const p of points){const d=Math.abs(p.t-t);if(d<distance){best=p;distance=d}}return best}
function hover(event,canvas){const rect=canvas.getBoundingClientRect(),mLeft=canvas.id==="stateChart"?112:72,mRight=22,pw=rect.width-mLeft-mRight,t=viewStart+clamp((event.clientX-rect.left-mLeft)/pw,0,1)*(viewEnd-viewStart),p=nearest(t);hoverT=p.t;const pos=p.side>0?"LONG":p.side<0?"SHORT":"FLAT",armed=p.armedSide>0?"LONG":p.armedSide<0?"SHORT":"FLAT";tooltip.textContent=`${dt(p.t)} UTC · ${active().displayName}\nO ${fmt(p.o,4)}  H ${fmt(p.h,4)}  L ${fmt(p.l,4)}  C ${fmt(p.c,4)}\nSMA7 ${fmt(p.ma7,4)}  ATR7 ${fmt(p.atr7,4)}  bands ${fmt(p.lowerBand,4)} / ${fmt(p.upperBand,4)}\nslope ${fmt(p.slopeAtr,4)}  RSI6 ${fmt(p.rsi6,2)}  relation ${p.relation??"—"}\nposition ${pos}  equity ${fmt(p.equity,4)}x\narmed ${armed}  age ${p.armedAge??"—"}  origin ${p.armedOrigin??"—"}  qualified ${p.armedOverboughtQualified??"—"}\nslope_loss_run ${p.slopeLossRun??"—"}  short_rsi_run ${p.shortRsiRun??"—"}\npending ${p.pendingReason??"—"}  open_fill ${p.openFillReason??"—"}`;tooltip.style.display="block";tooltip.style.left=`${Math.min(innerWidth-530,event.clientX+14)}px`;tooltip.style.top=`${Math.min(innerHeight-210,event.clientY+14)}px`;draw()}
for(const canvas of canvases){canvas.addEventListener("mousemove",event=>hover(event,canvas));canvas.addEventListener("mouseleave",()=>{tooltip.style.display="none";hoverT=null;draw()})}
const price=$("priceChart");price.addEventListener("wheel",event=>{event.preventDefault();const rect=price.getBoundingClientRect(),anchor=viewStart+clamp((event.clientX-rect.left-72)/(rect.width-94),0,1)*(viewEnd-viewStart);zoom(event.deltaY<0?.78:1.28,anchor)},{passive:false});price.addEventListener("pointerdown",event=>{dragging=true;dragX=event.clientX;dragStart=viewStart;price.setPointerCapture(event.pointerId)});price.addEventListener("pointermove",event=>{if(!dragging)return;const span=viewEnd-viewStart,shift=-(event.clientX-dragX)/price.getBoundingClientRect().width*span;viewStart=clamp(dragStart+shift,domainMin,domainMax-span);viewEnd=viewStart+span;draw()});price.addEventListener("pointerup",()=>{dragging=false});price.ondblclick=reset;
$("strategySelect").onchange=event=>{strategyKey=event.target.value;activeTrade=null;hoverT=null;table();draw()};$("reset").onclick=reset;$("zoomIn").onclick=()=>zoom(.65);$("zoomOut").onclick=()=>zoom(1.55);for(const id of["showMa","showBands","showTrades","showLabels","compareEquity"])$(id).onchange=draw;
$("title").textContent=DATA.title;$("subtitle").textContent=DATA.subtitle;$("status").innerHTML=[DATA.status.researchState,DATA.status.promotion,DATA.status.liveReadiness,DATA.status.timezone,DATA.status.comparator].map((v,i)=>`<span class="tag ${i>0&&i<3?"warn":""}">${esc(v)}</span>`).join("");$("meta").textContent=Object.entries(DATA.meta).map(([k,v])=>`${k}=${typeof v==="object"?JSON.stringify(v):v}`).join(" · ");
new ResizeObserver(draw).observe(document.querySelector(".chart"));table();draw();
</script>
</body>
</html>
"""


def build_trade_path_html_document(
    *,
    candidate_path: Sequence[Mapping[str, Any]],
    v4_path: Sequence[Mapping[str, Any]],
    candidate_trades: Sequence[Mapping[str, Any]],
    v4_trades: Sequence[Mapping[str, Any]],
    candidate_metrics: Mapping[str, Any],
    v4_metrics: Mapping[str, Any],
    state_trace: Mapping[str, Any],
    title: str = "HYPE 1D MA7 Intent Optimization：完整交易路径",
    meta: Mapping[str, Any] | None = None,
) -> tuple[bytes, dict[str, Any]]:
    """Validate and return deterministic UTF-8 HTML bytes without writing.

    The returned audit record is intentionally small enough for the stage
    orchestrator to retain alongside its locked component hashes.
    """

    payload = build_trade_path_payload(
        candidate_path=candidate_path,
        v4_path=v4_path,
        candidate_trades=candidate_trades,
        v4_trades=v4_trades,
        candidate_metrics=candidate_metrics,
        v4_metrics=v4_metrics,
        state_trace=state_trace,
        title=title,
        meta=meta,
    )
    serialized = _json_for_script(payload)
    if HTML_TEMPLATE.count("__PAYLOAD__") != 1:
        raise RuntimeError("renderer template payload marker drift")
    document = HTML_TEMPLATE.replace("__PAYLOAD__", serialized)
    if "__PAYLOAD__" in document:
        raise RuntimeError("renderer template placeholder remains")
    encoded = document.encode("utf-8")
    audit = {
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "bytes": len(encoded),
        "schema_version": SCHEMA_VERSION,
        "candidate_trade_links": payload["audit"]["candidateTradeLinks"],
        "exact_v4_trade_links": payload["audit"]["exactV4TradeLinks"],
        "status": payload["audit"]["pathTradeTraceConsistency"],
        "title": html.unescape(payload["title"]),
    }
    return encoded, audit


def render_trade_path_html(
    output_path: str | Path,
    *,
    candidate_path: Sequence[Mapping[str, Any]],
    v4_path: Sequence[Mapping[str, Any]],
    candidate_trades: Sequence[Mapping[str, Any]],
    v4_trades: Sequence[Mapping[str, Any]],
    candidate_metrics: Mapping[str, Any],
    v4_metrics: Mapping[str, Any],
    state_trace: Mapping[str, Any],
    title: str = "HYPE 1D MA7 Intent Optimization：完整交易路径",
    meta: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build, then exclusively write one offline comparison HTML document."""

    output = Path(output_path).expanduser().resolve()
    if output.suffix.lower() != ".html":
        raise ValueError("output_path must end in .html")
    if not output.parent.is_dir():
        raise FileNotFoundError(f"output directory does not exist: {output.parent}")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing HTML: {output}")
    encoded, audit = build_trade_path_html_document(
        candidate_path=candidate_path,
        v4_path=v4_path,
        candidate_trades=candidate_trades,
        v4_trades=v4_trades,
        candidate_metrics=candidate_metrics,
        v4_metrics=v4_metrics,
        state_trace=state_trace,
        title=title,
        meta=meta,
    )
    with output.open("xb") as handle:
        handle.write(encoded)
    return {"path": str(output), **audit}


__all__ = [
    "build_trade_path_html_document",
    "build_trade_path_payload",
    "render_trade_path_html",
]
