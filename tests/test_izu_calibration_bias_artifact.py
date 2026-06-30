from pathlib import Path
import subprocess
import sys


def test_calibration_bias_report_generator_writes_markdown(tmp_path: Path) -> None:
    output = tmp_path / "izu_calibration_bias.md"

    subprocess.run(
        [
            sys.executable,
            "scripts/generate_izu_calibration_bias_report.py",
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
    assert "# Virtual Izu calibration-bias stress report" in rendered
    assert "easy_clip_bias" in rendered
    assert "south_optimistic_gradient" in rendered
    assert "south_pessimistic_gradient" in rendered
    assert "easy_clip_plus_gradient_mismatch" in rendered
    assert "unbiased unique top" in rendered
    assert "biased unique top" in rendered
