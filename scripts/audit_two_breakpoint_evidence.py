"""Audit public-evidence records before scenario or counterfactual use.

The script does not fit a pollination model.  It checks whether sources, claims,
and declared scenario constraints preserve provenance, denominator/effort, and
the boundary between observation and sensitivity assumptions.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from channel_id.two_breakpoint_evidence import (
    audit_two_breakpoint_registry_directory,
    evidence_audit_to_dict,
    write_two_breakpoint_registry_templates,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        help="Directory containing sources.csv, claims.csv, and scenario_constraints.csv.",
    )
    parser.add_argument(
        "--write-templates",
        type=Path,
        default=None,
        help="Write blank evidence-registry templates and LLM extraction contract, then exit.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON output path. Defaults to stdout.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.write_templates is not None:
        if args.input_dir is not None:
            raise SystemExit("--write-templates cannot be combined with --input-dir")
        for path in write_two_breakpoint_registry_templates(args.write_templates):
            print(path)
        return
    if args.input_dir is None:
        raise SystemExit("--input-dir is required unless --write-templates is used")
    try:
        report = audit_two_breakpoint_registry_directory(args.input_dir)
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from error
    rendered = json.dumps(evidence_audit_to_dict(report), indent=2, ensure_ascii=False) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
