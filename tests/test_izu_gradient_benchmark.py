from channel_id.camera_visit_handling import CameraVisitHandlingDesign
from channel_id.guide_inbreeding import PostSeedSurvival
from channel_id.guide_paternal import PaternalGuideParameters
from channel_id.guide_scenarios import GuideScenario, ScenarioSettings, ScenarioYear
from channel_id.izu_gradient_benchmark import (
    GradientAnalysisMode,
    IzuGradientLandscape,
    IzuGradientSite,
    benchmark_izu_gradient_recovery,
    default_izu_gradient_sites,
    recover_izu_gradient_scenarios,
    settings_for_izu_gradient_site,
    simulate_izu_gradient_dataset,
)
from channel_id.nectar_guide import NectarGuideParameters, NectarGuideTrait
from channel_id.seed_set_paternity import SeedSetPaternityDesign


def template_settings() -> ScenarioSettings:
    return ScenarioSettings(
        trait=NectarGuideTrait(0.1, 0.4, 0.5),
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
        years=(ScenarioYear("template", 0.7),),
    )


def camera_design() -> CameraVisitHandlingDesign:
    return CameraVisitHandlingDesign(
        flower_camera_windows=2_000,
        exposure_multiplier_per_window=1.0,
        visit_detection_probability=1.0,
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


def landscape() -> IzuGradientLandscape:
    return IzuGradientLandscape(
        guide_contrast_north=0.1,
        guide_contrast_south=0.9,
        pollinator_service_north=0.8,
        pollinator_service_south=0.4,
        establishment_multiplier_north=1.0,
        establishment_multiplier_south=0.7,
    )


def test_default_izu_scaffold_is_ordered_and_explicitly_ordinal() -> None:
    sites = default_izu_gradient_sites()

    assert len(sites) == len({site.label for site in sites})
    assert [site.archipelago_position for site in sites] == sorted(
        site.archipelago_position for site in sites
    )
    assert sites[0].archipelago_position == 0.0
    assert sites[-1].archipelago_position == 1.0


def test_site_settings_use_or_ignore_the_declared_environment_gradient() -> None:
    north = IzuGradientSite("north", 0.0)
    south = IzuGradientSite("south", 1.0)

    calibrated_north = settings_for_izu_gradient_site(
        template_settings(), north, landscape(), GradientAnalysisMode.CALIBRATED
    )
    calibrated_south = settings_for_izu_gradient_site(
        template_settings(), south, landscape(), GradientAnalysisMode.CALIBRATED
    )
    flat_north = settings_for_izu_gradient_site(
        template_settings(), north, landscape(), GradientAnalysisMode.FLAT_ENVIRONMENT
    )
    flat_south = settings_for_izu_gradient_site(
        template_settings(), south, landscape(), GradientAnalysisMode.FLAT_ENVIRONMENT
    )

    assert calibrated_north.trait.guide_contrast == 0.1
    assert calibrated_south.trait.guide_contrast == 0.9
    assert calibrated_north.years[0].pollinator_service == 0.8
    assert calibrated_south.years[0].pollinator_service == 0.4
    assert flat_north.years[0].pollinator_service == flat_south.years[0].pollinator_service
    assert flat_north.years[0].establishment_multiplier == flat_south.years[0].establishment_multiplier


def test_virtual_gradient_dataset_contains_joint_observations_at_each_site() -> None:
    sites = (IzuGradientSite("north", 0.0), IzuGradientSite("south", 1.0))
    dataset = simulate_izu_gradient_dataset(
        GuideScenario.VISIT_ATTRACTION,
        template_settings(),
        landscape(),
        camera_design(),
        seed_design(),
        sites,
        seed=20260630,
    )

    assert dataset.truth is GuideScenario.VISIT_ATTRACTION
    assert [observation.site.label for observation in dataset.sites] == ["north", "south"]
    for observation in dataset.sites:
        assert len(observation.observations) == 4
        assert observation.camera.counts.detected_visits <= observation.camera.counts.true_visits
        assert observation.seed_set_paternity.seed_fates.total_ovules == seed_design().total_ovules


def test_calibrated_gradient_preserves_a_null_truth_better_than_flat_analysis() -> None:
    sites = (IzuGradientSite("north", 0.0), IzuGradientSite("south", 1.0))
    candidates = (
        GuideScenario.NULL,
        GuideScenario.VISIT_ATTRACTION,
        GuideScenario.HANDLING,
    )
    calibrated = benchmark_izu_gradient_recovery(
        GuideScenario.NULL,
        candidates,
        template_settings(),
        landscape(),
        camera_design(),
        seed_design(),
        sites,
        GradientAnalysisMode.CALIBRATED,
        replicates=20,
        seed=20260630,
    )
    flat = benchmark_izu_gradient_recovery(
        GuideScenario.NULL,
        candidates,
        template_settings(),
        landscape(),
        camera_design(),
        seed_design(),
        sites,
        GradientAnalysisMode.FLAT_ENVIRONMENT,
        replicates=20,
        seed=20260630,
    )

    assert calibrated.truth_retained_rate >= flat.truth_retained_rate
    assert calibrated.empty_compatible_set_rate <= flat.empty_compatible_set_rate
    assert 0.0 <= calibrated.truth_retained_rate <= 1.0
    assert 0.0 <= flat.truth_retained_rate <= 1.0


def test_gradient_recovery_is_reproducible_for_fixed_seed() -> None:
    sites = (IzuGradientSite("north", 0.0), IzuGradientSite("south", 1.0))
    candidates = (
        GuideScenario.NULL,
        GuideScenario.VISIT_ATTRACTION,
        GuideScenario.HANDLING,
    )
    first = benchmark_izu_gradient_recovery(
        GuideScenario.VISIT_ATTRACTION,
        candidates,
        template_settings(),
        landscape(),
        camera_design(),
        seed_design(),
        sites,
        GradientAnalysisMode.CALIBRATED,
        replicates=12,
        seed=20260630,
    )
    second = benchmark_izu_gradient_recovery(
        GuideScenario.VISIT_ATTRACTION,
        candidates,
        template_settings(),
        landscape(),
        camera_design(),
        seed_design(),
        sites,
        GradientAnalysisMode.CALIBRATED,
        replicates=12,
        seed=20260630,
    )

    assert first == second
