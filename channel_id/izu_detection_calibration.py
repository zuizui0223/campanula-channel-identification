"""Virtual recovery tests for finite camera-detection calibration.

The field-misspecification benchmark showed that visit-mediated routes can be
mis-ranked when wind/light changes effective camera detection but the pooled
likelihood keeps the nominal detection probability fixed.  This module tests a
specific remedy under deliberately favourable, explicit assumptions:

* each virtual island has an effective camera-condition stratum;
* an independent reference stream supplies a finite number of known visit
  opportunities in that stratum;
* the primary workflow detects some of those opportunities;
* a beta-smoothed detection estimate replaces the nominal detection probability
  in the *visit-count* term of the pooled likelihood.

The reference stream is treated as ground truth in this virtual experiment.
That is an optimistic calibration boundary.  In the field, independent reference
scoring, high-quality clips, or another prespecified source must justify that
assumption, and wind × light strata should replace the collapsed site-condition
strata used here.

Handling, seed fate, and paternity terms intentionally remain unchanged.  This
asks a narrow question: can finite calibration of visit detection recover the
visit-rate part of the likelihood under the wind/light failure mode?
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, isfinite, log
from random import Random
from typing import Mapping, Sequence

from .camera_visit_handling import (
    CameraVisitHandlingCounts,
    CameraVisitHandlingDesign,
    CameraVisitHandlingObservation,
    _camera_observations,
    _poisson_count,
)
from .guide_scenarios import ScenarioMetric, ScenarioSettings, ScenarioSpec, simulate_guide_scenario
from .izu_field_misspecification import IzuFieldDistortion
from .izu_gradient_benchmark import (
    GradientAnalysisMode,
    IzuGradientDataset,
    IzuGradientLandscape,
    IzuGradientSite,
    IzuGradientSiteObservation,
    default_izu_gradient_sites,
    settings_for_izu_gradient_site,
    simulate_izu_gradient_dataset,
    study_calibrated_observation_designs,
)
from .izu_pooled_evidence import (
    IzuScenarioEvidence,
    IzuSiteLogLikelihood,
    binomial_log_probability,
    multinomial_log_probability,
    paternity_call_probabilities,
    poisson_log_probability,
    score_izu_gradient_candidates,
    top_scoring_scenarios,
)
from .joint_seed_fates import seed_fate_probabilities
from .seed_set_paternity import SeedSetPaternityDesign


@dataclass(frozen=True)
class DetectionCalibrationDesign:
    """Independent reference-visit sample used to estimate detection per stratum.

    ``reference_visits_per_site`` is the number of externally reviewed known
    visit opportunities available in every virtual site-condition stratum.  It
    is not nominal video duration.  A reference scorer must first establish that
    those events were present.
    """

    reference_visits_per_site: int
    beta_prior_alpha: float = 1.0
    beta_prior_beta: float = 1.0

    def __post_init__(self) -> None:
        if self.reference_visits_per_site < 1:
            raise ValueError("reference_visits_per_site must be positive")
        if self.beta_prior_alpha <= 0.0 or self.beta_prior_beta <= 0.0:
            raise ValueError("beta prior parameters must be positive")


@dataclass(frozen=True)
class SiteDetectionCalibrationObservation:
    """One independent calibration result for an effective site-condition stratum."""

    site_id: str
    reference_visits: int
    primary_detected_visits: int

    def __post_init__(self) -> None:
        if not self.site_id:
            raise ValueError("site_id must be non-empty")
        if self.reference_visits < 1:
            raise ValueError("reference_visits must be positive")
        if not 0 <= self.primary_detected_visits <= self.reference_visits:
            raise ValueError("primary_detected_visits must lie between zero and reference_visits")


@dataclass(frozen=True)
class IzuDetectionCalibrationDataset:
    """Virtual field dataset plus independent finite detection calibrations."""

    dataset: IzuGradientDataset
    calibration: tuple[SiteDetectionCalibrationObservation, ...]


@dataclass(frozen=True)
class IzuDetectionCalibrationRecoverySummary:
    """Compare nominal versus finite-calibration visit-detection recovery."""

    truth: ScenarioSpec
    analysis_mode: GradientAnalysisMode
    replicates: int
    reference_visits_per_site: int
    nominal_truth_top_rank_rate: float
    calibrated_truth_top_rank_rate: float
    nominal_unique_truth_top_rate: float
    calibrated_unique_truth_top_rate: float
    nominal_mean_truth_rank: float
    calibrated_mean_truth_rank: float
    nominal_mean_truth_log_likelihood_gap: float
    calibrated_mean_truth_log_likelihood_gap: float


def _clip_open_probability(value: float) -> float:
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
    if log_sd == 0.0:
        return 1.0
    return exp(rng.normalvariate(-0.5 * log_sd * log_sd, log_sd))


def _perturbed_probability(rng: Random, baseline: float, logit_sd: float) -> float:
    if logit_sd == 0.0:
        return baseline
    return _inverse_logit(_logit(baseline) + rng.normalvariate(0.0, logit_sd))


def _bernoulli_count(trials: int, probability: float, rng: Random) -> int:
    if trials < 0:
        raise ValueError("trials must be non-negative")
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must lie in [0, 1]")
    return sum(rng.random() < probability for _ in range(trials))


def estimated_detection_probability(
    observation: SiteDetectionCalibrationObservation,
    design: DetectionCalibrationDesign,
) -> float:
    """Posterior mean under a beta-binomial calibration model.

    A symmetric Beta(1, 1) default prevents a finite calibration subset with
    zero or complete primary detections from yielding an impossible 0/1 rate in
    the Poisson likelihood.  This is a small-sample stabiliser, not a claim that
    the prior is field-validated.
    """

    return (
        observation.primary_detected_visits + design.beta_prior_alpha
    ) / (
        observation.reference_visits + design.beta_prior_alpha + design.beta_prior_beta
    )


def calibrated_detection_probabilities(
    calibration: Sequence[SiteDetectionCalibrationObservation],
    design: DetectionCalibrationDesign,
    sites: Sequence[IzuGradientSite],
) -> dict[str, float]:
    """Estimate one effective detection probability for every selected site."""

    expected_ids = {site.label for site in sites}
    observed_ids = {item.site_id for item in calibration}
    if len(observed_ids) != len(calibration):
        raise ValueError("calibration site IDs must be unique")
    if observed_ids != expected_ids:
        missing = sorted(expected_ids - observed_ids)
        extra = sorted(observed_ids - expected_ids)
        raise ValueError(f"calibration sites must match dataset sites; missing={missing}, extra={extra}")
    return {
        item.site_id: estimated_detection_probability(item, design)
        for item in calibration
    }


def simulate_izu_detection_calibration_dataset(
    truth: ScenarioSpec,
    template_settings: ScenarioSettings,
    landscape: IzuGradientLandscape,
    camera_design: CameraVisitHandlingDesign,
    seed_design: SeedSetPaternityDesign,
    distortion: IzuFieldDistortion,
    calibration_design: DetectionCalibrationDesign,
    sites: Sequence[IzuGradientSite] | None = None,
    seed: int = 0,
    study_familywise_confidence: float = 0.95,
) -> IzuDetectionCalibrationDataset:
    """Simulate field-style camera counts and an independent finite calibration subset.

    Seed fate and paternity are generated by the established Izu generator.  The
    camera channel is regenerated under the supplied detection distortion, while
    calibration reference visits are sampled independently from the same hidden
    effective detection process.  The scorer never receives that hidden process,
    only the finite calibration counts.
    """

    selected_sites = tuple(default_izu_gradient_sites() if sites is None else sites)
    if not selected_sites:
        raise ValueError("at least one site is required")
    if len({site.label for site in selected_sites}) != len(selected_sites):
        raise ValueError("site labels must be unique")

    rng = Random(seed)
    ideal_dataset = simulate_izu_gradient_dataset(
        truth,
        template_settings,
        landscape,
        camera_design,
        seed_design,
        sites=selected_sites,
        seed=rng.randrange(2**63),
        study_familywise_confidence=study_familywise_confidence,
    )
    interval_camera_design, _ = study_calibrated_observation_designs(
        camera_design,
        seed_design,
        len(selected_sites),
        study_familywise_confidence,
    )

    regenerated_sites: list[IzuGradientSiteObservation] = []
    calibration: list[SiteDetectionCalibrationObservation] = []
    for observed in ideal_dataset.sites:
        site = observed.site
        label = site.label
        settings = settings_for_izu_gradient_site(
            template_settings,
            site,
            landscape,
            GradientAnalysisMode.CALIBRATED,
        )
        result = simulate_guide_scenario(truth, settings)
        expected_visits = result.metric(ScenarioMetric.EXPECTED_VISITS, label)
        expected_legitimate_fraction = result.metric(
            ScenarioMetric.LEGITIMATE_CONTACT_FRACTION,
            label,
        )

        visit_multiplier = _mean_one_lognormal_multiplier(rng, distortion.site_visit_log_sd)
        legitimate_fraction = _perturbed_probability(
            rng,
            expected_legitimate_fraction,
            distortion.site_legitimate_logit_sd,
        )
        nominal_detection = min(
            1.0,
            camera_design.visit_detection_probability * distortion.detection_mean_multiplier,
        )
        nonlegitimate_detection = _perturbed_probability(
            rng,
            nominal_detection,
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
            is_legitimate = rng.random() < legitimate_fraction
            if is_legitimate:
                true_legitimate += 1
            detection = legitimate_detection if is_legitimate else nonlegitimate_detection
            if rng.random() >= detection:
                continue
            detected += 1
            if is_legitimate:
                called_as_legitimate = rng.random() < camera_design.legitimate_annotation_sensitivity
            else:
                called_as_legitimate = rng.random() >= camera_design.legitimate_annotation_specificity
            if called_as_legitimate:
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

        reference_detected = 0
        for _ in range(calibration_design.reference_visits_per_site):
            is_legitimate = rng.random() < legitimate_fraction
            detection = legitimate_detection if is_legitimate else nonlegitimate_detection
            reference_detected += rng.random() < detection
        calibration.append(
            SiteDetectionCalibrationObservation(
                site_id=label,
                reference_visits=calibration_design.reference_visits_per_site,
                primary_detected_visits=reference_detected,
            )
        )
        regenerated_sites.append(
            IzuGradientSiteObservation(
                site=site,
                truth_settings=observed.truth_settings,
                camera=camera_observation,
                seed_set_paternity=observed.seed_set_paternity,
            )
        )

    return IzuDetectionCalibrationDataset(
        dataset=IzuGradientDataset(truth=truth, sites=tuple(regenerated_sites)),
        calibration=tuple(calibration),
    )


def _site_log_likelihood_with_detection(
    candidate: ScenarioSpec,
    dataset: IzuGradientDataset,
    site_index: int,
    template_settings: ScenarioSettings,
    landscape: IzuGradientLandscape,
    camera_design: CameraVisitHandlingDesign,
    seed_design: SeedSetPaternityDesign,
    analysis_mode: GradientAnalysisMode,
    detection_probability: float,
) -> IzuSiteLogLikelihood:
    if not 0.0 < detection_probability <= 1.0:
        raise ValueError("detection_probability must lie in (0, 1]")
    observed = dataset.sites[site_index]
    settings = settings_for_izu_gradient_site(
        template_settings,
        observed.site,
        landscape,
        analysis_mode,
    )
    result = simulate_guide_scenario(candidate, settings)
    label = observed.site.label
    expected_visits = result.metric(ScenarioMetric.EXPECTED_VISITS, label)
    expected_legitimate_fraction = result.metric(
        ScenarioMetric.LEGITIMATE_CONTACT_FRACTION,
        label,
    )
    expected_outcross = result.metric(ScenarioMetric.OUTCROSS_VIABLE_SEEDS, label)
    expected_selfed = result.metric(ScenarioMetric.SELFED_VIABLE_SEEDS, label)

    camera_counts = observed.camera.counts
    visit_log_likelihood = poisson_log_probability(
        camera_counts.detected_visits,
        expected_visits * camera_design.total_exposure * detection_probability,
    )
    called_legitimate_probability = (
        expected_legitimate_fraction * camera_design.legitimate_annotation_sensitivity
        + (1.0 - expected_legitimate_fraction)
        * (1.0 - camera_design.legitimate_annotation_specificity)
    )
    handling_log_likelihood = binomial_log_probability(
        camera_counts.called_legitimate,
        camera_counts.detected_visits,
        called_legitimate_probability,
    )

    outcross_probability, selfed_probability, other_probability = seed_fate_probabilities(
        expected_outcross,
        expected_selfed,
        seed_design.potential_ovules_per_fruit,
    )
    seed_fates = observed.seed_set_paternity.seed_fates
    seed_fate_log_likelihood = multinomial_log_probability(
        (seed_fates.outcross_viable, seed_fates.selfed_viable, seed_fates.other),
        (outcross_probability, selfed_probability, other_probability),
    )
    mature_probability = outcross_probability + selfed_probability
    outcross_fraction = 0.0 if mature_probability == 0.0 else outcross_probability / mature_probability
    paternity_probabilities = paternity_call_probabilities(outcross_fraction, seed_design)
    paternity_calls = observed.seed_set_paternity.paternity_calls
    paternity_log_likelihood = multinomial_log_probability(
        (
            paternity_calls.outcross_calls,
            paternity_calls.self_calls,
            paternity_calls.unresolved_calls,
        ),
        paternity_probabilities,
    )
    return IzuSiteLogLikelihood(
        site=observed.site,
        visit_log_likelihood=visit_log_likelihood,
        handling_log_likelihood=handling_log_likelihood,
        seed_fate_log_likelihood=seed_fate_log_likelihood,
        paternity_log_likelihood=paternity_log_likelihood,
    )


def score_izu_gradient_candidates_with_detection_calibration(
    candidates: Sequence[ScenarioSpec],
    calibration_dataset: IzuDetectionCalibrationDataset,
    template_settings: ScenarioSettings,
    landscape: IzuGradientLandscape,
    camera_design: CameraVisitHandlingDesign,
    seed_design: SeedSetPaternityDesign,
    calibration_design: DetectionCalibrationDesign,
    analysis_mode: GradientAnalysisMode = GradientAnalysisMode.CALIBRATED,
) -> tuple[IzuScenarioEvidence, ...]:
    """Rank candidates after replacing nominal with finite calibrated detection rates."""

    dataset = calibration_dataset.dataset
    if not candidates:
        raise ValueError("at least one candidate is required")
    if len(set(candidates)) != len(candidates):
        raise ValueError("candidate scenarios must be unique")
    detection = calibrated_detection_probabilities(
        calibration_dataset.calibration,
        calibration_design,
        tuple(item.site for item in dataset.sites),
    )
    scored: list[IzuScenarioEvidence] = []
    for candidate in candidates:
        sites = tuple(
            _site_log_likelihood_with_detection(
                candidate,
                dataset,
                index,
                template_settings,
                landscape,
                camera_design,
                seed_design,
                analysis_mode,
                detection[dataset.sites[index].site.label],
            )
            for index in range(len(dataset.sites))
        )
        scored.append(IzuScenarioEvidence(candidate, analysis_mode, sites))
    return tuple(sorted(scored, key=lambda item: item.total_log_likelihood, reverse=True))


def _rank_and_gap(
    evidence: Sequence[IzuScenarioEvidence],
    truth: ScenarioSpec,
) -> tuple[bool, bool, float, float]:
    top = top_scoring_scenarios(evidence)
    truth_evidence = next(item for item in evidence if item.scenario == truth)
    rank = 1 + sum(
        item.total_log_likelihood > truth_evidence.total_log_likelihood + 1e-9
        for item in evidence
    )
    alternatives = [item.total_log_likelihood for item in evidence if item.scenario != truth]
    gap = truth_evidence.total_log_likelihood - max(alternatives) if alternatives else 0.0
    return truth in top, top == (truth,), rank, gap


def benchmark_izu_detection_calibration_recovery(
    truth: ScenarioSpec,
    candidates: Sequence[ScenarioSpec],
    template_settings: ScenarioSettings,
    landscape: IzuGradientLandscape,
    camera_design: CameraVisitHandlingDesign,
    seed_design: SeedSetPaternityDesign,
    distortion: IzuFieldDistortion,
    calibration_design: DetectionCalibrationDesign,
    sites: Sequence[IzuGradientSite] | None = None,
    analysis_mode: GradientAnalysisMode = GradientAnalysisMode.CALIBRATED,
    replicates: int = 100,
    seed: int = 0,
) -> IzuDetectionCalibrationRecoverySummary:
    """Compare nominal and finite-calibrated detection scoring over virtual replicates."""

    if replicates < 1:
        raise ValueError("replicates must be positive")
    if truth not in candidates:
        raise ValueError("truth must be included in candidates")
    rng = Random(seed)
    nominal_top = nominal_unique = calibrated_top = calibrated_unique = 0
    nominal_rank = calibrated_rank = 0.0
    nominal_gap = calibrated_gap = 0.0
    for _ in range(replicates):
        calibration_dataset = simulate_izu_detection_calibration_dataset(
            truth,
            template_settings,
            landscape,
            camera_design,
            seed_design,
            distortion,
            calibration_design,
            sites=sites,
            seed=rng.randrange(2**63),
        )
        nominal = score_izu_gradient_candidates(
            candidates,
            calibration_dataset.dataset,
            template_settings,
            landscape,
            camera_design,
            seed_design,
            analysis_mode,
        )
        calibrated = score_izu_gradient_candidates_with_detection_calibration(
            candidates,
            calibration_dataset,
            template_settings,
            landscape,
            camera_design,
            seed_design,
            calibration_design,
            analysis_mode,
        )
        n_top, n_unique, n_rank, n_gap = _rank_and_gap(nominal, truth)
        c_top, c_unique, c_rank, c_gap = _rank_and_gap(calibrated, truth)
        nominal_top += n_top
        nominal_unique += n_unique
        calibrated_top += c_top
        calibrated_unique += c_unique
        nominal_rank += n_rank
        calibrated_rank += c_rank
        nominal_gap += n_gap
        calibrated_gap += c_gap
    return IzuDetectionCalibrationRecoverySummary(
        truth=truth,
        analysis_mode=analysis_mode,
        replicates=replicates,
        reference_visits_per_site=calibration_design.reference_visits_per_site,
        nominal_truth_top_rank_rate=nominal_top / replicates,
        calibrated_truth_top_rank_rate=calibrated_top / replicates,
        nominal_unique_truth_top_rate=nominal_unique / replicates,
        calibrated_unique_truth_top_rate=calibrated_unique / replicates,
        nominal_mean_truth_rank=nominal_rank / replicates,
        calibrated_mean_truth_rank=calibrated_rank / replicates,
        nominal_mean_truth_log_likelihood_gap=nominal_gap / replicates,
        calibrated_mean_truth_log_likelihood_gap=calibrated_gap / replicates,
    )
