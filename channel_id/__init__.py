"""Tools for declared Campanula channel-identification studies."""

from .camera_visit_handling import (
    CameraVisitHandlingCounts,
    CameraVisitHandlingDesign,
    CameraVisitHandlingObservation,
    CameraVisitHandlingRecoverySummary,
    benchmark_camera_visit_handling_recovery,
    corrected_legitimate_fraction_interval,
    poisson_mean_interval,
    simulate_camera_visit_handling_observation,
)
from .discrimination import MeasurementOption, MeasurementRanking, rank_measurements
from .guide_design_power import (
    DesignPowerResult,
    MeasurementDesign,
    MeasurementPlan,
    MeasurementPlanRanking,
    ScenarioSurvivalRate,
    evaluate_measurement_plan,
    rank_measurement_plans,
    sweep_common_sample_sizes,
)
from .guide_inbreeding import PostSeedResult, PostSeedSurvival, apply_post_seed_survival
from .guide_multiguild import MultiguildGuideResult, PollinatorGuild, simulate_multiguild_guide_response
from .guide_paternal import PaternalGuideParameters, PaternalGuideResult, simulate_guide_paternal_fitness
from .guide_phenotype import FamilyGuideObservation, GuideReactionNorm
from .guide_scenarios import (
    GuideRoutes,
    GuideScenario,
    ScenarioCompatibility,
    ScenarioMetric,
    ScenarioObservation,
    ScenarioResult,
    ScenarioSettings,
    ScenarioSpec,
    ScenarioYear,
    ScenarioYearResult,
    assess_scenario_compatibility,
    core_maternal_scenarios,
    recover_compatible_scenarios,
    routes_for,
    simulate_guide_scenario,
)
from .guide_spatial import Patch, SpatialRecruitmentResult, distribute_seeds_to_patches
from .guide_temporal import TemporalFitnessSummary, YearPerformance, summarise_temporal_fitness
from .izu_gradient_benchmark import (
    GradientAnalysisMode,
    IzuGradientDataset,
    IzuGradientLandscape,
    IzuGradientRecoverySummary,
    IzuGradientSite,
    IzuGradientSiteObservation,
    benchmark_izu_gradient_recovery,
    default_izu_gradient_sites,
    recover_izu_gradient_scenarios,
    settings_for_izu_gradient_site,
    simulate_izu_gradient_dataset,
    study_calibrated_observation_designs,
)
from .izu_pooled_evidence import (
    IzuPooledEvidenceRecoverySummary,
    IzuScenarioEvidence,
    IzuSiteLogLikelihood,
    benchmark_izu_pooled_evidence_recovery,
    binomial_log_probability,
    multinomial_log_probability,
    paternity_call_probabilities,
    poisson_log_probability,
    score_izu_gradient_candidates,
    top_scoring_scenarios,
)
from .izu_sensitivity_report import (
    IzuObservationPlan,
    IzuRecoveryThresholds,
    IzuSensitivityReport,
    IzuSensitivityRow,
    IzuVirtualWorld,
    crossed_izu_observation_plans,
    default_izu_virtual_worlds,
    report_as_markdown_table,
    run_izu_sensitivity_report,
)
from .joint_seed_fates import (
    JointSeedFateRecoverySummary,
    SeedFateCounts,
    SeedFateObservationDesign,
    benchmark_joint_seed_fate_recovery,
    joint_seed_fate_observations,
    sample_seed_fates,
    seed_fate_probabilities,
    wilson_interval,
)
from .life_history import (
    CompatibilityResult,
    LifeHistoryParameters,
    LifeHistoryResult,
    Metric,
    ObservationInterval,
    ParameterGrid,
    Regime,
    SimulationCase,
    TraitState,
    assess_compatibility,
    retain_compatible_candidates,
    simulate_life_history,
)
from .nectar_guide import (
    GuideContrast,
    GuideSelectionDirection,
    NectarGuideParameters,
    NectarGuideRegime,
    NectarGuideResult,
    NectarGuideTrait,
    compare_guide_phenotypes,
    simulate_nectar_guide_life_history,
)
from .readiness import (
    ChannelDesign,
    ChannelReadiness,
    ChannelReadinessReport,
    PollinatorComponentStatus,
    assess_channel_readiness,
)
from .seed_set_paternity import (
    PaternityCalls,
    SeedSetPaternityDesign,
    SeedSetPaternityObservation,
    SeedSetPaternityRecoverySummary,
    benchmark_seed_set_paternity_recovery,
    corrected_outcross_fraction_interval,
    simulate_seed_set_paternity_observation,
)

