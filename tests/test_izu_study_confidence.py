import pytest

from channel_id.camera_visit_handling import CameraVisitHandlingDesign
from channel_id.izu_gradient_benchmark import study_calibrated_observation_designs
from channel_id.seed_set_paternity import SeedSetPaternityDesign


def camera_design() -> CameraVisitHandlingDesign:
    return CameraVisitHandlingDesign(
        flower_camera_windows=100,
        exposure_multiplier_per_window=1.0,
        visit_detection_probability=0.9,
        legitimate_annotation_sensitivity=0.9,
        legitimate_annotation_specificity=0.95,
        familywise_confidence=0.95,
    )


def seed_design() -> SeedSetPaternityDesign:
    return SeedSetPaternityDesign(
        maternal_individuals=10,
        fruits_per_maternal=2,
        potential_ovules_per_fruit=10,
        genotyped_mature_seeds_per_fruit=3,
        familywise_confidence=0.95,
    )


def test_study_confidence_is_split_over_two_modules_and_all_sites() -> None:
    camera, seed = study_calibrated_observation_designs(
        camera_design(),
        seed_design(),
        site_count=8,
        study_familywise_confidence=0.95,
    )

    # 0.05 total error / (8 sites × 2 observation modules).
    assert camera.familywise_confidence == pytest.approx(1.0 - 0.05 / 16.0)
    assert seed.familywise_confidence == pytest.approx(1.0 - 0.05 / 16.0)
    # Each module then divides its error over its own two component intervals.
    assert camera.marginal_confidence == pytest.approx(1.0 - 0.05 / 32.0)
    assert seed.marginal_confidence == pytest.approx(1.0 - 0.05 / 32.0)


def test_study_confidence_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="site_count"):
        study_calibrated_observation_designs(camera_design(), seed_design(), 0)
    with pytest.raises(ValueError, match="study_familywise_confidence"):
        study_calibrated_observation_designs(camera_design(), seed_design(), 1, 1.0)
