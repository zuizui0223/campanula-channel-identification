"""Generate a fixed-seed virtual Izu sensitivity baseline as Markdown.

This is a synthetic operating-characteristic report, not an estimate or a
sample-size recommendation for any real island. It exists to keep one
representative four-plan comparison reproducible while the user varies model
assumptions in separate analyses.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from channel_id.guide_inbreeding import PostSeedSurvival
from channel_id.guide_paternal import PaternalGuideParameters
from channel_id.guide_scenarios import ScenarioSettings, ScenarioYear
from channel_id.izu_gradient_benchmark import IzuGradientLandscape
from channel_id.izu_sensitivity_report import (
    IzuObservationPlan,
    IzuRecoveryThresholds,
    default_izu_virtual_worlds,
    report_as_markdown_table,
    run_izu_sensitivity_report,
)
from channel_id.nectar_guide import NectarGuideParameters, NectarGuideTrait


BASELINE_SEED = 20260630


def baseline_settings() -> ScenarioSettings:
    """Return the declared synthetic setting used by the baseline report."""

    return ScenarioSettings(
        trait=NectarGuideTrait(0.10, 0.40, 0.50),
        maternal_parameters=NectarGuideParameters(
            seed_budget=10.0,
            display_cost=0.0,
            guide_cost=0.0,
            assurance_cost=0.1,
            baseline_visit_rate=0.2,
            display_visit_gain=0.0,
            guide_visit_gain=1.0,
            baseline_legitimate_fraction=0.2,
            guide_handling_gain=0.8,
            pollen_to_outcross_fraction=1.0,
            selfing_viability=0.6,
            baseline_establishment=1.0,
        ),
        paternal_parameters=PaternalGuideParameters(1.0, 0.0, 1.0, 0.2),
        post_seed_survival=PostSeedSurvival(0.4, 0.5),
        years=(ScenarioYear("template", 0.7),),
    )


def baseline_landscape() -> IzuGradientLandscape:
    """Return the declared synthetic north-to-south landscape endpoints."""

    return IzuGradientLandscape(
        guide_contrast_north=0.10,
        guide_contrast_south=0.90,
        pollinator_service_north=0.80,
        pollinator_service_south=0.40,
        establishment_multiplier_north=1.00,
        establishment_multiplier_south=0.70,
    )


def baseline_plans() -> tuple[IzuObservationPlan, ...]:
    """Return four deliberately contrasting per-site observation plans."""

    return (
        IzuObservationPlan("light", 200, 20, 2, 10, 2),
        IzuObservationPlan("camera_heavy", 1_000, 20, 2, 10, 2),
        IzuObservationPlan("genetic_heavy", 200, 60, 2, 10, 5),
        IzuObservationPlan("balanced_high", 1_000, 60, 2, 10, 5),
    )


def render_baseline(replicates: int) -> str:
    """Run and render the report under fixed declared assumptions."""

    report = run_izu_sensitivity_report(
        worlds=default_izu_virtual_worlds(baseline_landscape()),
        plans=baseline_plans(),
        template_settings=baseline_settings(),
        thresholds=IzuRecoveryThresholds(
            minimum_truth_retained_rate=0.90,
            minimum_unique_truth_recovery_rate=0.80,
            maximum_empty_compatible_set_rate=0.10,
        ),
        replicates=replicates,
        seed=BASELINE_SEED,
        include_flat_environment_diagnostic=True,
    )
    lines = [
        "# Virtual Izu sensitivity baseline",
        "",
        "**Synthetic only.** This report is a fixed-seed operating-characteristic "
        "comparison, not a field recommendation or empirical estimate.",
        "",
        f"- Seed: `{BASELINE_SEED}`",
        f"- Replicates per plan × world × analysis mode: `{replicates}`",
        f"- Ordinal scaffold sites: `{len(report.sites)}`",
        "- Pass thresholds: retention ≥ 0.90, unique recovery ≥ 0.80, empty set ≤ 0.10.",
        "",
        "## Results",
        "",
        report_as_markdown_table(report),
        "",
        "## Pareto-minimal passing plans",
        "",
    ]
    frontier = report.pareto_minimal_passing_plans()
    if not frontier:
        lines.append("No plan passed every calibrated virtual world under these assumptions.")
    else:
        for plan in frontier:
            camera, fruits, genotype_cap = plan.totals_for_sites(len(report.sites))
            lines.append(
                f"- `{plan.label}`: balanced {len(report.sites)}-site proxy = "
                f"{camera} camera windows, {fruits} fruits, {genotype_cap} genotype-cap seeds."
            )
    lines.extend(
        (
            "",
            "## Interpretation boundary",
            "",
            "`flat_environment` rows deliberately ignore the declared pollinator-service "
            "and establishment gradient. They diagnose confounding risk and never decide "
            "whether a plan passes. The four plans differ in more than one operational "
            "axis and are illustrative sensitivity probes, not an optimized field grid.",
        )
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--replicates",
        type=int,
        default=50,
        help="virtual replicates per plan × world × analysis mode (default: 50)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="optional Markdown output path; stdout is used when omitted",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.replicates < 1:
        raise SystemExit("--replicates must be positive")
    rendered = render_baseline(args.replicates)
    if args.output is None:
        print(rendered, end="")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
