from pathlib import Path

from strategy_lab.data.settings import default_settings, load_settings


def test_default_storage_paths_live_under_repository_root() -> None:
    repository_root = Path(__file__).resolve().parents[1]

    settings = default_settings()

    assert settings.storage.root_dir == repository_root / "data"
    assert settings.storage.cache_dir == repository_root / "data" / "cache"
    assert settings.storage.registry_db_path == repository_root / "data" / "cache" / "_registry" / "runs.sqlite"


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
  cache_dir: data/cache/binance-recent1y
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(config_path)
    defaults = default_settings()

    assert settings.storage.root_dir == defaults.storage.root_dir
    assert settings.storage.normalized_dir == defaults.storage.normalized_dir
    assert settings.storage.cache_dir == defaults.storage.cache_dir
    assert settings.storage.registry_db_path == defaults.storage.registry_db_path


def test_explicit_local_relative_storage_resolves_under_repository_root(tmp_path: Path) -> None:
    config_path = tmp_path / "app.yaml"
    config_path.write_text(
        """
project:
  name: local
storage:
  shared: false
  root_dir: data
  raw_dir: data/raw
  normalized_dir: data/normalized
  features_dir: data/features
  cache_dir: data/cache
""".strip(),
        encoding="utf-8",
    )
    repository_root = Path(__file__).resolve().parents[1]

    settings = load_settings(config_path)

    assert settings.storage.root_dir == repository_root / "data"
    assert settings.storage.raw_dir == repository_root / "data" / "raw"
    assert settings.storage.normalized_dir == repository_root / "data" / "normalized"
    assert settings.storage.features_dir == repository_root / "data" / "features"
    assert settings.storage.cache_dir == repository_root / "data" / "cache"
    assert settings.storage.registry_db_path == repository_root / "data" / "cache" / "_registry" / "runs.sqlite"


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
  cache_dir: {tmp_path / "cache"}
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(config_path)

    assert settings.storage.root_dir == tmp_path / "data"
    assert settings.storage.cache_dir == tmp_path / "cache"
    assert settings.storage.registry_db_path == tmp_path / "cache" / "_registry" / "runs.sqlite"
