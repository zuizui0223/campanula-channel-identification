"""Generate a fixed-seed virtual Izu sensitivity baseline as Markdown.

This is a synthetic operating-characteristic report, not an estimate or a
sample-size recommendation for any real island. It keeps one representative
four-plan comparison reproducible while the user varies model assumptions in
separate analyses.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from channel_id.guide_inbreeding import PostSeedSurvival
from channel_id.guide_paternal import PaternalGuideParameters
from channel_id.guide_scenarios import ScenarioSettings, ScenarioYear
from channel_id.izu_gradient_benchmark import GradientAnalysisMode, IzuGradientLandscape
from channel_id.izu_observational_equivalence import (
    observational_equivalence_groups,
    observationally_distinct_candidates,
    scenario_label,
)
from channel_id.izu_pooled_evidence import benchmark_izu_pooled_evidence_recovery
from channel_id.izu_sensitivity_report import (
    IzuObservationPlan,
    IzuRecoveryThresholds,
    IzuVirtualWorld,
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


def equivalence_groups_as_markdown(
    worlds: tuple[IzuVirtualWorld, ...],
    settings: ScenarioSettings,
) -> str:
    """Render conditional candidate aliases under the current baseline settings."""

    lines = []
    for world in worlds:
        groups = observational_equivalence_groups(
            world.candidates,
            settings,
            world.landscape,
            analysis_mode=GradientAnalysisMode.CALIBRATED,
        )
        aliases = [group for group in groups if len(group) > 1]
        rendered_aliases = "; ".join(
            " = ".join(f"`{scenario_label(candidate)}`" for candidate in group)
            for group in aliases
        )
        if not rendered_aliases:
            rendered_aliases = "none"
        lines.append(
            f"- `{world.label}`: {len(groups)} observational classes from "
            f"{len(world.candidates)} declared candidates; aliases: {rendered_aliases}."
        )
    return "\n".join(lines)


def pooled_evidence_as_markdown_table(
    worlds: tuple[IzuVirtualWorld, ...],
    plans: tuple[IzuObservationPlan, ...],
    settings: ScenarioSettings,
    replicates: int,
) -> str:
    """Render calibrated pooled-ranking recovery for distinct baseline classes."""

    header = "| world | candidate classes | plan | top-rank truth | unique truth top | mean truth rank | mean truth log-likelihood gap | no finite candidate |"
    rule = "|---|---:|---|---:|---:|---:|---:|---:|"
    rows = []
    stream = BASELINE_SEED
    for world in worlds:
        candidates = observationally_distinct_candidates(
            world.candidates,
            settings,
            world.landscape,
            analysis_mode=GradientAnalysisMode.CALIBRATED,
        )
        if world.truth not in candidates:
            raise ValueError(
                "baseline truth is structurally equivalent to an earlier candidate; "
                "declare the intended representative first"
            )
        for plan in plans:
            summary = benchmark_izu_pooled_evidence_recovery(
                truth=world.truth,
                candidates=candidates,
                template_settings=settings,
                landscape=world.landscape,
                camera_design=plan.camera_design(),
                seed_design=plan.seed_design(),
                analysis_mode=GradientAnalysisMode.CALIBRATED,
                replicates=replicates,
                seed=stream,
            )
            rows.append(
                "| "
                + " | ".join(
                    (
                        world.label,
                        str(len(candidates)),
                        plan.label,
                        f"{summary.truth_top_rank_rate:.2f}",
                        f"{summary.unique_truth_top_rate:.2f}",
                        f"{summary.mean_truth_rank:.2f}",
                        f"{summary.mean_truth_log_likelihood_gap:.2f}",
                        f"{summary.no_finite_candidate_rate:.2f}",
                    )
                )
                + " |"
            )
            stream += 1
    return "\n".join((header, rule, *rows))


def render_baseline(replicates: int) -> str:
    """Run and render the report under fixed declared assumptions."""

    landscape = baseline_landscape()
    plans = baseline_plans()
    settings = baseline_settings()
    worlds = default_izu_virtual_worlds(landscape)
    report = run_izu_sensitivity_report(
        worlds=worlds,
        plans=plans,
        template_settings=settings,
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
        "## Interval-compatibility results",
        "",
        report_as_markdown_table(report),
        "",
        "## Structural candidate equivalence (calibrated environment)",
        "",
        "Route labels are collapsed only when their declared observed predictions are "
        "identical under the current settings. This is conditional equivalence, not a "
        "claim that the biological mechanisms are generally identical.",
        "",
        equivalence_groups_as_markdown(worlds, settings),
        "",
        "## Pooled-likelihood ranking results (calibrated environment)",
        "",
        "The table ranks structurally distinct candidates from raw virtual counts pooled "
        "over sites. It is a comparative likelihood score, not posterior support. "
        "`mean truth log-likelihood gap` is truth minus the best non-truth candidate.",
        "",
        pooled_evidence_as_markdown_table(worlds, plans, settings, replicates),
        "",
        "## Pareto-minimal interval-passing plans",
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
            "whether a plan passes. The pooled table uses only the calibrated environment "
            "because it asks whether the declared joint count model can recover a route after "
            "combining islands. The four plans differ in more than one operational axis and "
            "are illustrative sensitivity probes, not an optimized field grid.",
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
