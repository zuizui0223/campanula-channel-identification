"""Audit occurrence, environment, and photo evidence before scenario use.

This command produces a coverage report only. It does not fit a distribution
model, infer pollination effectiveness, or convert non-detection into absence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from channel_id.public_evidence import (
    load_environment,
    load_island_buffers,
    load_occurrences,
    load_photo_annotations,
    public_evidence_report,
    write_public_observation_templates,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument("--write-templates", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.write_templates is not None:
        if args.input_dir is not None:
            raise SystemExit("--write-templates cannot be combined with --input-dir")
        for path in write_public_observation_templates(args.write_templates):
            print(path)
        return
    if args.input_dir is None or args.output is None:
        raise SystemExit("--input-dir and --output are required for an audit")
    try:
        report = public_evidence_report(
            occurrences=load_occurrences(args.input_dir / "occurrences.csv"),
            buffers=load_island_buffers(args.input_dir / "island_buffers.csv"),
            photos=load_photo_annotations(args.input_dir / "photo_spot_annotations.csv"),
            environment=load_environment(args.input_dir / "environment.csv"),
        )
    except (OSError, ValueError, KeyError) as error:
        raise SystemExit(str(error)) from error
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