__all__ = [
    "ChannelDesign", "ChannelReadiness", "ChannelReadinessReport", "PollinatorComponentStatus", "assess_channel_readiness",
    "MeasurementOption", "MeasurementRanking", "rank_measurements",
    "CompatibilityResult", "LifeHistoryParameters", "LifeHistoryResult", "Metric", "ObservationInterval", "ParameterGrid", "Regime", "SimulationCase", "TraitState", "assess_compatibility", "retain_compatible_candidates", "simulate_life_history",
    "GuideContrast", "GuideSelectionDirection", "NectarGuideParameters", "NectarGuideRegime", "NectarGuideResult", "NectarGuideTrait", "compare_guide_phenotypes", "simulate_nectar_guide_life_history",
    "PaternalGuideParameters", "PaternalGuideResult", "simulate_guide_paternal_fitness",
    "PollinatorGuild", "MultiguildGuideResult", "simulate_multiguild_guide_response",
    "PostSeedSurvival", "PostSeedResult", "apply_post_seed_survival",
    "YearPerformance", "TemporalFitnessSummary", "summarise_temporal_fitness",
    "GuideReactionNorm", "FamilyGuideObservation",
    "Patch", "SpatialRecruitmentResult", "distribute_seeds_to_patches",
    "GuideScenario", "GuideRoutes", "ScenarioSpec", "routes_for", "core_maternal_scenarios", "ScenarioCompatibility", "ScenarioMetric", "ScenarioObservation", "ScenarioResult", "ScenarioSettings", "ScenarioYear", "ScenarioYearResult", "assess_scenario_compatibility", "recover_compatible_scenarios", "simulate_guide_scenario",
    "MeasurementDesign", "MeasurementPlan", "ScenarioSurvivalRate", "DesignPowerResult", "MeasurementPlanRanking", "evaluate_measurement_plan", "rank_measurement_plans", "sweep_common_sample_sizes",
    "SeedFateObservationDesign", "SeedFateCounts", "JointSeedFateRecoverySummary", "seed_fate_probabilities", "sample_seed_fates", "wilson_interval", "joint_seed_fate_observations", "benchmark_joint_seed_fate_recovery",
    "SeedSetPaternityDesign", "PaternityCalls", "SeedSetPaternityObservation", "SeedSetPaternityRecoverySummary", "corrected_outcross_fraction_interval", "simulate_seed_set_paternity_observation", "benchmark_seed_set_paternity_recovery",
    "CameraVisitHandlingDesign", "CameraVisitHandlingCounts", "CameraVisitHandlingObservation", "CameraVisitHandlingRecoverySummary", "poisson_mean_interval", "corrected_legitimate_fraction_interval", "simulate_camera_visit_handling_observation", "benchmark_camera_visit_handling_recovery",
    "IzuGradientSite", "IzuGradientLandscape", "GradientAnalysisMode", "IzuGradientSiteObservation", "IzuGradientDataset", "IzuGradientRecoverySummary", "default_izu_gradient_sites", "settings_for_izu_gradient_site", "study_calibrated_observation_designs", "simulate_izu_gradient_dataset", "recover_izu_gradient_scenarios", "benchmark_izu_gradient_recovery",
    "IzuObservationPlan", "IzuVirtualWorld", "IzuRecoveryThresholds", "IzuSensitivityRow", "IzuSensitivityReport", "crossed_izu_observation_plans", "default_izu_virtual_worlds", "run_izu_sensitivity_report", "report_as_markdown_table",
    "IzuSiteLogLikelihood", "IzuScenarioEvidence", "IzuPooledEvidenceRecoverySummary", "poisson_log_probability", "binomial_log_probability", "multinomial_log_probability", "paternity_call_probabilities", "score_izu_gradient_candidates", "top_scoring_scenarios", "benchmark_izu_pooled_evidence_recovery",
]
