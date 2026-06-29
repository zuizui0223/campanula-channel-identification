from random import Random

from channel_id.guide_inbreeding import PostSeedSurvival
from channel_id.guide_paternal import PaternalGuideParameters
from channel_id.guide_scenarios import GuideRoutes, GuideScenario, ScenarioSettings, ScenarioYear
from channel_id.nectar_guide import NectarGuideParameters, NectarGuideTrait
from channel_id.seed_set_paternity import (
    PaternityCalls,
    SeedSetPaternityDesign,
    benchmark_seed_set_paternity_recovery,
    corrected_outcross_fraction_interval,
    simulate_seed_set_paternity_observation,
)


def settings() -> ScenarioSettings:
    return ScenarioSettings(
        trait=NectarGuideTrait(0.8, 0.4, 0.5),
        maternal_parameters=NectarGuideParameters(
            10.0,
            0.0,
            0.0,
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


def test_seed_set_paternity_observation_preserves_sampling_accounting() -> None:
    design = SeedSetPaternityDesign(
        maternal_individuals=12,
        fruits_per_maternal=2,
        potential_ovules_per_fruit=10,
        genotyped_mature_seeds_per_fruit=4,
        unresolved_probability=0.2,
    )
    truth = GuideRoutes("visit_assurance", visit_attraction=True, assurance=True)

    observed = simulate_seed_set_paternity_observation(
        truth,
        settings(),
        "typical",
        design,
        Random(20260629),
    )

    assert observed.seed_fates.total_ovules == design.total_ovules
    assert (
        observed.seed_fates.outcross_viable
        + observed.seed_fates.selfed_viable
        + observed.seed_fates.other
        == design.total_ovules
    )
    assert observed.paternity_calls.sampled_mature_seeds <= (
        design.fruit_count * design.genotyped_mature_seeds_per_fruit
    )
    assert observed.paternity_calls.sampled_mature_seeds <= (
        observed.seed_fates.outcross_viable + observed.seed_fates.selfed_viable
    )
    for observation in observed.observations:
        assert 0.0 <= observation.lower <= observation.upper <= design.potential_ovules_per_fruit


def test_error_corrected_paternity_interval_contains_calibrated_fraction() -> None:
    design = SeedSetPaternityDesign(
        maternal_individuals=1,
        fruits_per_maternal=1,
        potential_ovules_per_fruit=10,
        genotyped_mature_seeds_per_fruit=10,
        outcross_to_self_error=0.10,
        self_to_outcross_error=0.05,
    )
    # A true 0.80 outcross fraction has expected observed call fraction
    # 0.05 + 0.80 * (1 - 0.10 - 0.05) = 0.73.
    lower, upper = corrected_outcross_fraction_interval(
        PaternityCalls(73, 27, 0, 100),
        design,
    )

    assert 0.0 <= lower <= 0.80 <= upper <= 1.0


def test_seed_set_paternity_benchmark_recovers_visit_assurance_truth() -> None:
    truth = GuideRoutes("visit_assurance", visit_attraction=True, assurance=True)
    candidates = (
        GuideScenario.NULL,
        GuideScenario.VISIT_ATTRACTION,
        GuideScenario.ASSURANCE,
        truth,
    )
    design = SeedSetPaternityDesign(
        maternal_individuals=40,
        fruits_per_maternal=2,
        potential_ovules_per_fruit=10,
        genotyped_mature_seeds_per_fruit=3,
    )

    first = benchmark_seed_set_paternity_recovery(
        truth,
        candidates,
        settings(),
        "typical",
        design,
        replicates=60,
        seed=20260629,
    )
    second = benchmark_seed_set_paternity_recovery(
        truth,
        candidates,
        settings(),
        "typical",
        design,
        replicates=60,
        seed=20260629,
    )

    assert first == second
    assert first.truth_retained_rate >= 0.90
    assert first.unique_truth_recovery_rate >= 0.90
    assert first.empty_compatible_set_rate <= 0.10
    assert first.mean_resolved_paternity_calls > 0.0
