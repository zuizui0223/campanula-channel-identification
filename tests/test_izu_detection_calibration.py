import pytest

from channel_id.camera_visit_handling import CameraVisitHandlingDesign
from channel_id.guide_inbreeding import PostSeedSurvival
from channel_id.guide_paternal import PaternalGuideParameters
from channel_id.guide_scenarios import GuideScenario, ScenarioSettings, ScenarioYear
from channel_id.izu_detection_calibration import (
    DetectionCalibrationDesign,
    SiteDetectionCalibrationObservation,
    benchmark_izu_detection_calibration_recovery,
    calibrated_detection_probabilities,
    estimated_detection_probability,
    score_izu_gradient_candidates_with_detection_calibration,
    simulate_izu_detection_calibration_dataset,
)
from channel_id.izu_field_misspecification import IzuFieldDistortion
from channel_id.izu_gradient_benchmark import IzuGradientLandscape, IzuGradientSite
from channel_id.izu_pooled_evidence import score_izu_gradient_candidates
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


def test_beta_smoothed_detection_estimate_handles_finite_calibration() -> None:
    design = DetectionCalibrationDesign(reference_visits_per_site=10)

    assert estimated_detection_probability(
        SiteDetectionCalibrationObservation("north", 10, 8), design
    ) == pytest.approx(9 / 12)
    assert estimated_detection_probability(
        SiteDetectionCalibrationObservation("north", 10, 0), design
    ) == pytest.approx(1 / 12)


def test_calibration_must_cover_each_dataset_site_once() -> None:
    design = DetectionCalibrationDesign(reference_visits_per_site=10)
    with pytest.raises(ValueError, match="must match"):
        calibrated_detection_probabilities(
            (SiteDetectionCalibrationObservation("north", 10, 8),),
            design,
            sites(),
        )


def test_virtual_calibration_dataset_is_reproducible_and_has_independent_rows() -> None:
    calibration_design = DetectionCalibrationDesign(reference_visits_per_site=40)
    distortion = IzuFieldDistortion(
        detection_mean_multiplier=0.60,
        site_detection_logit_sd=0.40,
    )
    first = simulate_izu_detection_calibration_dataset(
        GuideScenario.VISIT_ATTRACTION,
        settings(),
        landscape(),
        camera_design(),
        seed_design(),
        distortion,
        calibration_design,
        sites=sites(),
        seed=20260630,
    )
    second = simulate_izu_detection_calibration_dataset(
        GuideScenario.VISIT_ATTRACTION,
        settings(),
        landscape(),
        camera_design(),
        seed_design(),
        distortion,
        calibration_design,
        sites=sites(),
        seed=20260630,
    )

    assert first == second
    assert [item.site_id for item in first.calibration] == ["north", "south"]
    assert all(item.reference_visits == 40 for item in first.calibration)
    assert all(0 <= item.primary_detected_visits <= 40 for item in first.calibration)


def test_finite_calibration_recovers_visit_truth_when_nominal_detection_is_wrong() -> None:
    calibration_design = DetectionCalibrationDesign(reference_visits_per_site=1_000)
    distortion = IzuFieldDistortion(detection_mean_multiplier=0.45)
    generated = simulate_izu_detection_calibration_dataset(
        GuideScenario.VISIT_ATTRACTION,
        settings(),
        landscape(),
        camera_design(),
        seed_design(),
        distortion,
        calibration_design,
        sites=sites(),
        seed=20260630,
    )

    nominal = score_izu_gradient_candidates(
        candidates(),
        generated.dataset,
        settings(),
        landscape(),
        camera_design(),
        seed_design(),
    )
    calibrated = score_izu_gradient_candidates_with_detection_calibration(
        candidates(),
        generated,
        settings(),
        landscape(),
        camera_design(),
        seed_design(),
        calibration_design,
    )

    assert calibrated[0].scenario is GuideScenario.VISIT_ATTRACTION
    assert calibrated[0].total_log_likelihood > nominal[0].total_log_likelihood - 1e9


def test_calibration_benchmark_is_reproducible_and_improves_visit_recovery() -> None:
    calibration_design = DetectionCalibrationDesign(reference_visits_per_site=100)
    distortion = IzuFieldDistortion(detection_mean_multiplier=0.55)
    first = benchmark_izu_detection_calibration_recovery(
        GuideScenario.VISIT_ATTRACTION,
        candidates(),
        settings(),
        landscape(),
        camera_design(),
        seed_design(),
        distortion,
        calibration_design,
        sites=sites(),
        replicates=20,
        seed=20260630,
    )
    second = benchmark_izu_detection_calibration_recovery(
        GuideScenario.VISIT_ATTRACTION,
        candidates(),
        settings(),
        landscape(),
        camera_design(),
        seed_design(),
        distortion,
        calibration_design,
        sites=sites(),
        replicates=20,
        seed=20260630,
    )

    assert first == second
    assert first.calibrated_truth_top_rank_rate >= first.nominal_truth_top_rank_rate
    assert first.calibrated_unique_truth_top_rate >= first.nominal_unique_truth_top_rate
    assert first.calibrated_mean_truth_rank <= first.nominal_mean_truth_rank
