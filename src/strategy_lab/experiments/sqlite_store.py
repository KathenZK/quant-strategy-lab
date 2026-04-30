from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
import json
import sqlite3
import threading
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from strategy_lab.experiments.registry import RunRegistryEntry


_SQLITE_SCHEMA_LOCK = threading.RLock()
_SQLITE_WRITE_LOCK = threading.RLock()


def _json_dumps(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, default=str)


def _json_loads(payload: str | None, *, default):
    if not payload:
        return default
    return json.loads(payload)


def _safe_float(value: object | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_ts(value: object) -> str:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def _frame_from_parquet(path: str | None) -> pd.DataFrame:
    if not path:
        return pd.DataFrame()
    parquet_path = Path(path)
    if not parquet_path.exists():
        return pd.DataFrame()
    return pd.read_parquet(parquet_path)


class RunSqliteStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)

    def _connect(self, *, configure_wal: bool = False) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path, timeout=60.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 60000")
        connection.execute("PRAGMA foreign_keys = ON")
        if configure_wal:
            connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        return connection

    def ensure_schema(self) -> Path:
        with _SQLITE_SCHEMA_LOCK:
            with self._connect(configure_wal=True) as connection:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS runs (
                        manifest_path TEXT PRIMARY KEY,
                        kind TEXT NOT NULL,
                        name TEXT NOT NULL,
                        run_id TEXT NOT NULL,
                        generated_at TEXT NOT NULL,
                        app_config_path TEXT,
                        primary_report_path TEXT,
                        factor_report_path TEXT,
                        backtest_report_path TEXT,
                        paper_report_path TEXT,
                        strategy_name TEXT,
                        signal_name TEXT,
                        strategy_type TEXT,
                        variant_id TEXT,
                        config_hash TEXT,
                        git_sha TEXT,
                        data_snapshot_id TEXT,
                        signal_version TEXT,
                        backtest_metrics_json TEXT NOT NULL DEFAULT '{}',
                        backtest_attribution_json TEXT NOT NULL DEFAULT '{}',
                        paper_summary_json TEXT NOT NULL DEFAULT '{}',
                        structured_artifact_paths_json TEXT NOT NULL DEFAULT '{}',
                        child_manifest_paths_json TEXT NOT NULL DEFAULT '[]',
                        manifest_json TEXT,
                        sharpe REAL,
                        cumulative_return REAL,
                        annualized_return REAL,
                        max_drawdown REAL,
                        avg_turnover REAL,
                        final_equity REAL,
                        fill_count REAL
                    );

                    CREATE INDEX IF NOT EXISTS idx_runs_kind_generated_at
                        ON runs(kind, generated_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_runs_strategy_name
                        ON runs(strategy_name);
                    CREATE INDEX IF NOT EXISTS idx_runs_strategy_type
                        ON runs(strategy_type);
                    CREATE INDEX IF NOT EXISTS idx_runs_sharpe
                        ON runs(sharpe DESC);

                    CREATE TABLE IF NOT EXISTS run_relations (
                        parent_manifest_path TEXT NOT NULL,
                        child_manifest_path TEXT NOT NULL,
                        relation_type TEXT NOT NULL,
                        ordinal INTEGER NOT NULL DEFAULT 0,
                        PRIMARY KEY (parent_manifest_path, child_manifest_path, relation_type),
                        FOREIGN KEY (parent_manifest_path) REFERENCES runs(manifest_path) ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS idx_run_relations_parent
                        ON run_relations(parent_manifest_path, ordinal);

                    CREATE TABLE IF NOT EXISTS run_series (
                        manifest_path TEXT NOT NULL,
                        series_name TEXT NOT NULL,
                        ts TEXT NOT NULL,
                        value REAL,
                        PRIMARY KEY (manifest_path, series_name, ts),
                        FOREIGN KEY (manifest_path) REFERENCES runs(manifest_path) ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS idx_run_series_lookup
                        ON run_series(manifest_path, series_name, ts);

                    CREATE TABLE IF NOT EXISTS run_trades (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        manifest_path TEXT NOT NULL,
                        ts TEXT NOT NULL,
                        symbol TEXT,
                        side TEXT,
                        previous_weight REAL,
                        target_weight REAL,
                        delta_weight REAL,
                        price REAL,
                        signal REAL,
                        reason TEXT,
                        FOREIGN KEY (manifest_path) REFERENCES runs(manifest_path) ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS idx_run_trades_lookup
                        ON run_trades(manifest_path, ts);
                    """
                )
        return self.db_path

    def load_count(self) -> int:
        self.ensure_schema()
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM runs").fetchone()
        return int(row["count"]) if row else 0

    def _run_record(self, entry: RunRegistryEntry, manifest_payload: dict | None = None) -> dict[str, object]:
        backtest_metrics = dict(entry.backtest_metrics)
        paper_summary = dict(entry.paper_summary)
        return {
            "manifest_path": entry.manifest_path,
            "kind": entry.kind,
            "name": entry.name,
            "run_id": entry.run_id,
            "generated_at": entry.generated_at,
            "app_config_path": entry.app_config_path,
            "primary_report_path": entry.primary_report_path,
            "factor_report_path": entry.factor_report_path,
            "backtest_report_path": entry.backtest_report_path,
            "paper_report_path": entry.paper_report_path,
            "strategy_name": entry.strategy_name,
            "signal_name": entry.signal_name,
            "strategy_type": entry.strategy_type,
            "variant_id": entry.variant_id,
            "config_hash": entry.config_hash,
            "git_sha": entry.git_sha,
            "data_snapshot_id": entry.data_snapshot_id,
            "signal_version": (manifest_payload or {}).get("signal_version"),
            "backtest_metrics_json": _json_dumps(backtest_metrics),
            "backtest_attribution_json": _json_dumps(entry.backtest_attribution),
            "paper_summary_json": _json_dumps(paper_summary),
            "structured_artifact_paths_json": _json_dumps(entry.structured_artifact_paths),
            "child_manifest_paths_json": _json_dumps(entry.child_manifest_paths),
            "manifest_json": _json_dumps(manifest_payload) if manifest_payload is not None else None,
            "sharpe": _safe_float(backtest_metrics.get("sharpe")),
            "cumulative_return": _safe_float(backtest_metrics.get("cumulative_return")),
            "annualized_return": _safe_float(backtest_metrics.get("annualized_return")),
            "max_drawdown": _safe_float(backtest_metrics.get("max_drawdown")),
            "avg_turnover": _safe_float(backtest_metrics.get("avg_turnover")),
            "final_equity": _safe_float(paper_summary.get("final_equity")),
            "fill_count": _safe_float(paper_summary.get("fill_count")),
        }

    def _replace_relations(
        self,
        connection: sqlite3.Connection,
        *,
        parent_manifest_path: str,
        relation_type: str,
        child_manifest_paths: Iterable[str],
    ) -> None:
        connection.execute(
            "DELETE FROM run_relations WHERE parent_manifest_path = ? AND relation_type = ?",
            (parent_manifest_path, relation_type),
        )
        rows = [
            (parent_manifest_path, child_manifest_path, relation_type, ordinal)
            for ordinal, child_manifest_path in enumerate(child_manifest_paths)
        ]
        if rows:
            connection.executemany(
                """
                INSERT INTO run_relations (
                    parent_manifest_path,
                    child_manifest_path,
                    relation_type,
                    ordinal
                ) VALUES (?, ?, ?, ?)
                """,
                rows,
            )

    def _replace_workflow_detail(
        self,
        connection: sqlite3.Connection,
        *,
        manifest_path: str,
        structured_artifact_paths: dict[str, str],
    ) -> None:
        connection.execute("DELETE FROM run_series WHERE manifest_path = ?", (manifest_path,))
        connection.execute("DELETE FROM run_trades WHERE manifest_path = ?", (manifest_path,))

        series_rows: list[tuple[str, str, str, float | None]] = []
        for series_name, value_column in (("equity_curve", "equity"), ("period_returns", "returns")):
            frame = _frame_from_parquet(structured_artifact_paths.get(series_name))
            if frame.empty or "ts" not in frame.columns:
                continue
            for row in frame.itertuples(index=False):
                payload = row._asdict()
                series_rows.append(
                    (
                        manifest_path,
                        series_name,
                        _normalize_ts(payload["ts"]),
                        _safe_float(payload.get(value_column)),
                    )
                )
        if series_rows:
            connection.executemany(
                """
                INSERT INTO run_series (
                    manifest_path,
                    series_name,
                    ts,
                    value
                ) VALUES (?, ?, ?, ?)
                """,
                series_rows,
            )

        trade_frame = _frame_from_parquet(structured_artifact_paths.get("trades"))
        if trade_frame.empty:
            return
        trade_rows = []
        for row in trade_frame.itertuples(index=False):
            payload = row._asdict()
            trade_rows.append(
                (
                    manifest_path,
                    _normalize_ts(payload["ts"]),
                    payload.get("symbol"),
                    payload.get("side"),
                    _safe_float(payload.get("previous_weight")),
                    _safe_float(payload.get("target_weight")),
                    _safe_float(payload.get("delta_weight")),
                    _safe_float(payload.get("price")),
                    _safe_float(payload.get("signal")),
                    payload.get("reason"),
                )
            )
        if trade_rows:
            connection.executemany(
                """
                INSERT INTO run_trades (
                    manifest_path,
                    ts,
                    symbol,
                    side,
                    previous_weight,
                    target_weight,
                    delta_weight,
                    price,
                    signal,
                    reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                trade_rows,
            )

    def upsert_run(self, entry: RunRegistryEntry, *, manifest_payload: dict | None = None) -> Path:
        self.ensure_schema()
        record = self._run_record(entry, manifest_payload=manifest_payload)
        columns = list(record)
        placeholders = ", ".join(f":{column}" for column in columns)
        assignments = ", ".join(f"{column}=excluded.{column}" for column in columns if column != "manifest_path")
        relation_type = {
            "experiment_run": "experiment_child",
            "comparison_run": "comparison_child",
        }.get(entry.kind)
        with _SQLITE_WRITE_LOCK:
            with self._connect() as connection:
                connection.execute(
                    f"""
                    INSERT INTO runs ({", ".join(columns)})
                    VALUES ({placeholders})
                    ON CONFLICT(manifest_path) DO UPDATE SET
                        {assignments}
                    """,
                    record,
                )
                if relation_type is not None:
                    self._replace_relations(
                        connection,
                        parent_manifest_path=entry.manifest_path,
                        relation_type=relation_type,
                        child_manifest_paths=entry.child_manifest_paths,
                    )
                if entry.kind == "workflow_run":
                    self._replace_workflow_detail(
                        connection,
                        manifest_path=entry.manifest_path,
                        structured_artifact_paths=entry.structured_artifact_paths,
                    )
        return self.db_path

    def _decode_run_row(self, row: sqlite3.Row, *, include_manifest: bool = False) -> dict[str, object]:
        payload = dict(row)
        payload["backtest_metrics"] = _json_loads(payload.pop("backtest_metrics_json"), default={})
        payload["backtest_attribution"] = _json_loads(payload.pop("backtest_attribution_json"), default={})
        payload["paper_summary"] = _json_loads(payload.pop("paper_summary_json"), default={})
        payload["structured_artifact_paths"] = _json_loads(payload.pop("structured_artifact_paths_json"), default={})
        payload["child_manifest_paths"] = _json_loads(payload.pop("child_manifest_paths_json"), default=[])
        manifest_json = payload.pop("manifest_json", None)
        if include_manifest and manifest_json:
            payload["manifest"] = _json_loads(manifest_json, default={})
        return payload

    def load_runs(
        self,
        *,
        kind: str | None = None,
        search: str | None = None,
        strategy_type: str | None = None,
        limit: int | None = None,
        offset: int = 0,
        sort_by: str = "generated_at",
        sort_order: str = "desc",
    ) -> list[dict[str, object]]:
        self.ensure_schema()
        allowed_sorts = {
            "generated_at": "r.generated_at",
            "sharpe": "r.sharpe",
            "cumulative_return": "r.cumulative_return",
            "annualized_return": "r.annualized_return",
            "max_drawdown": "r.max_drawdown",
            "avg_turnover": "r.avg_turnover",
            "final_equity": "r.final_equity",
            "name": "r.name",
        }
        order_column = allowed_sorts.get(sort_by, "r.generated_at")
        order_direction = "ASC" if sort_order.lower() == "asc" else "DESC"
        clauses = []
        params: list[object] = []
        if kind is not None:
            clauses.append("r.kind = ?")
            params.append(kind)
        if strategy_type is not None:
            clauses.append("r.strategy_type = ?")
            params.append(strategy_type)
        if search:
            pattern = f"%{search.lower()}%"
            clauses.append(
                """
                (
                    LOWER(COALESCE(r.name, '')) LIKE ?
                    OR LOWER(COALESCE(r.strategy_name, '')) LIKE ?
                    OR LOWER(COALESCE(r.signal_name, '')) LIKE ?
                    OR LOWER(COALESCE(r.strategy_type, '')) LIKE ?
                    OR LOWER(COALESCE(r.variant_id, '')) LIKE ?
                )
                """
            )
            params.extend([pattern, pattern, pattern, pattern, pattern])
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        limit_sql = ""
        if limit is not None:
            limit_sql = "LIMIT ? OFFSET ?"
            params.extend([int(limit), int(offset)])
        query = f"""
            SELECT
                r.*,
                (
                    SELECT COUNT(*)
                    FROM run_relations rel
                    WHERE rel.parent_manifest_path = r.manifest_path
                ) AS child_run_count,
                (
                    SELECT COUNT(*)
                    FROM run_trades trade
                    WHERE trade.manifest_path = r.manifest_path
                ) AS trade_count
            FROM runs r
            {where_sql}
            ORDER BY {order_column} {order_direction}, r.generated_at DESC
            {limit_sql}
        """
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._decode_run_row(row) for row in rows]

    def load_run(self, manifest_path: str) -> dict[str, object] | None:
        self.ensure_schema()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    r.*,
                    (
                        SELECT COUNT(*)
                        FROM run_relations rel
                        WHERE rel.parent_manifest_path = r.manifest_path
                    ) AS child_run_count,
                    (
                        SELECT COUNT(*)
                        FROM run_trades trade
                        WHERE trade.manifest_path = r.manifest_path
                    ) AS trade_count
                FROM runs r
                WHERE r.manifest_path = ?
                """,
                (manifest_path,),
            ).fetchone()
        if row is None:
            return None
        return self._decode_run_row(row)

    def load_manifest(self, manifest_path: str) -> dict[str, object] | None:
        run = self.load_run(manifest_path)
        if run is None:
            return None
        self.ensure_schema()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT manifest_json FROM runs WHERE manifest_path = ?",
                (manifest_path,),
            ).fetchone()
        if row is None or not row["manifest_json"]:
            return None
        return _json_loads(row["manifest_json"], default={})

    def load_children(self, parent_manifest_path: str) -> list[dict[str, object]]:
        self.ensure_schema()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT child_manifest_path, relation_type, ordinal
                FROM run_relations
                WHERE parent_manifest_path = ?
                ORDER BY ordinal ASC
                """,
                (parent_manifest_path,),
            ).fetchall()
        return [dict(row) for row in rows]

    def load_series(self, manifest_path: str, series_name: str, *, limit: int | None = None) -> list[dict[str, object]]:
        self.ensure_schema()
        params: list[object] = [manifest_path, series_name]
        limit_sql = ""
        if limit is not None:
            limit_sql = "LIMIT ?"
            params.append(int(limit))
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT ts, value
                FROM (
                    SELECT ts, value
                    FROM run_series
                    WHERE manifest_path = ? AND series_name = ?
                    ORDER BY ts DESC
                    {limit_sql}
                ) AS tail
                ORDER BY ts ASC
                """,
                params,
            ).fetchall()
        value_key = "equity" if series_name == "equity_curve" else "returns"
        return [{"ts": row["ts"], value_key: row["value"]} for row in rows]

    def load_trades(self, manifest_path: str, *, limit: int | None = None) -> list[dict[str, object]]:
        self.ensure_schema()
        params: list[object] = [manifest_path]
        limit_sql = ""
        if limit is not None:
            limit_sql = "LIMIT ?"
            params.append(int(limit))
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    ts,
                    symbol,
                    side,
                    previous_weight,
                    target_weight,
                    delta_weight,
                    price,
                    signal,
                    reason
                FROM (
                    SELECT
                        ts,
                        symbol,
                        side,
                        previous_weight,
                        target_weight,
                        delta_weight,
                        price,
                        signal,
                        reason
                    FROM run_trades
                    WHERE manifest_path = ?
                    ORDER BY ts DESC, id DESC
                    {limit_sql}
                ) AS tail
                ORDER BY ts ASC
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]
