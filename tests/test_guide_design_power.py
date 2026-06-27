from channel_id.guide_design_power import (
    MeasurementDesign,
    MeasurementPlan,
    evaluate_measurement_plan,
    rank_measurement_plans,
    sweep_common_sample_sizes,
)
from channel_id.guide_inbreeding import PostSeedSurvival
from channel_id.guide_paternal import PaternalGuideParameters
from channel_id.guide_scenarios import GuideScenario, ScenarioMetric, ScenarioSettings, ScenarioYear
from channel_id.guide_spatial import Patch
from channel_id.nectar_guide import NectarGuideParameters, NectarGuideTrait


CANDIDATES = (
    GuideScenario.NULL,
    GuideScenario.VISIT_ATTRACTION,
    GuideScenario.HANDLING,
    GuideScenario.ASSURANCE,
)


def settings() -> ScenarioSettings:
    return ScenarioSettings(
        trait=NectarGuideTrait(guide_contrast=0.8, display=0.4, assurance=0.5),
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
        paternal_parameters=PaternalGuideParameters(
            baseline_pollen_export=1.0,
            display_export_gain=0.0,
            guide_export_gain=1.0,
            baseline_siring_success=0.2,
        ),
        post_seed_survival=PostSeedSurvival(outcrossed_survival=0.4, late_inbreeding_depression=0.5),
        years=(ScenarioYear("typical", pollinator_service=0.7),),
        spatial_patches=(Patch("occupied", establishment_probability=0.8, capacity=100.0),),
        spatial_dispersal=(1.0,),
    )


def visit_plan(sample_size: int, standard_deviation: float) -> MeasurementPlan:
    return MeasurementPlan(
        name=f"visits n={sample_size}",
        measurements=(
            MeasurementDesign(
                metric=ScenarioMetric.EXPECTED_VISITS,
                year_label="typical",
                sample_size=sample_size,
                individual_standard_deviation=standard_deviation,
            ),
        ),
    )


def test_larger_effective_sample_size_improves_visit_scenario_recovery() -> None:
    low_n = evaluate_measurement_plan(
        GuideScenario.VISIT_ATTRACTION,
        CANDIDATES,
        settings(),
        visit_plan(sample_size=4, standard_deviation=2.0),
        replicates=400,
        random_seed=17,
    )
    high_n = evaluate_measurement_plan(
        GuideScenario.VISIT_ATTRACTION,
        CANDIDATES,
        settings(),
        visit_plan(sample_size=100, standard_deviation=2.0),
        replicates=400,
        random_seed=17,
    )

    assert high_n.unique_truth_recovery_rate > low_n.unique_truth_recovery_rate
    assert high_n.mean_compatible_scenarios < low_n.mean_compatible_scenarios


def test_exact_intermediate_measurement_recovers_virtual_truth() -> None:
    result = evaluate_measurement_plan(
        GuideScenario.VISIT_ATTRACTION,
        CANDIDATES,
        settings(),
        visit_plan(sample_size=1, standard_deviation=0.0),
        replicates=20,
        random_seed=2,
    )

    assert result.truth_retention_rate == 1.0
    assert result.unique_truth_recovery_rate == 1.0
    assert result.mean_compatible_scenarios == 1.0


def test_plan_ranking_prefers_informative_measurement() -> None:
    rankings = rank_measurement_plans(
        GuideScenario.VISIT_ATTRACTION,
        CANDIDATES,
        settings(),
        (
            MeasurementPlan(
                name="noisy terminal output",
                measurements=(
                    MeasurementDesign(
                        metric=ScenarioMetric.FEMALE_RECRUITS,
                        year_label="typical",
                        sample_size=4,
                        individual_standard_deviation=4.0,
                    ),
                ),
            ),
            visit_plan(sample_size=1, standard_deviation=0.0),
        ),
        replicates=200,
        random_seed=4,
    )

    assert rankings[0].result.plan_name == "visits n=1"
    assert rankings[0].result.unique_truth_recovery_rate == 1.0


def test_common_sample_size_sweep_replaces_all_measurement_sizes() -> None:
    base = MeasurementPlan(
        name="visit plus outcross",
        measurements=(
            MeasurementDesign(ScenarioMetric.EXPECTED_VISITS, 3, 1.0, "typical"),
            MeasurementDesign(ScenarioMetric.OUTCROSS_VIABLE_SEEDS, 3, 2.0, "typical"),
        ),
    )
    plans = sweep_common_sample_sizes(base, (10, 30, 90))

    assert [plan.name for plan in plans] == [
        "visit plus outcross; n=10",
        "visit plus outcross; n=30",
        "visit plus outcross; n=90",
    ]
    assert [measurement.sample_size for measurement in plans[1].measurements] == [30, 30]
