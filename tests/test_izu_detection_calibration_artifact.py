from pathlib import Path
import subprocess
import sys


def test_detection_calibration_report_generator_writes_markdown(tmp_path: Path) -> None:
    output = tmp_path / "izu_detection_calibration.md"

    subprocess.run(
        [
            sys.executable,
            "scripts/generate_izu_detection_calibration_report.py",
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
    assert "# Virtual Izu finite detection-calibration report" in rendered
    assert "wind_light_detection_loss" in rendered
    assert "combined_field_stress" in rendered
    assert "reference visits/site" in rendered
    assert "calibrated unique top" in rendered
