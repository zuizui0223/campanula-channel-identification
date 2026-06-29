"""Compare virtual observation panels for visit versus handling mechanisms.

This is a pre-data demonstration.  It creates a virtual truth in which guide
contrast affects *both* encounter rate and legitimate handling, then compares:

1. visits only;
2. visits plus the fraction of visits with a legitimate contact; and
3. visits plus effective stigma-pollen deposition.

Run:

    python examples/handling_deposition_design_power.py

The standard deviations and effective sample sizes are intentionally virtual.
Replace them with pilot-derived quantities and assay-specific observation models
before using the comparison for a field protocol.
"""

from channel_id.guide_design_power import (
    MeasurementDesign,
    MeasurementPlan,
    rank_measurement_plans,
)
from channel_id.guide_inbreeding import PostSeedSurvival
from channel_id.guide_paternal import PaternalGuideParameters
from channel_id.guide_scenarios import (
    GuideRoutes,
    GuideScenario,
    ScenarioMetric,
    ScenarioSettings,
    ScenarioYear,
)
from channel_id.nectar_guide import NectarGuideParameters, NectarGuideTrait


TRUTH = GuideRoutes("visit_handling", visit_attraction=True, handling=True)
CANDIDATES = (
    GuideScenario.NULL,
    GuideScenario.VISIT_ATTRACTION,
    GuideScenario.HANDLING,
    TRUTH,
)


def settings() -> ScenarioSettings:
    return ScenarioSettings(
        trait=NectarGuideTrait(guide_contrast=0.8, display=0.4, assurance=0.0),
        maternal_parameters=NectarGuideParameters(
            seed_budget=10.0,
            display_cost=0.0,
            guide_cost=0.0,
            assurance_cost=0.0,
            baseline_visit_rate=0.5,
            display_visit_gain=0.0,
            guide_visit_gain=0.5,
            baseline_legitimate_fraction=0.2,
            guide_handling_gain=0.4,
            pollen_to_outcross_fraction=0.8,
            selfing_viability=0.6,
            baseline_establishment=1.0,
        ),
        paternal_parameters=PaternalGuideParameters(0.0, 0.0, 0.0, 0.0),
        post_seed_survival=PostSeedSurvival(
            outcrossed_survival=0.4,
            late_inbreeding_depression=0.5,
        ),
        years=(ScenarioYear("typical", pollinator_service=0.7),),
    )


def main() -> None:
    plans = (
        MeasurementPlan(
            "visits only",
            (
                MeasurementDesign(
                    ScenarioMetric.EXPECTED_VISITS,
                    sample_size=40,
                    individual_standard_deviation=0.35,
                    year_label="typical",
                ),
            ),
        ),
        MeasurementPlan(
            "visits + legitimate-contact fraction",
            (
                MeasurementDesign(
                    ScenarioMetric.EXPECTED_VISITS,
                    sample_size=40,
                    individual_standard_deviation=0.35,
                    year_label="typical",
                ),
                MeasurementDesign(
                    ScenarioMetric.LEGITIMATE_CONTACT_FRACTION,
                    sample_size=40,
                    individual_standard_deviation=0.15,
                    year_label="typical",
                ),
            ),
        ),
        MeasurementPlan(
            "visits + effective stigma-pollen deposition",
            (
                MeasurementDesign(
                    ScenarioMetric.EXPECTED_VISITS,
                    sample_size=40,
                    individual_standard_deviation=0.35,
                    year_label="typical",
                ),
                MeasurementDesign(
                    ScenarioMetric.STIGMA_POLLEN_DEPOSITION,
                    sample_size=40,
                    individual_standard_deviation=0.10,
                    year_label="typical",
                ),
            ),
        ),
    )

    rankings = rank_measurement_plans(
        truth_scenario=TRUTH,
        candidate_scenarios=CANDIDATES,
        settings=settings(),
        plans=plans,
        replicates=2_000,
        random_seed=20260629,
    )

    print("rank | plan | truth retained | unique truth | false survivors")
    for ranked in rankings:
        result = ranked.result
        print(
            f"{ranked.rank:>4} | {result.plan_name:<43} | "
            f"{result.truth_retention_rate:>13.3f} | "
            f"{result.unique_truth_recovery_rate:>12.3f} | "
            f"{result.mean_false_survivors:>15.3f}"
        )


if __name__ == "__main__":
    main()
