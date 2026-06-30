from random import Random

from channel_id.camera_visit_handling import (
    CameraVisitHandlingCounts,
    CameraVisitHandlingDesign,
    benchmark_camera_visit_handling_recovery,
    corrected_legitimate_fraction_interval,
    poisson_mean_interval,
    simulate_camera_visit_handling_observation,
)
from channel_id.guide_inbreeding import PostSeedSurvival
from channel_id.guide_paternal import PaternalGuideParameters
from channel_id.guide_scenarios import GuideRoutes, GuideScenario, ScenarioSettings, ScenarioYear
from channel_id.nectar_guide import NectarGuideParameters, NectarGuideTrait


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


def test_camera_counts_accept_a_valid_partition() -> None:
    counts = CameraVisitHandlingCounts(
        true_visits=10,
        true_legitimate_contacts=4,
        detected_visits=8,
        called_legitimate=3,
        called_nonlegitimate=5,
    )

    assert counts.called_legitimate + counts.called_nonlegitimate == counts.detected_visits


def test_camera_observation_preserves_detection_and_annotation_accounting() -> None:
    design = CameraVisitHandlingDesign(
        flower_camera_windows=200,
        exposure_multiplier_per_window=1.0,
        visit_detection_probability=0.80,
        legitimate_annotation_sensitivity=0.90,
        legitimate_annotation_specificity=0.95,
    )
    truth = GuideRoutes("visit_handling", visit_attraction=True, handling=True)

    observed = simulate_camera_visit_handling_observation(
        truth,
        settings(),
        "typical",
        design,
        Random(20260629),
    )

    counts = observed.counts
    assert 0 <= counts.true_legitimate_contacts <= counts.true_visits
    assert 0 <= counts.detected_visits <= counts.true_visits
    assert counts.called_legitimate + counts.called_nonlegitimate == counts.detected_visits
    assert observed.observations[0].metric.value == "expected_visits"
    assert observed.observations[1].metric.value == "legitimate_contact_fraction"
    assert 0.0 <= observed.observations[0].lower <= observed.observations[0].upper
    assert 0.0 <= observed.observations[1].lower <= observed.observations[1].upper <= 1.0


def test_poisson_and_handling_intervals_contain_calibrated_values() -> None:
    lower_count, upper_count = poisson_mean_interval(100, 0.95)
    assert 0.0 <= lower_count < 100.0 < upper_count

    design = CameraVisitHandlingDesign(
        flower_camera_windows=1,
        exposure_multiplier_per_window=1.0,
        visit_detection_probability=1.0,
        legitimate_annotation_sensitivity=0.90,
        legitimate_annotation_specificity=0.95,
    )
    # A true 0.80 legitimate-contact fraction implies a mean called-legitimate
    # fraction of 0.05 + 0.80 * (0.90 + 0.95 - 1.0) = 0.73.
    lower, upper = corrected_legitimate_fraction_interval(73, 100, design)
    assert 0.0 <= lower <= 0.80 <= upper <= 1.0


def test_camera_benchmark_recovers_a_handling_truth_reproducibly() -> None:
    truth = GuideScenario.HANDLING
    candidates = (
        GuideScenario.NULL,
        GuideScenario.VISIT_ATTRACTION,
        GuideScenario.HANDLING,
    )
    design = CameraVisitHandlingDesign(
        flower_camera_windows=1_000,
        exposure_multiplier_per_window=1.0,
        visit_detection_probability=1.0,
        legitimate_annotation_sensitivity=1.0,
        legitimate_annotation_specificity=1.0,
    )

    first = benchmark_camera_visit_handling_recovery(
        truth,
        candidates,
        settings(),
        "typical",
        design,
        replicates=60,
        seed=20260629,
    )
    second = benchmark_camera_visit_handling_recovery(
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
    assert first.mean_detected_visits > 0.0
