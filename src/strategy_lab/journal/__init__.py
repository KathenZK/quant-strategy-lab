from .models import ExperimentArtifacts, ExperimentConfig, ExperimentEntry
from .registry import BacktestJournal, BacktestJournalEntry, RunRegistry, RunRegistryEntry

__all__ = [
    "ExperimentArtifacts",
    "ExperimentConfig",
    "ExperimentEntry",
    "ExperimentRunner",
    "BacktestJournal",
    "BacktestJournalEntry",
    "RunRegistry",
    "RunRegistryEntry",
    "load_experiment_config",
]


def __getattr__(name: str):
    if name == "load_experiment_config":
        from .config import load_experiment_config

        return load_experiment_config
    if name == "ExperimentRunner":
        from .runner import ExperimentRunner

        return ExperimentRunner
    raise AttributeError(name)
