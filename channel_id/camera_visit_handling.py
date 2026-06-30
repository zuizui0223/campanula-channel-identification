"""Camera observation model for visits and legitimate floral handling.

A camera record does not directly equal either visit rate or legitimate-contact
rate. The two quantities have distinct observation processes:

* visits occur in a declared flower-by-camera-window exposure;
* a visit is detected with a calibrated probability;
* a detected visit is annotated as legitimate or non-legitimate with calibrated
  sensitivity and specificity.

This module generates virtual camera datasets on that hierarchy and converts
them into scenario-compatible intervals for ``EXPECTED_VISITS`` and
``LEGITIMATE_CONTACT_FRACTION``. It is an operating-characteristic tool, not
a final video-analysis likelihood. Site/plant random effects, time-varying
detection, individual pollinator identity, and correlated annotation error
remain explicit future extensions.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import log, sqrt
from random import Random
from statistics import NormalDist
from typing import Sequence

from .guide_scenarios import (
    ScenarioMetric,
    ScenarioObservation,
    ScenarioSettings,
    ScenarioSpec,
    recover_compatible_scenarios,
    simulate_guide_scenario,
)
from .joint_seed_fates import wilson_interval


@dataclass(frozen=True)
class CameraVisitHandlingDesign:
    """Declared camera exposure and annotation calibration.

    ``exposure_multiplier_per_window`` maps one flower-by-camera-window unit to
    the maternal-flower visit scale used by ``ScenarioMetric.EXPECTED_VISITS``.
    It must be estimated or justified from a pilot observation protocol; it is
    not automatically equal to camera minutes or hours.
    """

    flower_camera_windows: int
    exposure_multiplier_per_window: float
    visit_detection_probability: float
    legitimate_annotation_sensitivity: float
    legitimate_annotation_specificity: float
    familywise_confidence: float = 0.95

    def __post_init__(self) -> None:
        if self.flower_camera_windows < 1:
            raise ValueError("flower_camera_windows must be positive")
        if self.exposure_multiplier_per_window <= 0.0:
            raise ValueError("exposure_multiplier_per_window must be positive")
        for name, value in (
            ("visit_detection_probability", self.visit_detection_probability),
            ("legitimate_annotation_sensitivity", self.legitimate_annotation_sensitivity),
            ("legitimate_annotation_specificity", self.legitimate_annotation_specificity),
        ):
            if not 0.0 < value <= 1.0:
                raise ValueError(f"{name} must lie in (0, 1]")
        if self.legitimate_annotation_sensitivity + self.legitimate_annotation_specificity <= 1.0:
            raise ValueError(
                "legitimate annotation must be better than random classification "
                "(sensitivity + specificity > 1)"
            )
        if not 0.0 < self.familywise_confidence < 1.0:
            raise ValueError("familywise_confidence must lie in (0, 1)")

    @property
    def total_exposure(self) -> float:
        return self.flower_camera_windows * self.exposure_multiplier_per_window

    @property
    def marginal_confidence(self) -> float:
        """Bonferroni level for visit-rate and handling-fraction intervals."""

        return 1.0 - (1.0 - self.familywise_confidence) / 2.0


@dataclass(frozen=True)
class CameraVisitHandlingCounts:
    """Latent visits and observed camera/annotation counts in one virtual survey."""

    true_visits: int
    true_legitimate_contacts: int
    detected_visits: int
    called_legitimate: int
    called_nonlegitimate: int

    def __post_init__(self) -> None:
        if min(
            self.true_visits,
            self.true_legitimate_contacts,
            self.detected_visits,
            self.called_legitimate,
            self.called_nonlegitimate,
        ) < 0:
            raise ValueError("camera counts must be non-negative")
        if self.true_legitimate_contacts > self.true_visits:
            raise ValueError("true legitimate contacts cannot exceed true visits")
        if self.detected_visits > self.true_visits:
            raise ValueError("detected visits cannot exceed true visits")
        if self.called_legitimate + self.called_nonlegitimate != self.detected_visits:
            raise ValueError("annotation calls must partition detected visits")


@dataclass(frozen=True)
class CameraVisitHandlingObservation:
    """One virtual camera dataset and its two scenario-compatible intervals."""

    counts: CameraVisitHandlingCounts
    observations: tuple[ScenarioObservation, ScenarioObservation]


@dataclass(frozen=True)
class CameraVisitHandlingRecoverySummary:
    """Recovery properties of a declared camera visit/handling design."""

    truth: ScenarioSpec
    replicates: int
    truth_retained_rate: float
    unique_truth_recovery_rate: float
    empty_compatible_set_rate: float
    mean_compatible_scenarios: float
    mean_detected_visits: float


def _poisson_count(mean: float, rng: Random) -> int:
    """Draw a Poisson count by exponential inter-arrivals using stdlib only."""

    if mean < 0.0:
        raise ValueError("Poisson mean must be non-negative")
    if mean == 0.0:
        return 0
    elapsed = 0.0
    count = 0
    while True:
        draw = rng.random()
        while draw == 0.0:
            draw = rng.random()
        elapsed -= log(draw)
        if elapsed > mean:
            return count
        count += 1


def poisson_mean_interval(count: int, confidence: float) -> tuple[float, float]:
    """Approximate two-sided interval for a Poisson mean using an Anscombe transform.

    This is a count-model approximation, not a normal interval applied to raw
    visit counts. For final empirical inference, replace it with a hierarchical
    count likelihood when camera windows, plants, or sites are clustered.
    """

    if count < 0:
        raise ValueError("count must be non-negative")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must lie in (0, 1)")
    z_value = NormalDist().inv_cdf((1.0 + confidence) / 2.0)
    transformed = sqrt(count + 3.0 / 8.0)
    lower = max(0.0, (max(0.0, transformed - z_value / 2.0) ** 2) - 3.0 / 8.0)
    upper = (transformed + z_value / 2.0) ** 2 - 3.0 / 8.0
    return lower, upper


def corrected_legitimate_fraction_interval(
    called_legitimate: int,
    detected_visits: int,
    design: CameraVisitHandlingDesign,
) -> tuple[float, float]:
    """Return a call-error-corrected interval for legitimate contacts per visit."""

    if detected_visits < 0 or not 0 <= called_legitimate <= detected_visits:
        raise ValueError("called_legitimate must lie between zero and detected_visits")
    if detected_visits == 0:
        return 0.0, 1.0
    called_lower, called_upper = wilson_interval(
        called_legitimate,
        detected_visits,
        design.marginal_confidence,
    )
    false_positive = 1.0 - design.legitimate_annotation_specificity
    information = (
        design.legitimate_annotation_sensitivity
        + design.legitimate_annotation_specificity
        - 1.0
    )
    lower = (called_lower - false_positive) / information
    upper = (called_upper - false_positive) / information
    return max(0.0, lower), min(1.0, upper)


def _camera_observations(
    counts: CameraVisitHandlingCounts,
    design: CameraVisitHandlingDesign,
    year_label: str,
) -> tuple[ScenarioObservation, ScenarioObservation]:
    """Map camera counts to corrected scenario-scale intervals."""

    detected_lower, detected_upper = poisson_mean_interval(
        counts.detected_visits,
        design.marginal_confidence,
    )
    denominator = design.total_exposure * design.visit_detection_probability
    visit_lower = detected_lower / denominator
    visit_upper = detected_upper / denominator
    handling_lower, handling_upper = corrected_legitimate_fraction_interval(
        counts.called_legitimate,
        counts.detected_visits,
        design,
    )
    return (
        ScenarioObservation(
            ScenarioMetric.EXPECTED_VISITS,
            visit_lower,
            visit_upper,
            year_label,
        ),
        ScenarioObservation(
            ScenarioMetric.LEGITIMATE_CONTACT_FRACTION,
            handling_lower,
            handling_upper,
            year_label,
        ),
    )


def simulate_camera_visit_handling_observation(
    truth: ScenarioSpec,
    settings: ScenarioSettings,
    year_label: str,
    design: CameraVisitHandlingDesign,
    rng: Random,
) -> CameraVisitHandlingObservation:
    """Generate a virtual camera dataset for a declared scenario truth."""

    result = simulate_guide_scenario(truth, settings)
    visit_rate = result.metric(ScenarioMetric.EXPECTED_VISITS, year_label)
    legitimate_fraction = result.metric(ScenarioMetric.LEGITIMATE_CONTACT_FRACTION, year_label)
    true_visits = _poisson_count(visit_rate * design.total_exposure, rng)

    true_legitimate = 0
    detected = 0
    called_legitimate = 0
    called_nonlegitimate = 0
    for _ in range(true_visits):
        legitimate = rng.random() < legitimate_fraction
        if legitimate:
            true_legitimate += 1
        if rng.random() >= design.visit_detection_probability:
            continue
        detected += 1
        if legitimate:
            called_as_legitimate = rng.random() < design.legitimate_annotation_sensitivity
        else:
            called_as_legitimate = rng.random() >= design.legitimate_annotation_specificity
        if called_as_legitimate:
            called_legitimate += 1
        else:
            called_nonlegitimate += 1

    counts = CameraVisitHandlingCounts(
        true_visits=true_visits,
        true_legitimate_contacts=true_legitimate,
        detected_visits=detected,
        called_legitimate=called_legitimate,
        called_nonlegitimate=called_nonlegitimate,
    )
    return CameraVisitHandlingObservation(
        counts=counts,
        observations=_camera_observations(counts, design, year_label),
    )


def benchmark_camera_visit_handling_recovery(
    truth: ScenarioSpec,
    candidates: Sequence[ScenarioSpec],
    settings: ScenarioSettings,
    year_label: str,
    design: CameraVisitHandlingDesign,
    replicates: int,
    seed: int = 0,
) -> CameraVisitHandlingRecoverySummary:
    """Estimate scenario recovery for a declared camera observation protocol."""

    if replicates < 1:
        raise ValueError("replicates must be positive")
    if truth not in candidates:
        raise ValueError("truth must be included in candidates")
    if year_label not in {year.label for year in settings.years}:
        raise ValueError(f"unknown year label {year_label!r}")

    rng = Random(seed)
    truth_retained = 0
    unique_truth = 0
    empty = 0
    compatible_total = 0
    detected_total = 0
    for _ in range(replicates):
        virtual_observation = simulate_camera_visit_handling_observation(
            truth,
            settings,
            year_label,
            design,
            rng,
        )
        compatible = recover_compatible_scenarios(
            candidates,
            settings,
            virtual_observation.observations,
        )
        scenarios = tuple(report.scenario for report in compatible)
        compatible_total += len(scenarios)
        detected_total += virtual_observation.counts.detected_visits
        if truth in scenarios:
            truth_retained += 1
        if scenarios == (truth,):
            unique_truth += 1
        if not scenarios:
            empty += 1

    return CameraVisitHandlingRecoverySummary(
        truth=truth,
        replicates=replicates,
        truth_retained_rate=truth_retained / replicates,
        unique_truth_recovery_rate=unique_truth / replicates,
        empty_compatible_set_rate=empty / replicates,
        mean_compatible_scenarios=compatible_total / replicates,
        mean_detected_visits=detected_total / replicates,
    )
