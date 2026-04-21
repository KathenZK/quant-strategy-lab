from pathlib import Path

from signal_lab.data import DataLakeLayout
from signal_lab.scenarios import seed_trend_mvp_data


def _layout(tmp_path: Path) -> DataLakeLayout:
    return DataLakeLayout(
        root_dir=tmp_path / "data",
        raw_dir=tmp_path / "data" / "raw",
        normalized_dir=tmp_path / "data" / "normalized",
        features_dir=tmp_path / "data" / "features",
        reports_dir=tmp_path / "reports",
    )


def test_seed_trend_mvp_data_writes_required_datasets(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    written = seed_trend_mvp_data(layout)

    assert len(written) == 3
    for datasets in written.values():
        assert "ohlcv" in datasets
        assert "funding_rates" in datasets
        assert "open_interest" in datasets
        assert "basis_or_premium" in datasets
        assert "liquidations" in datasets
