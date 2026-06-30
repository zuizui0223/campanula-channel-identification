from pathlib import Path
import subprocess
import sys


def test_counterfactual_cli_writes_and_runs_synthetic_example(tmp_path: Path) -> None:
    config = tmp_path / "example.json"
    subprocess.run(
        [
            sys.executable,
            "scripts/run_two_breakpoint_counterfactual.py",
            "--write-example-config",
            str(config),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    output = tmp_path / "counterfactual.md"
    subprocess.run(
        [
            sys.executable,
            "scripts/run_two_breakpoint_counterfactual.py",
            "--config",
            str(config),
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    report = output.read_text(encoding="utf-8")
    assert "# Two-breakpoint counterfactual sensitivity comparison" in report
    assert "ardens_replacement_loss" in report
    assert "small_bee_substitution" in report
    assert "not a visit rate" in report
