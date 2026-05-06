from pathlib import Path

from strategy_lab.journal.batches import load_workflow_batch_config
from strategy_lab.journal.comparison import load_strategy_comparison
from strategy_lab.journal import load_experiment_config


def test_load_workflow_batch_config_resolves_relative_paths(tmp_path: Path) -> None:
    trend = tmp_path / "trend.yaml"
    trend.write_text("strategy:\n  name: trend\n", encoding="utf-8")
    crowding = tmp_path / "crowding.yaml"
    crowding.write_text("strategy:\n  name: crowding\n", encoding="utf-8")

    config_path = tmp_path / "batch.yaml"
    config_path.write_text(
        """
batch:
  name: shared_batch
  description: Shared workflow batch config.
  workflow_configs:
    - trend.yaml
    - crowding.yaml
""".strip(),
        encoding="utf-8",
    )

    batch = load_workflow_batch_config(config_path)

    assert batch.name == "shared_batch"
    assert batch.description == "Shared workflow batch config."
    assert batch.workflow_configs == [str(trend.resolve()), str(crowding.resolve())]


def test_comparison_loader_accepts_shared_batch_section(tmp_path: Path) -> None:
    trend = tmp_path / "trend.yaml"
    trend.write_text("strategy:\n  name: trend\n", encoding="utf-8")
    crowding = tmp_path / "crowding.yaml"
    crowding.write_text("strategy:\n  name: crowding\n", encoding="utf-8")

    config_path = tmp_path / "comparison-batch.yaml"
    config_path.write_text(
        """
batch:
  name: cmp_batch
  workflow_configs:
    - trend.yaml
    - crowding.yaml
""".strip(),
        encoding="utf-8",
    )

    config = load_strategy_comparison(config_path)

    assert config.name == "cmp_batch"
    assert len(config.workflow_configs) == 2


def test_experiment_loader_accepts_shared_batch_section(tmp_path: Path) -> None:
    trend = tmp_path / "trend.yaml"
    trend.write_text("strategy:\n  name: trend\n", encoding="utf-8")
    crowding = tmp_path / "crowding.yaml"
    crowding.write_text("strategy:\n  name: crowding\n", encoding="utf-8")

    config_path = tmp_path / "experiment-batch.yaml"
    config_path.write_text(
        """
batch:
  name: exp_batch
  workflow_configs:
    - trend.yaml
    - crowding.yaml
""".strip(),
        encoding="utf-8",
    )

    config = load_experiment_config(config_path)

    assert config.name == "exp_batch"
    assert len(config.workflow_configs) == 2
