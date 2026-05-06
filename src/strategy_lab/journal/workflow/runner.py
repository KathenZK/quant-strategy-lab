from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import subprocess

from strategy_lab.data import DataIngestionService, DataLakeLayout, DatasetKind
from strategy_lab.journal.registry import BacktestJournal, BacktestJournalEntry
from strategy_lab.data.features import FeatureBuilder
from strategy_lab.fs import atomic_write_path
from strategy_lab.journal.workflow.models import StrategyRunArtifacts, StrategyWorkflowConfig
from strategy_lab.journal.workflow.state import IncrementalStateStore
from strategy_lab.journal.workflow.workflow_service import WorkflowService


def _hash_payload(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _git_sha() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path.cwd(),
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


@dataclass(slots=True)
class StrategyRunner:
    layout: DataLakeLayout
    builder: FeatureBuilder
    ingestion: DataIngestionService = field(init=False)
    state_store: IncrementalStateStore = field(init=False)
    workflow_service: WorkflowService = field(init=False)

    def __post_init__(self) -> None:
        self.ingestion = DataIngestionService(self.layout)
        self.state_store = IncrementalStateStore(self.layout.root_dir)
        self.workflow_service = WorkflowService(self.builder)

    def _resolve_since(
        self,
        config: StrategyWorkflowConfig,
        *,
        dataset: DatasetKind,
        symbol: str,
        timeframe: str | None = None,
    ) -> datetime | None:
        explicit = config.refresh.since
        if explicit:
            return datetime.fromisoformat(explicit.replace("Z", "+00:00"))
        if not config.refresh.incremental:
            return None
        timeframe = config.refresh.timeframe if timeframe is None else timeframe
        return self.state_store.resolve_since(
            dataset=dataset,
            exchange=config.strategy.exchange,
            symbol=symbol,
            market_type=config.strategy.market_type,
            timeframe=timeframe,
            overlap_bars=config.refresh.overlap_bars,
        )

    def _record_refresh(
        self,
        *,
        config: StrategyWorkflowConfig,
        dataset: DatasetKind,
        symbol: str,
        result: dict[str, object],
        timeframe: str | None = None,
    ) -> None:
        timeframe = config.refresh.timeframe if timeframe is None else timeframe
        self.state_store.update_checkpoint(
            dataset=dataset,
            exchange=config.strategy.exchange,
            symbol=symbol,
            market_type=config.strategy.market_type,
            timeframe=timeframe,
            last_ts=result["last_ts"],
            rows=int(result["rows"]),
            raw_path=str(result["raw"]),
            normalized_path=str(result["normalized"]),
        )

    def refresh_data(
        self,
        config: StrategyWorkflowConfig,
        *,
        liquidation_feature_names: list[str] | None = None,
    ) -> dict[str, dict[str, dict[str, object]]]:
        config = self.workflow_service.with_resolved_symbols(config)
        artifacts: dict[str, dict[str, dict[str, object]]] = {}
        if not config.refresh.enabled:
            return artifacts

        for symbol in config.strategy.symbols:
            symbol_artifacts: dict[str, dict[str, object]] = {}
            ohlcv = self.ingestion.refresh_ohlcv(
                exchange=config.strategy.exchange,
                symbol=symbol,
                market_type=config.strategy.market_type,
                timeframe=config.refresh.timeframe,
                since=self._resolve_since(config, dataset=DatasetKind.OHLCV, symbol=symbol),
                limit=config.refresh.limit,
                drop_incomplete=True,
            )
            symbol_artifacts["ohlcv"] = ohlcv
            if ohlcv.get("rows"):
                self._record_refresh(config=config, dataset=DatasetKind.OHLCV, symbol=symbol, result=ohlcv)

            if config.strategy.market_type.value == "perp" and config.refresh.include_derivatives:
                funding = self.ingestion.refresh_funding_rates(
                    exchange=config.strategy.exchange,
                    symbol=symbol,
                    since=self._resolve_since(config, dataset=DatasetKind.FUNDING_RATES, symbol=symbol),
                    limit=config.refresh.limit,
                )
                open_interest = self.ingestion.refresh_open_interest(
                    exchange=config.strategy.exchange,
                    symbol=symbol,
                    timeframe=config.refresh.timeframe,
                    since=self._resolve_since(config, dataset=DatasetKind.OPEN_INTEREST, symbol=symbol),
                    limit=config.refresh.limit,
                )
                basis = self.ingestion.refresh_basis_or_premium(
                    exchange=config.strategy.exchange,
                    symbol=symbol,
                    timeframe=config.refresh.timeframe,
                    since=self._resolve_since(config, dataset=DatasetKind.BASIS, symbol=symbol),
                    limit=config.refresh.limit,
                )
                symbol_artifacts["funding_rates"] = funding
                symbol_artifacts["open_interest"] = open_interest
                symbol_artifacts["basis_or_premium"] = basis
                liquidations = None
                if liquidation_feature_names:
                    liquidations = self.ingestion.refresh_historical_liquidations(
                        exchange=config.strategy.exchange,
                        symbol=symbol,
                        timeframe="4h",
                        since=self._resolve_since(config, dataset=DatasetKind.LIQUIDATIONS, symbol=symbol, timeframe="4h"),
                        limit=1000,
                    )
                    symbol_artifacts["historical_liquidations"] = liquidations
                self._record_refresh(config=config, dataset=DatasetKind.FUNDING_RATES, symbol=symbol, result=funding)
                self._record_refresh(config=config, dataset=DatasetKind.OPEN_INTEREST, symbol=symbol, result=open_interest)
                self._record_refresh(config=config, dataset=DatasetKind.BASIS, symbol=symbol, result=basis)
                if liquidations and liquidations.get("rows"):
                    self._record_refresh(config=config, dataset=DatasetKind.LIQUIDATIONS, symbol=symbol, result=liquidations, timeframe="4h")

            artifacts[symbol] = symbol_artifacts
        return artifacts

    def build_features(self, config: StrategyWorkflowConfig, *, strategy=None) -> dict[str, dict[str, dict[str, str]]]:
        config = self.workflow_service.with_resolved_symbols(config)
        artifacts: dict[str, dict[str, dict[str, str]]] = {}
        factor_names = self.workflow_service.required_factor_names(config, strategy=strategy)
        for symbol in config.strategy.symbols:
            bundle = self.builder.build_symbol_features(
                exchange=config.strategy.exchange,
                symbol=symbol,
                market_type=config.strategy.market_type,
                timeframe=config.refresh.timeframe,
                benchmark_symbol=config.strategy.benchmark_symbol,
                factor_names=factor_names,
            )
            if bundle.empty:
                continue
            artifacts[symbol] = self.builder.persist_bundle(
                bundle,
                exchange=config.strategy.exchange,
                symbol=symbol,
                market_type=config.strategy.market_type,
                timeframe=config.refresh.timeframe,
                benchmark_symbol=config.strategy.benchmark_symbol,
            )
        return artifacts

    def run(self, config: StrategyWorkflowConfig) -> StrategyRunArtifacts:
        config = self.workflow_service.with_resolved_symbols(config)
        strategy = self.workflow_service.strategy_instance(config)
        liquidation_feature_names = strategy.required_liquidation_features() if strategy else []
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        refresh_artifacts = self.refresh_data(config, liquidation_feature_names=liquidation_feature_names)
        feature_artifacts = self.build_features(config, strategy=strategy)
        run_dir = self.layout.reports_dir / "runs" / config.strategy.name / run_id
        execution_result = self.workflow_service.execute(config, run_dir=run_dir, strategy=strategy)

        manifest_payload = {
            "run_id": run_id,
            "strategy": asdict(config.strategy),
            "refresh": asdict(config.refresh),
            "universe": asdict(config.universe),
            "execution": asdict(config.execution),
            "risk": asdict(config.risk),
            "schedule": asdict(config.schedule),
            "metadata": config.metadata,
            "config_hash": config.metadata.get("config_hash") or _hash_payload(asdict(config)),
            "git_sha": _git_sha(),
            "data_snapshot_id": _hash_payload({"refresh": refresh_artifacts, "features": feature_artifacts}),
            "refresh_artifacts": refresh_artifacts,
            "feature_artifacts": feature_artifacts,
            "structured_artifacts": execution_result.structured_artifacts or {},
            "signal_name": execution_result.signal_name,
            "strategy_type": config.strategy.strategy_type,
            "signal_version": execution_result.signal_version,
            "factor_report_path": execution_result.factor_report_path,
            "backtest_report_path": execution_result.backtest_report_path,
            "paper_report_path": execution_result.paper_report_path,
            "backtest_metrics": execution_result.backtest_metrics or {},
            "backtest_attribution": execution_result.backtest_attribution or {},
            "paper_summary": execution_result.paper_summary or {},
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        manifest_path = run_dir / "run_manifest.json"
        manifest_text = json.dumps(manifest_payload, indent=2, sort_keys=True, default=str)
        atomic_write_path(manifest_path, lambda temp_path: temp_path.write_text(manifest_text, encoding="utf-8"))
        BacktestJournal(self.layout.reports_dir, db_path=self.layout.run_registry_db_path).append(
            BacktestJournalEntry(
                kind="workflow_run",
                name=config.strategy.name,
                run_id=run_id,
                generated_at=str(manifest_payload["generated_at"]),
                manifest_path=str(manifest_path),
                primary_report_path=(
                    execution_result.backtest_report_path
                    or execution_result.factor_report_path
                    or execution_result.paper_report_path
                ),
                factor_report_path=execution_result.factor_report_path,
                backtest_report_path=execution_result.backtest_report_path,
                paper_report_path=execution_result.paper_report_path,
                strategy_name=config.strategy.name,
                signal_name=execution_result.signal_name,
                strategy_type=config.strategy.strategy_type,
                variant_id=config.metadata.get("variant_id"),
                config_hash=str(manifest_payload["config_hash"]),
                git_sha=manifest_payload["git_sha"],
                data_snapshot_id=str(manifest_payload["data_snapshot_id"]),
                backtest_metrics=execution_result.backtest_metrics or {},
                backtest_attribution=execution_result.backtest_attribution or {},
                paper_summary=execution_result.paper_summary or {},
                structured_artifact_paths=execution_result.structured_artifacts or {},
            ),
            manifest_payload=manifest_payload,
        )

        return StrategyRunArtifacts(
            run_id=run_id,
            factor_report_path=execution_result.factor_report_path,
            backtest_report_path=execution_result.backtest_report_path,
            paper_report_path=execution_result.paper_report_path,
            manifest_path=str(manifest_path),
            backtest_metrics=execution_result.backtest_metrics or {},
            paper_summary=execution_result.paper_summary or {},
            backtest_attribution=execution_result.backtest_attribution or None,
        )
