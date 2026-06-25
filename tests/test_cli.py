from typer.testing import CliRunner

from strategy_lab.data.cli import app


def test_cli_exposes_data_first_commands() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "layout" in result.output
    assert "refresh-symbol" in result.output
    assert "build-ema-cross-quality-dataset" in result.output
    assert "run-strategy" not in result.output
    assert "dashboard" not in result.output
