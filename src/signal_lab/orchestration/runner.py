from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import subprocess

import pandas as pd

from signal_lab.backtest import CrossSectionalBacktester, PortfolioBacktester, compute_backtest_attribution
from signal_lab.data import DataIngestionService, DataLakeLayout, DatasetKind
from signal_lab.execution import PaperBroker, PaperTradingSession
from signal_lab.experiments.registry import RunRegistry, RunRegistryEntry
from signal_lab.features import FeatureBuilder
from signal_lab.orchestration.models import StrategyRunArtifacts, StrategyWorkflowConfig
from signal_lab.orchestration.panels import MultiFactorUniversePanels, UniversePanels, load_multi_factor_panels, load_universe_panels
from signal_lab.orchestration.state import IncrementalStateStore
from signal_lab.portfolio import RiskManager
from signal_lab.reporting import render_backtest_report, render_factor_report, render_paper_trading_report
from signal_lab.research import FactorResearchLab
from signal_lab.strategies import create_strategy


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


def _frame_with_ts(frame: pd.DataFrame | pd.Series, value_name: str | None = None) -> pd.DataFrame:
    if isinstance(frame, pd.Series):
        output = frame.rename(value_name or frame.name or "value").to_frame()
    else:
        output = frame.copy()
    index_name = output.index.name or "ts"
    return output.reset_index().rename(columns={index_name: "ts"})


def _build_trade_events(
    *,
    weights: pd.DataFrame,
    price_frame: pd.DataFrame,
    signal_frame: pd.DataFrame,
) -> pd.DataFrame:
    if weights.empty:
        return pd.DataFrame(
            columns=[
                "ts",
                "symbol",
                "side",
                "previous_weight",
                "target_weight",
                "delta_weight",
                "price",
                "signal",
                "reason",
            ]
        )

    aligned_prices = price_frame.reindex_like(weights)
    aligned_signals = signal_frame.reindex_like(weights)
    previous = weights.shift(1).fillna(0.0)
    delta = weights.fillna(0.0) - previous
    rows: list[dict[str, object]] = []
    for ts in delta.index:
        for symbol, delta_weight in delta.loc[ts].dropna().items():
            if abs(float(delta_weight)) < 1e-12:
                continue
            prior = float(previous.loc[ts, symbol])
            target = float(weights.loc[ts, symbol])
            if delta_weight > 0:
                reason = "increase_long" if target > 0 else "reduce_short"
                side = "buy"
            else:
                reason = "increase_short" if target < 0 else "reduce_long"
                side = "sell"
            rows.append(
                {
                    "ts": ts,
                    "symbol": symbol,
                    "side": side,
                    "previous_weight": prior,
                    "target_weight": target,
                    "delta_weight": float(delta_weight),
                    "price": float(aligned_prices.loc[ts, symbol]) if pd.notna(aligned_prices.loc[ts, symbol]) else None,
                    "signal": float(aligned_signals.loc[ts, symbol]) if pd.notna(aligned_signals.loc[ts, symbol]) else None,
                    "reason": reason,
                }
            )
    return pd.DataFrame(rows)


def _write_structured_artifacts(
    *,
    artifacts_dir: Path,
    signal_frame: pd.DataFrame,
    price_frame: pd.DataFrame,
    weights: pd.DataFrame | None,
    backtest,
    backtest_metrics: dict[str, float],
    backtest_attribution: dict[str, float | str | None],
) -> dict[str, str]:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}

    def _write_parquet(name: str, frame: pd.DataFrame | pd.Series, value_name: str | None = None) -> None:
        path = artifacts_dir / f"{name}.parquet"
        _frame_with_ts(frame, value_name=value_name).to_parquet(path, index=False)
        paths[name] = str(path)

    _write_parquet("signals", signal_frame)
    _write_parquet("prices", price_frame)
    if weights is not None:
        _write_parquet("weights", weights)
        trades = _build_trade_events(weights=weights, price_frame=price_frame, signal_frame=signal_frame)
        trade_path = artifacts_dir / "trades.parquet"
        trades.to_parquet(trade_path, index=False)
        paths["trades"] = str(trade_path)

    if backtest is not None:
        _write_parquet("equity_curve", backtest.equity_curve, value_name="equity")
        _write_parquet("period_returns", backtest.period_returns, value_name="returns")
        _write_parquet("turnover", backtest.turnover, value_name="turnover")
        _write_parquet("trading_costs", backtest.trading_costs, value_name="trading_costs")
        _write_parquet("funding_costs", backtest.funding_costs, value_name="funding_costs")

    metrics_path = artifacts_dir / "metrics.json"
    metrics_path.write_text(
        json.dumps(
            {
                "backtest_metrics": backtest_metrics,
                "backtest_attribution": backtest_attribution,
            },
            indent=2,
            sort_keys=True,
            default=str,
        ),
        encoding="utf-8",
    )
    paths["metrics"] = str(metrics_path)
    return paths


