from pathlib import Path

from strategy_lab.config.settings import default_settings, load_settings


def test_relative_profile_storage_converges_to_shared_paths(tmp_path: Path) -> None:
    config_path = tmp_path / "app.yaml"
    config_path.write_text(
        """
project:
  name: shared
storage:
  root_dir: data/binance-recent1y
  raw_dir: data/binance-recent1y/raw
  normalized_dir: data/binance-recent1y/normalized
  features_dir: data/binance-recent1y/features
  reports_dir: reports/binance-recent1y
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(config_path)
    defaults = default_settings()

    assert settings.storage.root_dir == defaults.storage.root_dir
    assert settings.storage.normalized_dir == defaults.storage.normalized_dir
    assert settings.storage.reports_dir == defaults.storage.reports_dir
    assert settings.storage.registry_db_path == defaults.storage.registry_db_path


def test_absolute_storage_paths_remain_isolated_for_tests(tmp_path: Path) -> None:
    config_path = tmp_path / "app.yaml"
    config_path.write_text(
        f"""
project:
  name: isolated
storage:
  root_dir: {tmp_path / "data"}
  raw_dir: {tmp_path / "data" / "raw"}
  normalized_dir: {tmp_path / "data" / "normalized"}
  features_dir: {tmp_path / "data" / "features"}
  reports_dir: {tmp_path / "reports"}
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(config_path)

    assert settings.storage.root_dir == tmp_path / "data"
    assert settings.storage.reports_dir == tmp_path / "reports"
    assert settings.storage.registry_db_path == tmp_path / "reports" / "_registry" / "runs.sqlite"
