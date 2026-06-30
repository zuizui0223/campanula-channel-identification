from random import Random

import pytest

from channel_id.camera_visit_handling import CameraVisitHandlingDesign
from channel_id.guide_inbreeding import PostSeedSurvival
from channel_id.guide_paternal import PaternalGuideParameters
from channel_id.guide_scenarios import GuideScenario, ScenarioSettings, ScenarioYear
from channel_id.izu_calibration_bias import (
    DetectionCalibrationBias,
    benchmark_izu_calibration_bias_recovery,
    default_detection_calibration_biases,
    perturb_calibrated_detection_probabilities,
    score_izu_gradient_candidates_with_calibration_bias,
)
from channel_id.izu_detection_calibration import (
    DetectionCalibrationDesign,
    simulate_izu_detection_calibration_dataset,
)
from channel_id.izu_field_misspecification import IzuFieldDistortion
from channel_id.izu_gradient_benchmark import IzuGradientLandscape, IzuGradientSite
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
    return IzuGradientLandscape(0.1, 0.9, 0.8, 0.4, 1.0, 0.7)


def camera_design() -> CameraVisitHandlingDesign:
    return CameraVisitHandlingDesign(
        flower_camera_windows=3_000,
        exposure_multiplier_per_window=1.0,
        visit_detection_probability=0.9,
        legitimate_annotation_sensitivity=1.0,
        legitimate_annotation_specificity=1.0,
    )


def seed_design() -> SeedSetPaternityDesign:
    return SeedSetPaternityDesign(
        maternal_individuals=80,
        fruits_per_maternal=2,
        potential_ovules_per_fruit=10,
        genotyped_mature_seeds_per_fruit=5,
    )


def sites() -> tuple[IzuGradientSite, ...]:
    return (IzuGradientSite("north", 0.0), IzuGradientSite("south", 1.0))


def candidates():
    return (GuideScenario.NULL, GuideScenario.VISIT_ATTRACTION, GuideScenario.HANDLING)


def test_default_bias_suite_has_global_and_gradient_stresses() -> None:
    assert [item.label for item in default_detection_calibration_biases()] == [
        "unbiased",
        "easy_clip_bias",
        "south_optimistic_gradient",
        "south_pessimistic_gradient",
        "easy_clip_plus_gradient_mismatch",
    ]


def test_positive_easy_clip_bias_inflates_detection_estimates() -> None:
    original = {"north": 0.45, "south": 0.65}
    biased = perturb_calibrated_detection_probabilities(
        original,
        DetectionCalibrationBias("easy", logit_bias=0.8),
        Random(20260630),
    )

    assert biased["north"] > original["north"]
    assert biased["south"] > original["south"]


def test_gradient_bias_changes_detection_in_opposite_directions_across_islands() -> None:
    original = {"north": 0.50, "south": 0.50}
    perturbed = perturb_calibrated_detection_probabilities(
        original,
        DetectionCalibrationBias("gradient", archipelago_logit_slope=2.0),
        Random(20260630),
        {"north": 0.0, "south": 1.0},
    )

    assert perturbed["north"] < original["north"]
    assert perturbed["south"] > original["south"]


def test_gradient_bias_requires_complete_site_positions() -> None:
    with pytest.raises(ValueError, match="site_positions"):
        perturb_calibrated_detection_probabilities(
            {"north": 0.5},
            DetectionCalibrationBias("gradient", archipelago_logit_slope=1.0),
            Random(20260630),
        )


def test_zero_bias_without_mismatch_preserves_detection_estimates() -> None:
    original = {"north": 0.45, "south": 0.65}
    perturbed = perturb_calibrated_detection_probabilities(
        original,
        DetectionCalibrationBias("unbiased"),
        Random(20260630),
    )

    assert perturbed == pytest.approx(original)


def test_biased_scoring_is_reproducible_from_fixed_virtual_data() -> None:
    calibration_design = DetectionCalibrationDesign(50)
    generated = simulate_izu_detection_calibration_dataset(
        GuideScenario.VISIT_ATTRACTION,
        settings(),
        landscape(),
        camera_design(),
        seed_design(),
        IzuFieldDistortion(detection_mean_multiplier=0.55),
        calibration_design,
        sites=sites(),
        seed=20260630,
    )
    bias = DetectionCalibrationBias(
        "gradient",
        logit_bias=0.8,
        archipelago_logit_slope=2.0,
        site_logit_sd=0.4,
    )
    first = score_izu_gradient_candidates_with_calibration_bias(
        candidates(), generated, settings(), landscape(), camera_design(), seed_design(),
        calibration_design, bias, seed=20260630,
    )
    second = score_izu_gradient_candidates_with_calibration_bias(
        candidates(), generated, settings(), landscape(), camera_design(), seed_design(),
        calibration_design, bias, seed=20260630,
    )

    assert first == second
    assert len(first) == 3


def test_calibration_bias_benchmark_is_reproducible() -> None:
    calibration_design = DetectionCalibrationDesign(50)
    bias = DetectionCalibrationBias(
        "gradient",
        logit_bias=0.8,
        archipelago_logit_slope=2.0,
        site_logit_sd=0.5,
    )
    first = benchmark_izu_calibration_bias_recovery(
        GuideScenario.VISIT_ATTRACTION,
        candidates(),
        settings(),
        landscape(),
        camera_design(),
        seed_design(),
        IzuFieldDistortion(detection_mean_multiplier=0.55),
        calibration_design,
        bias,
        sites=sites(),
        replicates=12,
        seed=20260630,
    )
    second = benchmark_izu_calibration_bias_recovery(
        GuideScenario.VISIT_ATTRACTION,
        candidates(),
        settings(),
        landscape(),
        camera_design(),
        seed_design(),
        IzuFieldDistortion(detection_mean_multiplier=0.55),
        calibration_design,
        bias,
        sites=sites(),
        replicates=12,
        seed=20260630,
    )

    assert first == second
    assert first.unbiased_truth_top_rank_rate >= first.nominal_truth_top_rank_rate
    assert 0.0 <= first.biased_truth_top_rank_rate <= 1.0
