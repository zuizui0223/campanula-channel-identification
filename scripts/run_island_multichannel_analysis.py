"""Run the evidence-constrained island multichannel compatibility analysis.

The input is the source-locked, island-level literature table. Optional
guide/spot order constraints must be human-reviewed and source-locatable; the
script does not turn unreviewed photographs into quantitative trait values.

Example:
    python scripts/run_island_multichannel_analysis.py \
      --input data/inoue_literature_island_traits.csv \
      --guide-constraints data/guide_direction_constraints.csv \
      --output-json artifacts/island_multichannel_analysis.json \
      --output-md artifacts/island_multichannel_analysis.md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from channel_id.island_multichannel import (
    EvidenceChannel,
    compare_scenarios,
    load_guide_order_constraints,
    load_island_evidence,
    render_markdown,
)


def _summary_json(results):
    return [
        {
            "scenario": result.scenario.value,
            "draws": result.draws,
            "log_marginal_compatibility": result.log_marginal_compatibility,
            "mean_log_likelihood": result.mean_log_likelihood,
            "mean_outcrossing_log_likelihood": result.mean_outcrossing_log_likelihood,
            "mean_bagging_log_likelihood": result.mean_bagging_log_likelihood,
            "mean_flower_log_likelihood": result.mean_flower_log_likelihood,
            "mean_guide_log_likelihood": result.mean_guide_log_likelihood,
            "max_importance_weight": result.posterior_best_draw_fraction,
            "included_channels": [channel.value for channel in result.included_channels],
            "boundary": result.boundary,
            "expected_predictions": [
                {
                    "island_id": prediction.island_id,
                    "effective_outcross_service": prediction.effective_outcross_service,
                    "assurance": prediction.assurance,
                    "expected_outcrossing": prediction.expected_outcrossing,
                    "expected_bagging": prediction.expected_bagging,
                    "expected_flower_length_mm": prediction.expected_flower_length_mm,
                    "latent_guide": prediction.latent_guide,
                }
                for prediction in result.expected_predictions
            ],
        }
        for result in results
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/inoue_literature_island_traits.csv"))
    parser.add_argument(
        "--guide-constraints",
        type=Path,
        default=Path("data/guide_direction_constraints.csv"),
        help="Optional reviewed ordinal guide constraints; an empty valid CSV is allowed.",
    )
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    parser.add_argument("--draws", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=20260702)
    args = parser.parse_args()

    evidence = load_island_evidence(args.input)
    constraints = load_guide_order_constraints(args.guide_constraints)
    full = compare_scenarios(evidence, constraints, draws=args.draws, seed=args.seed)

    ablations = {}
    for channel in EvidenceChannel:
        retained = tuple(candidate for candidate in EvidenceChannel if candidate is not channel)
        ablations[channel.value] = _summary_json(
            compare_scenarios(
                evidence,
                constraints,
                draws=args.draws,
                seed=args.seed,
                included_channels=retained,
            )
        )

    payload = {
        "schema_version": 1,
        "input": str(args.input),
        "guide_constraints": str(args.guide_constraints),
        "draws": args.draws,
        "seed": args.seed,
        "evidence_rows": len(evidence),
        "guide_constraints_count": len(constraints),
        "boundary": (
            "Source-locked, partial-identification compatibility analysis. "
            "Public occurrence or visitor-regime records are not treated as "
            "flower-specific pollination effectiveness, and scenario rankings "
            "are prior-sensitive rather than historical causal proof."
        ),
        "full_evidence": _summary_json(full),
        "leave_one_channel_out": ablations,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    markdown = render_markdown(full)
    markdown += "\n## Channel ablation\n\n"
    markdown += (
        "Each auxiliary ranking omits one channel. Large rank changes indicate "
        "that the retained interpretation depends materially on that channel.\n\n"
    )
    for channel, ranking in ablations.items():
        markdown += f"### Omit `{channel}`\n\n"
        markdown += "| rank | scenario | log marginal compatibility |\n|---:|---|---:|\n"
        for rank, row in enumerate(ranking, start=1):
            markdown += f"| {rank} | {row['scenario']} | {row['log_marginal_compatibility']:.3f} |\n"
        markdown += "\n"
    args.output_md.write_text(markdown, encoding="utf-8")


if __name__ == "__main__":
    main()
