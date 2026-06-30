"""Field-style misspecification stress tests for pooled Izu evidence.

The pooled scorer in :mod:`izu_pooled_evidence` is internally consistent when
its data are generated under the same count and classification assumptions.
This module intentionally breaks that match *only in the generator* and then
scores the resulting aggregate observations with the original idealised model.

The purpose is not to claim that these values are measured field variances.  It
is to expose which unmodelled processes can make a camera/seed/paternity design
rank the wrong route:

* site-level visit and handling residual variation;
* maternal-level seed-fate overdispersion;
* wind/light-driven detection loss and heterogeneity;
* detection that depends on whether handling was legitimate;
* outcross-biased paternity non-resolution.

The current output remains one aggregate dataset per island.  These stress tests
are therefore a warning system for the later raw-record hierarchy, not a
substitute for fitting day, camera, plant, and fruit random effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, inf, log
from random import Random
from typing import Sequence

from .camera_visit_handling import (
    CameraVisitHandlingCounts,
    CameraVisitHandlingDesign,
    CameraVisitHandlingObservation,
    _camera_observations,
    _poisson_count,
)
from .guide_scenarios import (
    ScenarioMetric,
    ScenarioSettings,
    ScenarioSpec,
    simulate_guide_scenario,
)
from .izu_gradient_benchmark import (
    GradientAnalysisMode,
    IzuGradientDataset,
    IzuGradientLandscape,
    IzuGradientSite,
    IzuGradientSiteObservation,
    default_izu_gradient_sites,
    settings_for_izu_gradient_site,
    study_calibrated_observation_designs,
)
from .izu_pooled_evidence import score_izu_gradient_candidates, top_scoring_scenarios
from .joint_seed_fates import SeedFateCounts, sample_seed_fates, seed_fate_probabilities
from .seed_set_paternity import (
    PaternityCalls,
    SeedSetPaternityDesign,
    SeedSetPaternityObservation,
    _component_observations,
    _sample_mature_cross_types,
)


@dataclass(frozen=True)
class IzuFieldDistortion:
    """Unmodelled processes used only to generate virtual field observations.

    Every parameter is known to the generator but deliberately omitted from the
    pooled scorer.  Standard deviations are on a latent log or logit scale.

    ``detection_mean_multiplier`` represents an overall wind/light reduction in
    usable camera detection. ``site_detection_logit_sd`` represents residual
    variation in the resulting site-average detection after day/camera windows
    have been collapsed. ``legitimate_detection_relative`` permits legitimate
    contacts to be less detectable than other visits.

    ``outcross_unresolved_odds_multiplier`` multiplies the unresolved-call odds
    for outcross seeds relative to selfed seeds; 1.0 preserves the ideal model's
    cross-type-independent resolution assumption.
    """

    site_visit_log_sd: float = 0.0
    site_legitimate_logit_sd: float = 0.0
    maternal_seed_log_sd: float = 0.0
    detection_mean_multiplier: float = 1.0
    site_detection_logit_sd: float = 0.0
    legitimate_detection_relative: float = 1.0
    outcross_unresolved_odds_multiplier: float = 1.0

    def __post_init__(self) -> None:
        for name, value in (
            ("site_visit_log_sd", self.site_visit_log_sd),
            ("site_legitimate_logit_sd", self.site_legitimate_logit_sd),
            ("maternal_seed_log_sd", self.maternal_seed_log_sd),
            ("site_detection_logit_sd", self.site_detection_logit_sd),
        ):
            if value < 0.0:
                raise ValueError(f"{name} must be non-negative")
        if not 0.0 < self.detection_mean_multiplier <= 1.0:
            raise ValueError("detection_mean_multiplier must lie in (0, 1]")
        if not 0.0 < self.legitimate_detection_relative <= 1.0:
            raise ValueError("legitimate_detection_relative must lie in (0, 1]")
        if self.outcross_unresolved_odds_multiplier <= 0.0:
            raise ValueError("outcross_unresolved_odds_multiplier must be positive")


@dataclass(frozen=True)
class IzuFieldStressCase:
    """Named misspecification case used in a reproducible robustness suite."""

    label: str
    distortion: IzuFieldDistortion

    def __post_init__(self) -> None:
        if not self.label:
            raise ValueError("stress-case label must be non-empty")


@dataclass(frozen=True)
class IzuFieldStressRecoverySummary:
    """Pooled-ranking recovery under one generator-only field distortion."""

    truth: ScenarioSpec
    case: IzuFieldStressCase
    analysis_mode: GradientAnalysisMode
    replicates: int
    truth_top_rank_rate: float
    unique_truth_top_rate: float
    mean_truth_rank: float
    mean_truth_log_likelihood_gap: float
    no_finite_candidate_rate: float


def default_izu_field_stress_cases() -> tuple[IzuFieldStressCase, ...]:
    """Return a compact suite of distinct field-failure mechanisms.

    Numeric values are deliberately moderate stress assumptions, not estimates
    for the Izu Islands.  They should be swept or replaced by calibration data
    before field decisions are made.
    """

    return (
        IzuFieldStressCase("ideal", IzuFieldDistortion()),
        IzuFieldStressCase(
            "site_maternal_variation",
            IzuFieldDistortion(
                site_visit_log_sd=0.45,
                site_legitimate_logit_sd=0.50,
                maternal_seed_log_sd=0.50,
            ),
        ),
        IzuFieldStressCase(
            "wind_light_detection_loss",
            IzuFieldDistortion(
                detection_mean_multiplier=0.65,
                site_detection_logit_sd=0.80,
            ),
        ),
        IzuFieldStressCase(
            "handling_dependent_detection_loss",
            IzuFieldDistortion(legitimate_detection_relative=0.60),
        ),
        IzuFieldStressCase(
            "outcross_biased_unresolved",
            IzuFieldDistortion(outcross_unresolved_odds_multiplier=3.00),
        ),
        IzuFieldStressCase(
            "combined_field_stress",
            IzuFieldDistortion(
                site_visit_log_sd=0.45,
                site_legitimate_logit_sd=0.50,
                maternal_seed_log_sd=0.50,
                detection_mean_multiplier=0.65,
                site_detection_logit_sd=0.80,
                legitimate_detection_relative=0.60,
                outcross_unresolved_odds_multiplier=3.00,
            ),
        ),
    )


def _clip_open_probability(value: float) -> float:
    """Clip to an open unit interval for logit-scale perturbations."""

    return min(1.0 - 1e-12, max(1e-12, value))


def _logit(value: float) -> float:
    value = _clip_open_probability(value)
    return log(value / (1.0 - value))


def _inverse_logit(value: float) -> float:
    if value >= 0.0:
        return 1.0 / (1.0 + exp(-value))
    exponent = exp(value)
    return exponent / (1.0 + exponent)


def _mean_one_lognormal_multiplier(rng: Random, log_sd: float) -> float:
    """Draw a lognormal multiplier with mean one."""

    if log_sd == 0.0:
        return 1.0
    return exp(rng.normalvariate(-0.5 * log_sd * log_sd, log_sd))


def _perturbed_probability(rng: Random, baseline: float, logit_sd: float) -> float:
    """Draw a bounded residual variation around a declared probability."""

    if logit_sd == 0.0:
        return baseline
    return _inverse_logit(_logit(baseline) + rng.normalvariate(0.0, logit_sd))


def _outcross_unresolved_probability(
    self_unresolved_probability: float,
    outcross_odds_multiplier: float,
) -> float:
    """Apply a cross-type resolution bias on the unresolved-call odds scale."""

    if self_unresolved_probability == 0.0:
        return 0.0
    if self_unresolved_probability == 1.0:
        return 1.0
    odds = self_unresolved_probability / (1.0 - self_unresolved_probability)
    adjusted_odds = odds * outcross_odds_multiplier
    return adjusted_odds / (1.0 + adjusted_odds)


def _scaled_seed_expectations(
    outcross_expected: float,
    selfed_expected: float,
    multiplier: float,
    potential_ovules: int,
) -> tuple[float, float]:
    """Apply latent seed variation while retaining a valid per-fruit fate simplex."""

    outcross = outcross_expected * multiplier
    selfed = selfed_expected * multiplier
    total = outcross + selfed
    if total <= potential_ovules:
        return outcross, selfed
    scale = potential_ovules / total
    return outcross * scale, selfed * scale


def _sample_biased_paternity_calls(
    sampled_outcross: int,
    sampled_selfed: int,
    design: SeedSetPaternityDesign,
    distortion: IzuFieldDistortion,
    rng: Random,
) -> PaternityCalls:
    """Classify paternity calls with unmodelled cross-type-dependent resolution."""

    outcross_unresolved = _outcross_unresolved_probability(
        design.unresolved_probability,
        distortion.outcross_unresolved_odds_multiplier,
    )
    outcross_calls = 0
    self_calls = 0
    unresolved = 0
    for _ in range(sampled_outcross):
        if rng.random() < outcross_unresolved:
            unresolved += 1
        elif rng.random() < design.outcross_to_self_error:
            self_calls += 1
        else:
            outcross_calls += 1
    for _ in range(sampled_selfed):
        if rng.random() < design.unresolved_probability:
            unresolved += 1
        elif rng.random() < design.self_to_outcross_error:
            outcross_calls += 1
        else:
            self_calls += 1
    return PaternityCalls(
        outcross_calls=outcross_calls,
        self_calls=self_calls,
        unresolved_calls=unresolved,
        sampled_mature_seeds=sampled_outcross + sampled_selfed,
    )


def simulate_izu_field_misspecified_dataset(
    truth: ScenarioSpec,
    template_settings: ScenarioSettings,
    landscape: IzuGradientLandscape,
    camera_design: CameraVisitHandlingDesign,
    seed_design: SeedSetPaternityDesign,
    distortion: IzuFieldDistortion,
    sites: Sequence[IzuGradientSite] | None = None,
    seed: int = 0,
    study_familywise_confidence: float = 0.95,
) -> IzuGradientDataset:
    """Generate one virtual multi-island dataset under unmodelled field stress.

    The returned observations use the standard camera/seed interval conversion
    so they remain compatible with existing design tools.  The raw counts,
    however, were generated under ``distortion`` while the downstream pooled
    scorer is intentionally supplied only the original ideal designs.
    """

    selected_sites = tuple(default_izu_gradient_sites() if sites is None else sites)
    if not selected_sites:
        raise ValueError("at least one site is required")
    if len({site.label for site in selected_sites}) != len(selected_sites):
        raise ValueError("site labels must be unique")
    interval_camera_design, interval_seed_design = study_calibrated_observation_designs(
        camera_design,
        seed_design,
        len(selected_sites),
        study_familywise_confidence,
    )

    rng = Random(seed)
    observations: list[IzuGradientSiteObservation] = []
    for site in selected_sites:
        settings = settings_for_izu_gradient_site(
            template_settings,
            site,
            landscape,
            GradientAnalysisMode.CALIBRATED,
        )
        result = simulate_guide_scenario(truth, settings)
        label = site.label
        expected_visits = result.metric(ScenarioMetric.EXPECTED_VISITS, label)
        expected_legitimate = result.metric(ScenarioMetric.LEGITIMATE_CONTACT_FRACTION, label)
        expected_outcross = result.metric(ScenarioMetric.OUTCROSS_VIABLE_SEEDS, label)
        expected_selfed = result.metric(ScenarioMetric.SELFED_VIABLE_SEEDS, label)

        visit_multiplier = _mean_one_lognormal_multiplier(rng, distortion.site_visit_log_sd)
        legitimate_fraction = _perturbed_probability(
            rng,
            expected_legitimate,
            distortion.site_legitimate_logit_sd,
        )
        base_detection = min(
            1.0,
            camera_design.visit_detection_probability * distortion.detection_mean_multiplier,
        )
        nonlegitimate_detection = _perturbed_probability(
            rng,
            base_detection,
            distortion.site_detection_logit_sd,
        )
        legitimate_detection = min(
            1.0,
            nonlegitimate_detection * distortion.legitimate_detection_relative,
        )
        true_visits = _poisson_count(
            expected_visits * visit_multiplier * camera_design.total_exposure,
            rng,
        )
        true_legitimate = 0
        detected = 0
        called_legitimate = 0
        called_nonlegitimate = 0
        for _ in range(true_visits):
            legitimate = rng.random() < legitimate_fraction
            if legitimate:
                true_legitimate += 1
            detection_probability = legitimate_detection if legitimate else nonlegitimate_detection
            if rng.random() >= detection_probability:
                continue
            detected += 1
            if legitimate:
                call_legitimate = rng.random() < camera_design.legitimate_annotation_sensitivity
            else:
                call_legitimate = rng.random() >= camera_design.legitimate_annotation_specificity
            if call_legitimate:
                called_legitimate += 1
            else:
                called_nonlegitimate += 1
        camera_counts = CameraVisitHandlingCounts(
            true_visits=true_visits,
            true_legitimate_contacts=true_legitimate,
            detected_visits=detected,
            called_legitimate=called_legitimate,
            called_nonlegitimate=called_nonlegitimate,
        )
        camera_observation = CameraVisitHandlingObservation(
            counts=camera_counts,
            observations=_camera_observations(camera_counts, interval_camera_design, label),
        )

        total_outcross = 0
        total_selfed = 0
        total_other = 0
        total_outcross_calls = 0
        total_self_calls = 0
        total_unresolved = 0
        total_sampled = 0
        for _ in range(seed_design.maternal_individuals):
            maternal_multiplier = _mean_one_lognormal_multiplier(
                rng,
                distortion.maternal_seed_log_sd,
            )
            outcross_per_fruit, selfed_per_fruit = _scaled_seed_expectations(
                expected_outcross,
                expected_selfed,
                maternal_multiplier,
                seed_design.potential_ovules_per_fruit,
            )
            outcross_probability, selfed_probability, _ = seed_fate_probabilities(
                outcross_per_fruit,
                selfed_per_fruit,
                seed_design.potential_ovules_per_fruit,
            )
            for _ in range(seed_design.fruits_per_maternal):
                fruit = sample_seed_fates(
                    outcross_probability,
                    selfed_probability,
                    seed_design.potential_ovules_per_fruit,
                    rng,
                )
                total_outcross += fruit.outcross_viable
                total_selfed += fruit.selfed_viable
                total_other += fruit.other
                sampled_outcross, sampled_selfed = _sample_mature_cross_types(
                    fruit.outcross_viable,
                    fruit.selfed_viable,
                    min(
                        seed_design.genotyped_mature_seeds_per_fruit,
                        fruit.outcross_viable + fruit.selfed_viable,
                    ),
                    rng,
                )
                calls = _sample_biased_paternity_calls(
                    sampled_outcross,
                    sampled_selfed,
                    seed_design,
                    distortion,
                    rng,
                )
                total_outcross_calls += calls.outcross_calls
                total_self_calls += calls.self_calls
                total_unresolved += calls.unresolved_calls
                total_sampled += calls.sampled_mature_seeds
        seed_fates = SeedFateCounts(
            outcross_viable=total_outcross,
            selfed_viable=total_selfed,
            other=total_other,
            total_ovules=seed_design.total_ovules,
        )
        paternity_calls = PaternityCalls(
            outcross_calls=total_outcross_calls,
            self_calls=total_self_calls,
            unresolved_calls=total_unresolved,
            sampled_mature_seeds=total_sampled,
        )
        seed_observation = SeedSetPaternityObservation(
            seed_fates=seed_fates,
            paternity_calls=paternity_calls,
            observations=_component_observations(
                seed_fates,
                paternity_calls,
                interval_seed_design,
                label,
            ),
        )
        observations.append(
            IzuGradientSiteObservation(
                site=site,
                truth_settings=settings,
                camera=camera_observation,
                seed_set_paternity=seed_observation,
            )
        )
    return IzuGradientDataset(truth=truth, sites=tuple(observations))


def benchmark_izu_field_stress_recovery(
    truth: ScenarioSpec,
    candidates: Sequence[ScenarioSpec],
    template_settings: ScenarioSettings,
    landscape: IzuGradientLandscape,
    camera_design: CameraVisitHandlingDesign,
    seed_design: SeedSetPaternityDesign,
    case: IzuFieldStressCase,
    sites: Sequence[IzuGradientSite] | None = None,
    analysis_mode: GradientAnalysisMode = GradientAnalysisMode.CALIBRATED,
    replicates: int = 100,
    seed: int = 0,
) -> IzuFieldStressRecoverySummary:
    """Stress-test ideal pooled scoring against generator-only field deviations."""

    if replicates < 1:
        raise ValueError("replicates must be positive")
    if truth not in candidates:
        raise ValueError("truth must be included in candidates")
    rng = Random(seed)
    truth_top = 0
    unique_truth_top = 0
    truth_rank_total = 0
    truth_gap_total = 0.0
    no_finite = 0
    for _ in range(replicates):
        dataset = simulate_izu_field_misspecified_dataset(
            truth,
            template_settings,
            landscape,
            camera_design,
            seed_design,
            case.distortion,
            sites=sites,
            seed=rng.randrange(2**63),
        )
        evidence = score_izu_gradient_candidates(
            candidates,
            dataset,
            template_settings,
            landscape,
            camera_design,
            seed_design,
            analysis_mode,
        )
        top = top_scoring_scenarios(evidence)
        if not top:
            no_finite += 1
            truth_rank_total += len(candidates) + 1
            continue
        truth_evidence = next(item for item in evidence if item.scenario == truth)
        truth_rank = 1 + sum(
            item.total_log_likelihood > truth_evidence.total_log_likelihood + 1e-9
            for item in evidence
        )
        truth_rank_total += truth_rank
        if truth in top:
            truth_top += 1
        if top == (truth,):
            unique_truth_top += 1
        alternatives = [
            item.total_log_likelihood
            for item in evidence
            if item.scenario != truth
        ]
        if alternatives and truth_evidence.total_log_likelihood > -inf:
            truth_gap_total += truth_evidence.total_log_likelihood - max(alternatives)

    return IzuFieldStressRecoverySummary(
        truth=truth,
        case=case,
        analysis_mode=analysis_mode,
        replicates=replicates,
        truth_top_rank_rate=truth_top / replicates,
        unique_truth_top_rate=unique_truth_top / replicates,
        mean_truth_rank=truth_rank_total / replicates,
        mean_truth_log_likelihood_gap=truth_gap_total / replicates,
        no_finite_candidate_rate=no_finite / replicates,
    )
