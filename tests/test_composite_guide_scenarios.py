from dataclasses import replace

from channel_id.guide_inbreeding import PostSeedSurvival
from channel_id.guide_paternal import PaternalGuideParameters
from channel_id.guide_scenarios import (
    GuideRoutes,
    GuideScenario,
    ScenarioMetric,
    ScenarioObservation,
    ScenarioSettings,
    ScenarioYear,
    core_maternal_scenarios,
    recover_compatible_scenarios,
    simulate_guide_scenario,
)
from channel_id.nectar_guide import NectarGuideParameters, NectarGuideTrait


def spec() -> ScenarioSettings:
    return ScenarioSettings(
        trait=NectarGuideTrait(0.8, 0.4, 0.5),
        maternal_parameters=NectarGuideParameters(
            10.0,
            0.0,
            1.5,
            0.1,
            0.2,
            0.0,
            1.0,
            0.2,
            0.8,
            1.0,
            0.6,
            1.0,
        ),
        paternal_parameters=PaternalGuideParameters(1.0, 0.0, 1.0, 0.2),
        post_seed_survival=PostSeedSurvival(0.4, 0.5),
        years=(ScenarioYear("typical", 0.7),),
    )


def test_visit_assurance_keeps_both_declared_routes_active() -> None:
    settings = spec()
    compound = GuideRoutes("visit_assurance", visit_attraction=True, assurance=True)
    visit_only = simulate_guide_scenario(GuideScenario.VISIT_ATTRACTION, settings)
    compound_result = simulate_guide_scenario(compound, settings)

    assert compound_result.metric(ScenarioMetric.EXPECTED_VISITS, "typical") == visit_only.metric(
        ScenarioMetric.EXPECTED_VISITS,
        "typical",
    )
    assert compound_result.metric(ScenarioMetric.OUTCROSS_VIABLE_SEEDS, "typical") == visit_only.metric(
        ScenarioMetric.OUTCROSS_VIABLE_SEEDS,
        "typical",
    )
    assert compound_result.metric(ScenarioMetric.SELFED_VIABLE_SEEDS, "typical") > 0.0


def test_compound_truth_is_not_forced_into_an_empty_or_wrong_named_scenario() -> None:
    settings = spec()
    truth = GuideRoutes("visit_assurance", visit_attraction=True, assurance=True)
    result = simulate_guide_scenario(truth, settings)
    observations = (
        ScenarioObservation(
            ScenarioMetric.EXPECTED_VISITS,
            result.metric(ScenarioMetric.EXPECTED_VISITS, "typical") - 1e-8,
            result.metric(ScenarioMetric.EXPECTED_VISITS, "typical") + 1e-8,
            "typical",
        ),
        ScenarioObservation(
            ScenarioMetric.OUTCROSS_VIABLE_SEEDS,
            result.metric(ScenarioMetric.OUTCROSS_VIABLE_SEEDS, "typical") - 1e-8,
            result.metric(ScenarioMetric.OUTCROSS_VIABLE_SEEDS, "typical") + 1e-8,
            "typical",
        ),
        ScenarioObservation(
            ScenarioMetric.SELFED_VIABLE_SEEDS,
            result.metric(ScenarioMetric.SELFED_VIABLE_SEEDS, "typical") - 1e-8,
            result.metric(ScenarioMetric.SELFED_VIABLE_SEEDS, "typical") + 1e-8,
            "typical",
        ),
    )
    candidates = (
        GuideScenario.NULL,
        GuideScenario.VISIT_ATTRACTION,
        GuideScenario.ASSURANCE,
        truth,
    )

    compatible = recover_compatible_scenarios(candidates, settings, observations)

    assert [report.scenario for report in compatible] == [truth]


def test_cost_only_is_distinct_from_null_when_guide_expression_has_a_budget_cost() -> None:
    settings = spec()
    cost_settings = replace(
        settings,
        maternal_parameters=replace(settings.maternal_parameters, guide_cost=1.5),
    )
    null = simulate_guide_scenario(GuideScenario.NULL, cost_settings)
    cost = simulate_guide_scenario(GuideScenario.COST, cost_settings)

    assert cost.metric(ScenarioMetric.EXPECTED_VISITS, "typical") == null.metric(
        ScenarioMetric.EXPECTED_VISITS,
        "typical",
    )
    assert cost.metric(ScenarioMetric.OUTCROSS_VIABLE_SEEDS, "typical") < null.metric(
        ScenarioMetric.OUTCROSS_VIABLE_SEEDS,
        "typical",
    )


def test_core_maternal_scenarios_include_cost_and_compound_alternatives() -> None:
    labels = {
        scenario.label if isinstance(scenario, GuideRoutes) else scenario.value
        for scenario in core_maternal_scenarios()
    }

    assert {"cost", "visit_assurance", "handling_assurance", "visit_cost"} <= labels
