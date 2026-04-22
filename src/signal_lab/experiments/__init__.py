from .config import load_experiment_config
from .models import ExperimentArtifacts, ExperimentConfig, ExperimentEntry
from .registry import RunRegistry, RunRegistryEntry

__all__ = [
    "ExperimentArtifacts",
    "ExperimentConfig",
    "ExperimentEntry",
    "ExperimentRunner",
    "RunRegistry",
    "RunRegistryEntry",
    "load_experiment_config",
]


def __getattr__(name: str):
    if name == "ExperimentRunner":
        from .runner import ExperimentRunner

        return ExperimentRunner
    raise AttributeError(name)
