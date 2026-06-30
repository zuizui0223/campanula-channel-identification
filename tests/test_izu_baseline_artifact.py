from pathlib import Path
import subprocess
import sys


def test_virtual_baseline_generator_writes_markdown(tmp_path: Path) -> None:
    output = tmp_path / "izu_virtual_baseline.md"

    subprocess.run(
        [
            sys.executable,
            "scripts/generate_izu_sensitivity_baseline.py",
            "--replicates",
            "1",
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    rendered = output.read_text(encoding="utf-8")
    assert "# Virtual Izu sensitivity baseline" in rendered
    assert "Replicates per plan × world × analysis mode: `1`" in rendered
    assert "null_environment_gradient" in rendered
    assert "visit_assurance_environment_gradient" in rendered
    assert "camera_heavy" in rendered
    assert "genetic_heavy" in rendered
    assert "flat_environment" in rendered
