from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import json

from signal_lab.backtest import CrossSectionalBacktester
from signal_lab.data import DataIngestionService, DataLakeLayout, DatasetKind
from signal_lab.execution import PaperBroker, PaperTradingSession
from signal_lab.features import FeatureBuilder
from signal_lab.orchestration.models import StrategyRunArtifacts, StrategyWorkflowConfig
from signal_lab.orchestration.panels import load_universe_panels
from signal_lab.orchestration.state import IncrementalStateStore
from signal_lab.portfolio import RiskManager
from signal_lab.reporting import render_backtest_report, render_factor_report, render_paper_trading_report
from signal_lab.research import FactorResearchLab


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
                symbol_artifacts["funding_rates"] = funding
                symbol_artifacts["open_interest"] = open_interest
                self._record_refresh(config=config, dataset=DatasetKind.FUNDING_RATES, symbol=symbol, result=funding)
                self._record_refresh(config=config, dataset=DatasetKind.OPEN_INTEREST, symbol=symbol, result=open_interest)

            artifacts[symbol] = symbol_artifacts
        return artifacts

    def build_features(self, config: StrategyWorkflowConfig) -> dict[str, dict[str, dict[str, str]]]:
        artifacts: dict[str, dict[str, dict[str, str]]] = {}
        for symbol in config.strategy.symbols:
            bundle = self.builder.build_symbol_features(
                exchange=config.strategy.exchange,
                symbol=symbol,
                market_type=config.strategy.market_type,
                benchmark_symbol=config.strategy.benchmark_symbol,
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

    def run(self, config: StrategyWorkflowConfig) -> StrategyRunArtifacts:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        refresh_artifacts = self.refresh_data(config)
        feature_artifacts = self.build_features(config)
        panels = load_universe_panels(
            builder=self.builder,
            exchange=config.strategy.exchange,
            symbols=config.strategy.symbols,
            market_type=config.strategy.market_type,
            factor_name=config.strategy.factor,
            benchmark_symbol=config.strategy.benchmark_symbol,
        )

        factor_report_path: Path | None = None
        backtest_report_path: Path | None = None
        paper_report_path: Path | None = None
        backtest_metrics: dict[str, float] = {}
        paper_summary: dict[str, float] = {}

        if config.run_factor_report:
            diagnostics = FactorResearchLab().evaluate(panels.factor, panels.price)
            report = render_factor_report(config.strategy.factor, diagnostics)
            factor_report_path = self.layout.reports_dir / "runs" / config.strategy.name / run_id / "factor_report.md"
            factor_report_path.parent.mkdir(parents=True, exist_ok=True)
            factor_report_path.write_text(report, encoding="utf-8")

        if config.run_backtest:
            backtester = CrossSectionalBacktester(assumptions=config.execution)
            backtest = backtester.run(
                factor_frame=panels.factor,
                price_frame=panels.price,
                dollar_volume=panels.dollar_volume,
                funding_rate=panels.funding_rate,
            )
            backtest_metrics = backtest.metrics
            report = render_backtest_report(config.strategy.factor, backtest)
            backtest_report_path = self.layout.reports_dir / "runs" / config.strategy.name / run_id / "backtest_report.md"
            backtest_report_path.parent.mkdir(parents=True, exist_ok=True)
            backtest_report_path.write_text(report, encoding="utf-8")

        if config.run_paper_trade:
            strategy = CrossSectionalBacktester(assumptions=config.execution)
            target_weights = strategy.build_weights(panels.factor)
            session = PaperTradingSession(
                broker=PaperBroker(
                    starting_cash=config.execution.starting_cash,
                    fee_bps=config.execution.fee_bps,
                    slippage_bps=config.execution.slippage_bps,
                ),
                risk_manager=RiskManager(config.risk),
            )
            paper = session.run(
                target_weights=target_weights,
                price_frame=panels.price,
                dollar_volume=panels.dollar_volume,
                funding_rate=panels.funding_rate,
            )
            paper_summary = {
                "final_equity": float(paper.equity_curve.iloc[-1]) if not paper.equity_curve.empty else 0.0,
                "fill_count": float(len(paper.fills)),
                "funding_cashflow": float(paper.funding_cashflows.sum()) if not paper.funding_cashflows.empty else 0.0,
            }
            report = render_paper_trading_report(config.strategy.factor, paper)
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
            "refresh_artifacts": refresh_artifacts,
            "feature_artifacts": feature_artifacts,
            "factor_version": self.builder.registry.get(config.strategy.factor).version(),
            "factor_report_path": str(factor_report_path) if factor_report_path else None,
            "backtest_report_path": str(backtest_report_path) if backtest_report_path else None,
            "paper_report_path": str(paper_report_path) if paper_report_path else None,
            "backtest_metrics": backtest_metrics,
            "paper_summary": paper_summary,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        manifest_path = self.layout.reports_dir / "runs" / config.strategy.name / run_id / "run_manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest_payload, indent=2, sort_keys=True, default=str), encoding="utf-8")

        return StrategyRunArtifacts(
            run_id=run_id,
            factor_report_path=str(factor_report_path) if factor_report_path else None,
            backtest_report_path=str(backtest_report_path) if backtest_report_path else None,
            paper_report_path=str(paper_report_path) if paper_report_path else None,
            manifest_path=str(manifest_path),
        )