@dataclass(slots=True)
class StrategyRunner:
    layout: DataLakeLayout
    builder: FeatureBuilder
    ingestion: DataIngestionService = field(init=False)
    state_store: IncrementalStateStore = field(init=False)

    def __post_init__(self) -> None:
        self.ingestion = DataIngestionService(self.layout)
        self.state_store = IncrementalStateStore(self.layout.root_dir)

    def _resolve_since(self, config: StrategyWorkflowConfig, *, dataset: DatasetKind, symbol: str) -> datetime | None:
        explicit = config.refresh.since
        if explicit:
            return datetime.fromisoformat(explicit.replace("Z", "+00:00"))
        if not config.refresh.incremental:
            return None
        return self.state_store.resolve_since(
            dataset=dataset,
            exchange=config.strategy.exchange,
            symbol=symbol,
            market_type=config.strategy.market_type,
            timeframe=config.refresh.timeframe,
            overlap_bars=config.refresh.overlap_bars,
        )

    def _record_refresh(self, *, config: StrategyWorkflowConfig, dataset: DatasetKind, symbol: str, result: dict[str, object]) -> None:
        self.state_store.update_checkpoint(
            dataset=dataset,
            exchange=config.strategy.exchange,
            symbol=symbol,
            market_type=config.strategy.market_type,
            timeframe=config.refresh.timeframe,
            last_ts=result["last_ts"],
            rows=int(result["rows"]),
            raw_path=str(result["raw"]),
            normalized_path=str(result["normalized"]),
        )

    def refresh_data(self, config: StrategyWorkflowConfig) -> dict[str, dict[str, dict[str, object]]]:
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
            )
            symbol_artifacts["ohlcv"] = ohlcv
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
                liquidations = self.ingestion.refresh_historical_liquidations(
                    exchange=config.strategy.exchange,
                    symbol=symbol,
                    timeframe="4h",
                    since=self._resolve_since(config, dataset=DatasetKind.LIQUIDATIONS, symbol=symbol),
                    limit=1000,
                )
                symbol_artifacts["funding_rates"] = funding
                symbol_artifacts["open_interest"] = open_interest
                symbol_artifacts["basis_or_premium"] = basis
                symbol_artifacts["historical_liquidations"] = liquidations
                self._record_refresh(config=config, dataset=DatasetKind.FUNDING_RATES, symbol=symbol, result=funding)
                self._record_refresh(config=config, dataset=DatasetKind.OPEN_INTEREST, symbol=symbol, result=open_interest)
                self._record_refresh(config=config, dataset=DatasetKind.BASIS, symbol=symbol, result=basis)
                if liquidations.get("rows"):
                    self._record_refresh(config=config, dataset=DatasetKind.LIQUIDATIONS, symbol=symbol, result=liquidations)

            artifacts[symbol] = symbol_artifacts
        return artifacts

    def build_features(self, config: StrategyWorkflowConfig) -> dict[str, dict[str, dict[str, str]]]:
        artifacts: dict[str, dict[str, dict[str, str]]] = {}
        factor_names: list[str] | None = None
        if config.strategy.signal_type != "factor":
            factor_names = create_strategy(config.strategy.signal_type, config.strategy.strategy_options).required_factors()
        elif config.strategy.factor is not None:
            factor_names = [config.strategy.factor]
        for symbol in config.strategy.symbols:
            bundle = self.builder.build_symbol_features(
                exchange=config.strategy.exchange,
                symbol=symbol,
                market_type=config.strategy.market_type,
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
                benchmark_symbol=config.strategy.benchmark_symbol,
            )
        return artifacts

    def _prepare_signal_inputs(
        self,
        config: StrategyWorkflowConfig,
    ) -> tuple[str, str, object, object, object]:
        if config.strategy.signal_type != "factor":
            strategy = create_strategy(config.strategy.signal_type, config.strategy.strategy_options)
            panels = load_multi_factor_panels(
                builder=self.builder,
                exchange=config.strategy.exchange,
                symbols=config.strategy.symbols,
                market_type=config.strategy.market_type,
                factor_names=strategy.required_factors(),
                benchmark_symbol=config.strategy.benchmark_symbol,
            )
            signal_frame = strategy.build_signal_frame(panels.factors)
            target_weights = strategy.build_weights(
                signal_frame,
                panels.liquidation_features,
                price_frame=panels.price,
                factors=panels.factors,
            )
            return strategy.signal_name, strategy.version(), panels, signal_frame, target_weights

        panels = load_universe_panels(
            builder=self.builder,
            exchange=config.strategy.exchange,
            symbols=config.strategy.symbols,
            market_type=config.strategy.market_type,
            factor_name=config.strategy.signal_name,
            benchmark_symbol=config.strategy.benchmark_symbol,
        )
        return config.strategy.signal_name, self.builder.registry.get(config.strategy.signal_name).version(), panels, panels.factor, None

    def run_backtest(
        self,
        config: StrategyWorkflowConfig,
        *,
        panels: UniversePanels | MultiFactorUniversePanels,
        signal_frame: pd.DataFrame,
        target_weights: pd.DataFrame | None,
    ):
        if target_weights is None:
            return CrossSectionalBacktester(assumptions=config.execution).run(
                factor_frame=signal_frame,
                price_frame=panels.price,
                dollar_volume=panels.dollar_volume,
                funding_rate=panels.funding_rate,
            )
        return PortfolioBacktester(assumptions=config.execution).run(
            target_weights=target_weights,
            price_frame=panels.price,
            dollar_volume=panels.dollar_volume,
            funding_rate=panels.funding_rate,
        )

    def run(self, config: StrategyWorkflowConfig) -> StrategyRunArtifacts:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        refresh_artifacts = self.refresh_data(config)
        feature_artifacts = self.build_features(config)
        signal_name, signal_version, panels, signal_frame, target_weights = self._prepare_signal_inputs(config)

        factor_report_path: Path | None = None
        backtest_report_path: Path | None = None
        paper_report_path: Path | None = None
        backtest_metrics: dict[str, float] = {}
        backtest_attribution: dict[str, float | str | None] = {}
        paper_summary: dict[str, float] = {}
        backtest = None
        effective_weights = target_weights

        if config.run_factor_report:
            diagnostics = FactorResearchLab().evaluate(signal_frame, panels.price)
            report = render_factor_report(signal_name, diagnostics)
            factor_report_path = self.layout.reports_dir / "runs" / config.strategy.name / run_id / "factor_report.md"
            factor_report_path.parent.mkdir(parents=True, exist_ok=True)
            factor_report_path.write_text(report, encoding="utf-8")

        if config.run_backtest:
            backtest = self.run_backtest(
                config,
                panels=panels,
                signal_frame=signal_frame,
                target_weights=target_weights,
            )
            effective_weights = backtest.weights
            backtest_metrics = backtest.metrics
            backtest_attribution = compute_backtest_attribution(
                weights=backtest.weights,
                price_frame=panels.price,
                funding_rate=panels.funding_rate,
                fee_bps=config.execution.fee_bps,
                slippage_bps=config.execution.slippage_bps,
            )
            report = render_backtest_report(signal_name, backtest)
            backtest_report_path = self.layout.reports_dir / "runs" / config.strategy.name / run_id / "backtest_report.md"
            backtest_report_path.parent.mkdir(parents=True, exist_ok=True)
            backtest_report_path.write_text(report, encoding="utf-8")

        structured_artifacts = _write_structured_artifacts(
            artifacts_dir=self.layout.reports_dir / "runs" / config.strategy.name / run_id / "artifacts",
            signal_frame=signal_frame,
            price_frame=panels.price,
            weights=effective_weights,
            backtest=backtest,
            backtest_metrics=backtest_metrics,
            backtest_attribution=backtest_attribution,
        )

        if config.run_paper_trade:
            paper_target_weights = target_weights
            if paper_target_weights is None:
                strategy = CrossSectionalBacktester(assumptions=config.execution)
                paper_target_weights = strategy.build_weights(signal_frame)
            session = PaperTradingSession(
                broker=PaperBroker(
                    starting_cash=config.execution.starting_cash,
                    fee_bps=config.execution.fee_bps,
                    slippage_bps=config.execution.slippage_bps,
                ),
                risk_manager=RiskManager(config.risk),
            )
            paper = session.run(
                target_weights=paper_target_weights,
                price_frame=panels.price,
                dollar_volume=panels.dollar_volume,
                funding_rate=panels.funding_rate,
            )
            paper_summary = {
                "final_equity": float(paper.equity_curve.iloc[-1]) if not paper.equity_curve.empty else 0.0,
                "fill_count": float(len(paper.fills)),
                "funding_cashflow": float(paper.funding_cashflows.sum()) if not paper.funding_cashflows.empty else 0.0,
            }
            report = render_paper_trading_report(signal_name, paper)
            paper_report_path = self.layout.reports_dir / "runs" / config.strategy.name / run_id / "paper_report.md"
            paper_report_path.parent.mkdir(parents=True, exist_ok=True)
            paper_report_path.write_text(report, encoding="utf-8")

        manifest_payload = {
            "run_id": run_id,
            "strategy": asdict(config.strategy),
            "refresh": asdict(config.refresh),
            "execution": asdict(config.execution),
            "risk": asdict(config.risk),
            "schedule": asdict(config.schedule),
            "metadata": config.metadata,
            "config_hash": config.metadata.get("config_hash") or _hash_payload(asdict(config)),
            "git_sha": _git_sha(),
            "data_snapshot_id": _hash_payload({"refresh": refresh_artifacts, "features": feature_artifacts}),
            "refresh_artifacts": refresh_artifacts,
            "feature_artifacts": feature_artifacts,
            "structured_artifacts": structured_artifacts,
            "signal_name": signal_name,
            "signal_type": config.strategy.signal_type,
            "signal_version": signal_version,
            "factor_report_path": str(factor_report_path) if factor_report_path else None,
            "backtest_report_path": str(backtest_report_path) if backtest_report_path else None,
            "paper_report_path": str(paper_report_path) if paper_report_path else None,
            "backtest_metrics": backtest_metrics,
            "backtest_attribution": backtest_attribution,
            "paper_summary": paper_summary,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        manifest_path = self.layout.reports_dir / "runs" / config.strategy.name / run_id / "run_manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest_payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
        RunRegistry(self.layout.reports_dir).append(
            RunRegistryEntry(
                kind="workflow_run",
                name=config.strategy.name,
                run_id=run_id,
                generated_at=str(manifest_payload["generated_at"]),
                manifest_path=str(manifest_path),
                primary_report_path=str(backtest_report_path or factor_report_path or paper_report_path) if (backtest_report_path or factor_report_path or paper_report_path) else None,
                factor_report_path=str(factor_report_path) if factor_report_path else None,
                backtest_report_path=str(backtest_report_path) if backtest_report_path else None,
                paper_report_path=str(paper_report_path) if paper_report_path else None,
                strategy_name=config.strategy.name,
                signal_name=signal_name,
                signal_type=config.strategy.signal_type,
                variant_id=config.metadata.get("variant_id"),
                config_hash=str(manifest_payload["config_hash"]),
                git_sha=manifest_payload["git_sha"],
                data_snapshot_id=str(manifest_payload["data_snapshot_id"]),
                backtest_metrics=backtest_metrics,
                backtest_attribution=backtest_attribution,
                paper_summary=paper_summary,
                structured_artifact_paths=structured_artifacts,
            )
        )

        return StrategyRunArtifacts(
            run_id=run_id,
            factor_report_path=str(factor_report_path) if factor_report_path else None,
            backtest_report_path=str(backtest_report_path) if backtest_report_path else None,
            paper_report_path=str(paper_report_path) if paper_report_path else None,
            manifest_path=str(manifest_path),
            backtest_attribution=backtest_attribution or None,
        )
