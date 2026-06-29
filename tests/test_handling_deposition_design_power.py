from math import exp, isclose

from channel_id.guide_design_power import MeasurementDesign, MeasurementPlan, evaluate_measurement_plan
from channel_id.guide_inbreeding import PostSeedSurvival
from channel_id.guide_paternal import PaternalGuideParameters
from channel_id.guide_scenarios import (
    GuideRoutes,
    GuideScenario,
    ScenarioMetric,
    ScenarioSettings,
    ScenarioYear,
    simulate_guide_scenario,
)
from channel_id.nectar_guide import NectarGuideParameters, NectarGuideRegime, NectarGuideTrait, simulate_nectar_guide_life_history


TRUTH = GuideRoutes("visit_handling", visit_attraction=True, handling=True)
CANDIDATES = (
    GuideScenario.NULL,
    GuideScenario.VISIT_ATTRACTION,
    GuideScenario.HANDLING,
    TRUTH,
)


def settings() -> ScenarioSettings:
    """Virtual system where visits and handling are distinct, active pathways."""

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
        paternal_parameters=PaternalGuideParameters(
            baseline_pollen_export=0.0,
            display_export_gain=0.0,
            guide_export_gain=0.0,
            baseline_siring_success=0.0,
        ),
        post_seed_survival=PostSeedSurvival(
            outcrossed_survival=0.4,
            late_inbreeding_depression=0.5,
        ),
        years=(ScenarioYear("typical", pollinator_service=0.7),),
    )


def test_contact_and_deposition_observables_follow_the_declared_life_cycle() -> None:
    parameters = settings().maternal_parameters
    result = simulate_nectar_guide_life_history(
        settings().trait,
        NectarGuideRegime(pollinator_service=0.7),
        parameters,
    )

    assert isclose(
        result.expected_legitimate_contacts,
        result.expected_visits * result.legitimate_contact_fraction,
    )
    assert isclose(
        result.stigma_pollen_deposition,
        result.expected_legitimate_contacts * parameters.pollen_to_outcross_fraction,
    )
    assert isclose(result.outcross_fraction, 1.0 - exp(-result.stigma_pollen_deposition))


def test_visits_only_leave_a_compound_handling_route_unresolved() -> None:
    result = evaluate_measurement_plan(
        TRUTH,
        CANDIDATES,
        settings(),
        MeasurementPlan(
            "exact visits only",
            (
                MeasurementDesign(
                    ScenarioMetric.EXPECTED_VISITS,
                    sample_size=1,
                    individual_standard_deviation=0.0,
                    year_label="typical",
                ),
            ),
        ),
        replicates=20,
        random_seed=17,
    )

    # Visit-only and visit-plus-handling have identical expected visits by design.
    assert result.truth_retention_rate == 1.0
    assert result.unique_truth_recovery_rate == 0.0
    assert result.mean_compatible_scenarios == 2.0


def test_contact_or_deposition_breaks_visit_handling_ambiguity_in_virtual_data() -> None:
    visit_only = MeasurementPlan(
        "visits only",
        (
            MeasurementDesign(
                ScenarioMetric.EXPECTED_VISITS,
                sample_size=40,
                individual_standard_deviation=0.35,
                year_label="typical",
            ),
        ),
    )
    visit_and_contact = MeasurementPlan(
        "visits plus legitimate-contact fraction",
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
    )
    visit_and_deposition = MeasurementPlan(
        "visits plus effective pollen deposition",
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
    )

    visit_result = evaluate_measurement_plan(
        TRUTH,
        CANDIDATES,
        settings(),
        visit_only,
        replicates=1_000,
        random_seed=20260629,
    )
    contact_result = evaluate_measurement_plan(
        TRUTH,
        CANDIDATES,
        settings(),
        visit_and_contact,
        replicates=1_000,
        random_seed=20260629,
    )
    deposition_result = evaluate_measurement_plan(
        TRUTH,
        CANDIDATES,
        settings(),
        visit_and_deposition,
        replicates=1_000,
        random_seed=20260629,
    )

    assert visit_result.unique_truth_recovery_rate == 0.0
    assert visit_result.truth_retention_rate > 0.90
    assert contact_result.unique_truth_recovery_rate > 0.85
    assert deposition_result.unique_truth_recovery_rate > 0.85
    assert contact_result.unique_truth_recovery_rate > visit_result.unique_truth_recovery_rate
    assert deposition_result.unique_truth_recovery_rate > visit_result.unique_truth_recovery_rate


def test_scenario_results_expose_contact_and_deposition_metrics() -> None:
    result = simulate_guide_scenario(TRUTH, settings())

    assert isclose(result.metric(ScenarioMetric.LEGITIMATE_CONTACT_FRACTION, "typical"), 0.52)
    assert result.metric(ScenarioMetric.EXPECTED_LEGITIMATE_CONTACTS, "typical") > 0.0
    assert result.metric(ScenarioMetric.STIGMA_POLLEN_DEPOSITION, "typical") > 0.0
