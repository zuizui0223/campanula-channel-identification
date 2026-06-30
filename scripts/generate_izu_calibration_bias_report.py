"""Stress-test finite Izu camera calibration against biased clip selection.

The report compares nominal fixed detection, unbiased finite calibration, and
finite calibration whose analysis estimate is deliberately biased.  It remains
synthetic and uses an optimistic independent reference stream.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from channel_id.guide_inbreeding import PostSeedSurvival
from channel_id.guide_paternal import PaternalGuideParameters
from channel_id.guide_scenarios import ScenarioSettings, ScenarioYear
from channel_id.izu_calibration_bias import (
    benchmark_izu_calibration_bias_recovery,
    default_detection_calibration_biases,
)
from channel_id.izu_detection_calibration import DetectionCalibrationDesign
from channel_id.izu_field_misspecification import default_izu_field_stress_cases
from channel_id.izu_gradient_benchmark import GradientAnalysisMode, IzuGradientLandscape
from channel_id.izu_observational_equivalence import observationally_distinct_candidates
from channel_id.izu_sensitivity_report import IzuObservationPlan, default_izu_virtual_worlds
from channel_id.nectar_guide import NectarGuideParameters, NectarGuideTrait


REPORT_SEED = 20260630
REFERENCE_VISITS_PER_SITE = 50


def settings() -> ScenarioSettings:
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


def landscape() -> IzuGradientLandscape:
    return IzuGradientLandscape(0.10, 0.90, 0.80, 0.40, 1.00, 0.70)


def plans() -> tuple[IzuObservationPlan, ...]:
    return (
        IzuObservationPlan("light", 200, 20, 2, 10, 2),
        IzuObservationPlan("camera_heavy", 1_000, 20, 2, 10, 2),
        IzuObservationPlan("genetic_heavy", 200, 60, 2, 10, 5),
        IzuObservationPlan("balanced_high", 1_000, 60, 2, 10, 5),
    )


def render_calibration_bias_report(replicates: int) -> str:
    if replicates < 1:
        raise ValueError("replicates must be positive")
    model_settings = settings()
    model_landscape = landscape()
    worlds_by_label = {
        world.label: world for world in default_izu_virtual_worlds(model_landscape)
    }
    worlds = (
        worlds_by_label["visit_environment_gradient"],
        worlds_by_label["visit_assurance_environment_gradient"],
    )
    stress_by_label = {
        case.label: case for case in default_izu_field_stress_cases()
    }
    stress_cases = (
        stress_by_label["wind_light_detection_loss"],
        stress_by_label["combined_field_stress"],
    )
    biases = default_detection_calibration_biases()
    calibration_design = DetectionCalibrationDesign(REFERENCE_VISITS_PER_SITE)

    lines = [
        "# Virtual Izu calibration-bias stress report",
        "",
        "**Synthetic only.** Every row starts from the same finite independent "
        "reference calibration, then deliberately distorts its analysis-side "
        "detection estimate. This tests selection/mismatch fragility, not field "
        "performance.",
        "",
        f"- Seed: `{REPORT_SEED}`",
        f"- Replicates per world × plan × stress × bias: `{replicates}`",
        f"- Reference visits: `{REFERENCE_VISITS_PER_SITE}` per virtual site-condition.",
        "- `easy_clip_bias`: calibration detection is too optimistic by +0.80 on the logit scale.",
        "- `stratum_mismatch`: independent site-condition mismatch SD = 0.70 on the logit scale.",
        "",
        "| world | candidate classes | plan | field stress | calibration assumption | nominal unique top | unbiased unique top | biased unique top | Δ biased vs unbiased | nominal mean rank | unbiased mean rank | biased mean rank |",
        "|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    stream = REPORT_SEED
    for world in worlds:
        candidates = observationally_distinct_candidates(
            world.candidates,
            model_settings,
            world.landscape,
            analysis_mode=GradientAnalysisMode.CALIBRATED,
        )
        if world.truth not in candidates:
            raise ValueError("truth must be the representative of its observational class")
        for plan in plans():
            for stress in stress_cases:
                for bias in biases:
                    summary = benchmark_izu_calibration_bias_recovery(
                        truth=world.truth,
                        candidates=candidates,
                        template_settings=model_settings,
                        landscape=world.landscape,
                        camera_design=plan.camera_design(),
                        seed_design=plan.seed_design(),
                        distortion=stress.distortion,
                        calibration_design=calibration_design,
                        bias=bias,
                        analysis_mode=GradientAnalysisMode.CALIBRATED,
                        replicates=replicates,
                        seed=stream,
                    )
                    delta = (
                        summary.biased_unique_truth_top_rate
                        - summary.unbiased_unique_truth_top_rate
                    )
                    lines.append(
                        "| "
                        + " | ".join(
                            (
                                world.label,
                                str(len(candidates)),
                                plan.label,
                                stress.label,
                                bias.label,
                                f"{summary.nominal_unique_truth_top_rate:.2f}",
                                f"{summary.unbiased_unique_truth_top_rate:.2f}",
                                f"{summary.biased_unique_truth_top_rate:.2f}",
                                f"{delta:+.2f}",
                                f"{summary.nominal_mean_truth_rank:.2f}",
                                f"{summary.unbiased_mean_truth_rank:.2f}",
                                f"{summary.biased_mean_truth_rank:.2f}",
                            )
                        )
                        + " |"
                    )
                    stream += 1
    lines.extend(
        (
            "",
            "## Interpretation boundary",
            "",
            "The unbiased column remains optimistic because reference visits are treated as known opportunities. The biased columns do not estimate a particular real bias. They ask whether preserving the calibration count alone is enough when clips are easier than ordinary footage or do not match the wind/light stratum. A loss of biased recovery means clip selection method and condition matching must be retained and modeled, not merely that more clips are needed.",
        )
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replicates", type=int, default=25)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        rendered = render_calibration_bias_report(args.replicates)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
