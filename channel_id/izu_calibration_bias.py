"""Stress-test finite camera calibration when its estimate is biased or mismatched.

The finite-detection calibration benchmark treats independently reviewed
reference visits as coming from the same effective detection process as the
primary footage. That is useful as an optimistic upper bound, but calibration
can fail before any likelihood is fitted:

* clips may be preferentially selected because they are bright, stable, or easy
  to score, making their apparent detection rate too high;
* a pooled or mismatched calibration stratum can differ from the primary
  site-condition even when individual clips were reviewed correctly;
* calibration mismatch can covary with the same north-to-south axis that carries
  the virtual floral-guide contrast, creating trait–detection confounding.

This module takes the finite beta-smoothed detection estimates from
:mod:`izu_detection_calibration`, perturbs them on the logit scale *only for the
analysis*, and then checks whether the true virtual route remains top-ranked.
The primary virtual dataset and its independent calibration counts are unchanged.

A positive global logit bias means the analyst's calibration estimate is too
optimistic about primary-video detection. A positive gradient slope means that
optimism increases towards the southern end of the declared ordinal archipelago
axis. The values are synthetic stress assumptions, not measurements of a
particular camera system.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, log
from random import Random
from typing import Mapping, Sequence

from .camera_visit_handling import CameraVisitHandlingDesign
from .guide_scenarios import ScenarioSettings, ScenarioSpec
from .izu_detection_calibration import (
    DetectionCalibrationDesign,
    IzuDetectionCalibrationDataset,
    _site_log_likelihood_with_detection,
    calibrated_detection_probabilities,
    simulate_izu_detection_calibration_dataset,
)
from .izu_field_misspecification import IzuFieldDistortion
from .izu_gradient_benchmark import (
    GradientAnalysisMode,
    IzuGradientLandscape,
    IzuGradientSite,
)
from .izu_pooled_evidence import (
    IzuScenarioEvidence,
    score_izu_gradient_candidates,
    top_scoring_scenarios,
)
from .seed_set_paternity import SeedSetPaternityDesign


@dataclass(frozen=True)
class DetectionCalibrationBias:
    """Analysis-side departure from an unbiased finite detection calibration.

    ``logit_bias`` shifts every calibration estimate after it is computed from
    reference visits. A positive value represents a calibration subset that
    makes detection appear better than it is in the primary footage.

    ``archipelago_logit_slope`` adds a deterministic condition mismatch along
    the declared ordinal north-to-south axis. It is centred at 0.5, so it changes
    relative calibration between ends of the virtual gradient rather than just
    applying a global rescaling.

    ``site_logit_sd`` adds mean-zero independent site-condition mismatch. This
    is a compact proxy for coarsening wind/light strata or using non-matching
    calibration clips; it is not a fitted random effect.
    """

    label: str
    logit_bias: float = 0.0
    archipelago_logit_slope: float = 0.0
    site_logit_sd: float = 0.0

    def __post_init__(self) -> None:
        if not self.label:
            raise ValueError("calibration-bias label must be non-empty")
        if self.site_logit_sd < 0.0:
            raise ValueError("site_logit_sd must be non-negative")


@dataclass(frozen=True)
class IzuCalibrationBiasRecoverySummary:
    """Nominal, unbiased, and biased-calibration recovery for one virtual case."""

    truth: ScenarioSpec
    bias: DetectionCalibrationBias
    analysis_mode: GradientAnalysisMode
    replicates: int
    reference_visits_per_site: int
    nominal_truth_top_rank_rate: float
    unbiased_truth_top_rank_rate: float
    biased_truth_top_rank_rate: float
    nominal_unique_truth_top_rate: float
    unbiased_unique_truth_top_rate: float
    biased_unique_truth_top_rate: float
    nominal_mean_truth_rank: float
    unbiased_mean_truth_rank: float
    biased_mean_truth_rank: float
    nominal_mean_truth_log_likelihood_gap: float
    unbiased_mean_truth_log_likelihood_gap: float
    biased_mean_truth_log_likelihood_gap: float


def default_detection_calibration_biases() -> tuple[DetectionCalibrationBias, ...]:
    """Return distinct synthetic calibration-failure modes for the report."""

    return (
        DetectionCalibrationBias("unbiased"),
        DetectionCalibrationBias("easy_clip_bias", logit_bias=0.80),
        DetectionCalibrationBias(
            "south_optimistic_gradient",
            archipelago_logit_slope=2.00,
        ),
        DetectionCalibrationBias(
            "south_pessimistic_gradient",
            archipelago_logit_slope=-2.00,
        ),
        DetectionCalibrationBias(
            "easy_clip_plus_gradient_mismatch",
            logit_bias=0.80,
            archipelago_logit_slope=2.00,
            site_logit_sd=0.70,
        ),
    )


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


def perturb_calibrated_detection_probabilities(
    detection_probabilities: Mapping[str, float],
    bias: DetectionCalibrationBias,
    rng: Random,
    site_positions: Mapping[str, float] | None = None,
) -> dict[str, float]:
    """Apply an analysis-side calibration bias without altering raw observations."""

    if bias.archipelago_logit_slope != 0.0:
        if site_positions is None:
            raise ValueError("site_positions are required for a gradient calibration bias")
        if set(site_positions) != set(detection_probabilities):
            raise ValueError("site_positions must match detection-probability site IDs")
    perturbed: dict[str, float] = {}
    for site_id, probability in detection_probabilities.items():
        if not 0.0 < probability < 1.0:
            raise ValueError("calibrated detection probabilities must lie in (0, 1)")
        offset = bias.logit_bias
        if bias.archipelago_logit_slope != 0.0:
            position = site_positions[site_id]
            if not 0.0 <= position <= 1.0:
                raise ValueError("site positions must lie in [0, 1]")
            offset += bias.archipelago_logit_slope * (position - 0.5)
        if bias.site_logit_sd > 0.0:
            offset += rng.normalvariate(0.0, bias.site_logit_sd)
        perturbed[site_id] = _inverse_logit(_logit(probability) + offset)
    return perturbed


def score_izu_gradient_candidates_with_detection_probabilities(
    candidates: Sequence[ScenarioSpec],
    calibration_dataset: IzuDetectionCalibrationDataset,
    template_settings: ScenarioSettings,
    landscape: IzuGradientLandscape,
    camera_design: CameraVisitHandlingDesign,
    seed_design: SeedSetPaternityDesign,
    detection_probabilities: Mapping[str, float],
    analysis_mode: GradientAnalysisMode = GradientAnalysisMode.CALIBRATED,
) -> tuple[IzuScenarioEvidence, ...]:
    """Score candidates with externally supplied effective detection probabilities."""

    dataset = calibration_dataset.dataset
    if not candidates:
        raise ValueError("at least one candidate is required")
    if len(set(candidates)) != len(candidates):
        raise ValueError("candidate scenarios must be unique")
    expected_sites = {observed.site.label for observed in dataset.sites}
    if set(detection_probabilities) != expected_sites:
        missing = sorted(expected_sites - set(detection_probabilities))
        extra = sorted(set(detection_probabilities) - expected_sites)
        raise ValueError(f"detection probabilities must match dataset sites; missing={missing}, extra={extra}")
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
                detection_probabilities[dataset.sites[index].site.label],
            )
            for index in range(len(dataset.sites))
        )
        scored.append(IzuScenarioEvidence(candidate, analysis_mode, sites))
    return tuple(sorted(scored, key=lambda item: item.total_log_likelihood, reverse=True))


def score_izu_gradient_candidates_with_calibration_bias(
    candidates: Sequence[ScenarioSpec],
    calibration_dataset: IzuDetectionCalibrationDataset,
    template_settings: ScenarioSettings,
    landscape: IzuGradientLandscape,
    camera_design: CameraVisitHandlingDesign,
    seed_design: SeedSetPaternityDesign,
    calibration_design: DetectionCalibrationDesign,
    bias: DetectionCalibrationBias,
    seed: int = 0,
    analysis_mode: GradientAnalysisMode = GradientAnalysisMode.CALIBRATED,
) -> tuple[IzuScenarioEvidence, ...]:
    """Score candidates after finite calibration is distorted by a declared bias."""

    dataset = calibration_dataset.dataset
    unbiased = calibrated_detection_probabilities(
        calibration_dataset.calibration,
        calibration_design,
        tuple(observed.site for observed in dataset.sites),
    )
    positions = {
        observed.site.label: observed.site.archipelago_position
        for observed in dataset.sites
    }
    detection = perturb_calibrated_detection_probabilities(
        unbiased,
        bias,
        Random(seed),
        positions,
    )
    return score_izu_gradient_candidates_with_detection_probabilities(
        candidates,
        calibration_dataset,
        template_settings,
        landscape,
        camera_design,
        seed_design,
        detection,
        analysis_mode,
    )


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


def benchmark_izu_calibration_bias_recovery(
    truth: ScenarioSpec,
    candidates: Sequence[ScenarioSpec],
    template_settings: ScenarioSettings,
    landscape: IzuGradientLandscape,
    camera_design: CameraVisitHandlingDesign,
    seed_design: SeedSetPaternityDesign,
    distortion: IzuFieldDistortion,
    calibration_design: DetectionCalibrationDesign,
    bias: DetectionCalibrationBias,
    sites: Sequence[IzuGradientSite] | None = None,
    analysis_mode: GradientAnalysisMode = GradientAnalysisMode.CALIBRATED,
    replicates: int = 100,
    seed: int = 0,
) -> IzuCalibrationBiasRecoverySummary:
    """Compare nominal, unbiased, and biased finite calibration across replicates."""

    if replicates < 1:
        raise ValueError("replicates must be positive")
    if truth not in candidates:
        raise ValueError("truth must be included in candidates")
    rng = Random(seed)
    totals = [0.0] * 12
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
        unbiased = score_izu_gradient_candidates_with_calibration_bias(
            candidates,
            calibration_dataset,
            template_settings,
            landscape,
            camera_design,
            seed_design,
            calibration_design,
            DetectionCalibrationBias("unbiased"),
            seed=rng.randrange(2**63),
            analysis_mode=analysis_mode,
        )
        biased = score_izu_gradient_candidates_with_calibration_bias(
            candidates,
            calibration_dataset,
            template_settings,
            landscape,
            camera_design,
            seed_design,
            calibration_design,
            bias,
            seed=rng.randrange(2**63),
            analysis_mode=analysis_mode,
        )
        for index, value in enumerate(_rank_and_gap(nominal, truth)):
            totals[index] += value
        for index, value in enumerate(_rank_and_gap(unbiased, truth), start=4):
            totals[index] += value
        for index, value in enumerate(_rank_and_gap(biased, truth), start=8):
            totals[index] += value
    values = [item / replicates for item in totals]
    return IzuCalibrationBiasRecoverySummary(
        truth=truth,
        bias=bias,
        analysis_mode=analysis_mode,
        replicates=replicates,
        reference_visits_per_site=calibration_design.reference_visits_per_site,
        nominal_truth_top_rank_rate=values[0],
        nominal_unique_truth_top_rate=values[1],
        nominal_mean_truth_rank=values[2],
        nominal_mean_truth_log_likelihood_gap=values[3],
        unbiased_truth_top_rank_rate=values[4],
        unbiased_unique_truth_top_rate=values[5],
        unbiased_mean_truth_rank=values[6],
        unbiased_mean_truth_log_likelihood_gap=values[7],
        biased_truth_top_rank_rate=values[8],
        biased_unique_truth_top_rate=values[9],
        biased_mean_truth_rank=values[10],
        biased_mean_truth_log_likelihood_gap=values[11],
    )
