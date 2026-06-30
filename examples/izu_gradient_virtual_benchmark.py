"""Compare calibrated and ignored environment gradients before field data exist."""

from channel_id.camera_visit_handling import CameraVisitHandlingDesign
from channel_id.guide_inbreeding import PostSeedSurvival
from channel_id.guide_paternal import PaternalGuideParameters
from channel_id.guide_scenarios import GuideRoutes, GuideScenario, ScenarioSettings, ScenarioYear
from channel_id.izu_gradient_benchmark import (
    GradientAnalysisMode,
    IzuGradientLandscape,
    benchmark_izu_gradient_recovery,
)
from channel_id.nectar_guide import NectarGuideParameters, NectarGuideTrait
from channel_id.seed_set_paternity import SeedSetPaternityDesign


def settings() -> ScenarioSettings:
    return ScenarioSettings(
        trait=NectarGuideTrait(0.10, 0.40, 0.50),
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


def main() -> None:
    landscape = IzuGradientLandscape(
        guide_contrast_north=0.10,
        guide_contrast_south=0.90,
        pollinator_service_north=0.80,
        pollinator_service_south=0.40,
        establishment_multiplier_north=1.00,
        establishment_multiplier_south=0.70,
    )
    camera = CameraVisitHandlingDesign(
        flower_camera_windows=1_000,
        exposure_multiplier_per_window=1.0,
        visit_detection_probability=0.85,
        legitimate_annotation_sensitivity=0.90,
        legitimate_annotation_specificity=0.95,
    )
    seed = SeedSetPaternityDesign(
        maternal_individuals=40,
        fruits_per_maternal=2,
        potential_ovules_per_fruit=10,
        genotyped_mature_seeds_per_fruit=3,
    )
    truth = GuideRoutes("visit_assurance", visit_attraction=True, assurance=True)
    candidates = (
        GuideScenario.NULL,
        GuideScenario.VISIT_ATTRACTION,
        GuideScenario.HANDLING,
        GuideScenario.ASSURANCE,
        truth,
    )

    for mode in (GradientAnalysisMode.CALIBRATED, GradientAnalysisMode.FLAT_ENVIRONMENT):
        summary = benchmark_izu_gradient_recovery(
            truth=truth,
            candidates=candidates,
            template_settings=settings(),
            landscape=landscape,
            camera_design=camera,
            seed_design=seed,
            analysis_mode=mode,
            replicates=500,
            seed=20260630,
        )
        print(mode.value)
        print(summary)


if __name__ == "__main__":
    main()
