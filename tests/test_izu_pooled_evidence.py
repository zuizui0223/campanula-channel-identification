from math import log

import pytest

from channel_id.camera_visit_handling import CameraVisitHandlingDesign
from channel_id.guide_inbreeding import PostSeedSurvival
from channel_id.guide_paternal import PaternalGuideParameters
from channel_id.guide_scenarios import GuideScenario, ScenarioSettings, ScenarioYear
from channel_id.izu_gradient_benchmark import (
    GradientAnalysisMode,
    IzuGradientLandscape,
    IzuGradientSite,
    simulate_izu_gradient_dataset,
)
from channel_id.izu_pooled_evidence import (
    benchmark_izu_pooled_evidence_recovery,
    binomial_log_probability,
    multinomial_log_probability,
    paternity_call_probabilities,
    poisson_log_probability,
    score_izu_gradient_candidates,
    top_scoring_scenarios,
)
from channel_id.nectar_guide import NectarGuideParameters, NectarGuideTrait
from channel_id.seed_set_paternity import SeedSetPaternityDesign


def settings() -> ScenarioSettings:
    return ScenarioSettings(
        trait=NectarGuideTrait(0.1, 0.4, 0.5),
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
    return IzuGradientLandscape(
        guide_contrast_north=0.1,
        guide_contrast_south=0.9,
        pollinator_service_north=0.8,
        pollinator_service_south=0.4,
        establishment_multiplier_north=1.0,
        establishment_multiplier_south=0.7,
    )


def camera_design() -> CameraVisitHandlingDesign:
    return CameraVisitHandlingDesign(
        flower_camera_windows=5_000,
        exposure_multiplier_per_window=1.0,
        visit_detection_probability=1.0,
        legitimate_annotation_sensitivity=1.0,
        legitimate_annotation_specificity=1.0,
    )


def seed_design() -> SeedSetPaternityDesign:
    return SeedSetPaternityDesign(
        maternal_individuals=100,
        fruits_per_maternal=2,
        potential_ovules_per_fruit=10,
        genotyped_mature_seeds_per_fruit=5,
    )


def sites() -> tuple[IzuGradientSite, ...]:
    return (IzuGradientSite("north", 0.0), IzuGradientSite("south", 1.0))


def test_log_probability_helpers_match_simple_known_values() -> None:
    assert poisson_log_probability(0, 0.0) == 0.0
    assert poisson_log_probability(1, 0.0) == float("-inf")
    assert binomial_log_probability(1, 2, 0.5) == pytest.approx(log(0.5))
    assert multinomial_log_probability((1, 1), (0.5, 0.5)) == pytest.approx(log(0.5))


def test_paternity_call_probabilities_partition_one() -> None:
    plan = SeedSetPaternityDesign(
        maternal_individuals=1,
        fruits_per_maternal=1,
        potential_ovules_per_fruit=10,
        genotyped_mature_seeds_per_fruit=3,
        unresolved_probability=0.10,
        outcross_to_self_error=0.02,
        self_to_outcross_error=0.03,
    )

    probabilities = paternity_call_probabilities(0.75, plan)

    assert sum(probabilities) == pytest.approx(1.0)
    assert probabilities[2] == pytest.approx(0.10)


def test_pooled_score_ranks_strong_visit_truth_first_under_calibrated_gradient() -> None:
    candidates = (
        GuideScenario.NULL,
        GuideScenario.VISIT_ATTRACTION,
        GuideScenario.HANDLING,
    )
    dataset = simulate_izu_gradient_dataset(
        GuideScenario.VISIT_ATTRACTION,
        settings(),
        landscape(),
        camera_design(),
        seed_design(),
        sites=sites(),
        seed=20260630,
    )

    evidence = score_izu_gradient_candidates(
        candidates,
        dataset,
        settings(),
        landscape(),
        camera_design(),
        seed_design(),
        GradientAnalysisMode.CALIBRATED,
    )

    assert evidence[0].scenario is GuideScenario.VISIT_ATTRACTION
    assert top_scoring_scenarios(evidence) == (GuideScenario.VISIT_ATTRACTION,)
    assert len(evidence[0].sites) == 2
    assert evidence[0].total_log_likelihood > evidence[-1].total_log_likelihood


def test_pooled_benchmark_is_reproducible_and_recovers_visit_truth() -> None:
    candidates = (
        GuideScenario.NULL,
        GuideScenario.VISIT_ATTRACTION,
        GuideScenario.HANDLING,
    )
    first = benchmark_izu_pooled_evidence_recovery(
        GuideScenario.VISIT_ATTRACTION,
        candidates,
        settings(),
        landscape(),
        camera_design(),
        seed_design(),
        sites=sites(),
        replicates=12,
        seed=20260630,
    )
    second = benchmark_izu_pooled_evidence_recovery(
        GuideScenario.VISIT_ATTRACTION,
        candidates,
        settings(),
        landscape(),
        camera_design(),
        seed_design(),
        sites=sites(),
        replicates=12,
        seed=20260630,
    )

    assert first == second
    assert first.truth_top_rank_rate >= 0.90
    assert first.unique_truth_top_rate >= 0.90
    assert first.mean_truth_rank <= 1.10
    assert first.mean_truth_log_likelihood_gap > 0.0
    assert first.no_finite_candidate_rate == 0.0
