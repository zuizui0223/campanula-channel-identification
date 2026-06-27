from channel_id.guide_inbreeding import PostSeedSurvival
from channel_id.guide_paternal import PaternalGuideParameters
from channel_id.guide_scenarios import GuideScenario, ScenarioMetric, ScenarioObservation, ScenarioSettings, ScenarioYear, recover_compatible_scenarios, simulate_guide_scenario
from channel_id.guide_spatial import Patch
from channel_id.nectar_guide import NectarGuideParameters, NectarGuideTrait


def spec() -> ScenarioSettings:
    return ScenarioSettings(
        trait=NectarGuideTrait(0.8, 0.4, 0.5),
        maternal_parameters=NectarGuideParameters(10.0, 0.0, 0.0, 0.1, 0.2, 0.0, 1.0, 0.2, 0.8, 1.0, 0.6, 1.0),
        paternal_parameters=PaternalGuideParameters(1.0, 0.0, 1.0, 0.2),
        post_seed_survival=PostSeedSurvival(0.4, 0.5),
        years=(ScenarioYear("typical", 0.7),),
        spatial_patches=(Patch("occupied", 0.8, 100.0),),
        spatial_dispersal=(1.0,),
    )


def test_coarse_terminal_observation_leaves_ambiguity() -> None:
    settings = spec()
    truth = simulate_guide_scenario(GuideScenario.VISIT_ATTRACTION, settings)
    total = truth.metric(ScenarioMetric.TOTAL_CONTRIBUTION, "typical")
    compatible = recover_compatible_scenarios(
        tuple(GuideScenario),
        settings,
        (
            ScenarioObservation(
                ScenarioMetric.TOTAL_CONTRIBUTION,
                max(0.0, total - 3.0),
                total + 3.0,
                "typical",
            ),
        ),
    )
    assert len(compatible) > 1


def test_intermediate_observations_recover_visit_scenario() -> None:
    settings = spec()
    truth = simulate_guide_scenario(GuideScenario.VISIT_ATTRACTION, settings)
    visits = truth.metric(ScenarioMetric.EXPECTED_VISITS, "typical")
    outcross = truth.metric(ScenarioMetric.OUTCROSS_VIABLE_SEEDS, "typical")
    compatible = recover_compatible_scenarios(
        tuple(GuideScenario), settings,
        (ScenarioObservation(ScenarioMetric.EXPECTED_VISITS, visits - 1e-8, visits + 1e-8, "typical"), ScenarioObservation(ScenarioMetric.OUTCROSS_VIABLE_SEEDS, outcross - 1e-8, outcross + 1e-8, "typical")),
    )
    assert [report.scenario for report in compatible] == [GuideScenario.VISIT_ATTRACTION]


def test_spatial_scenario_requires_patch_data() -> None:
    settings = spec()
    nonspatial = ScenarioSettings(settings.trait, settings.maternal_parameters, settings.paternal_parameters, settings.post_seed_survival, settings.years)
    try:
        simulate_guide_scenario(GuideScenario.SPATIAL, nonspatial)
    except ValueError as error:
        assert "spatial" in str(error)
    else:
        raise AssertionError("spatial scenario must require patch data")