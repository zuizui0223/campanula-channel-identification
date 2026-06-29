"""Finite-sample scenario-recovery checks for pre-data design work.

The deterministic scenario-recovery tests confirm algebraic consistency.  This
module asks the harder pre-data question: after individual-level count noise and
simultaneous observation intervals are introduced, how often does the declared
candidate set retain the virtual truth, recover it uniquely, or become empty?

The sampler is intentionally lightweight and dependency-free.  It draws
independent Poisson per-maternal counts around each declared expected metric.
That is not a final field likelihood: visit counts, seed components, and
recruitment can be correlated and overdispersed in real populations.  Its role
is to make operating-characteristic checks mandatory before data collection and
to provide a transparent baseline that richer observation models can replace.
"""

from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import Sequence

from .guide_scenarios import (
    GuideScenario,
    ScenarioMetric,
    ScenarioObservation,
    ScenarioSettings,
    ScenarioSpec,
    recover_compatible_scenarios,
    simulate_guide_scenario,
)
from .observation import (
    SimultaneousIntervalPlan,
    normal_mean_interval,
    poisson_sample,
)


@dataclass(frozen=True)
class FiniteSampleRecoveryDesign:
    """Declared synthetic observation design for one scenario-recovery exercise."""

    maternal_individuals: int
    metrics: tuple[ScenarioMetric, ...]
    familywise_confidence: float = 0.95

    def __post_init__(self) -> None:
        if self.maternal_individuals < 2:
            raise ValueError("at least two maternal individuals are required")
        if not self.metrics:
            raise ValueError("at least one metric is required")
        if ScenarioMetric.GEOMETRIC_MEAN_CONTRIBUTION in self.metrics:
            raise ValueError("geometric_mean_contribution is not an individual-level observation")
        if len(set(self.metrics)) != len(self.metrics):
            raise ValueError("metrics must be unique")
        if not 0.0 < self.familywise_confidence < 1.0:
            raise ValueError("familywise_confidence must lie in (0, 1)")


@dataclass(frozen=True)
class ScenarioRecoverySummary:
    """Operating characteristics over a declared number of virtual repetitions."""

    truth: ScenarioSpec
    replicates: int
    truth_retained_rate: float
    unique_truth_recovery_rate: float
    empty_compatible_set_rate: float
    mean_compatible_scenarios: float


def finite_sample_observations(
    truth: ScenarioSpec,
    settings: ScenarioSettings,
    year_label: str,
    design: FiniteSampleRecoveryDesign,
    rng: Random,
) -> tuple[ScenarioObservation, ...]:
    """Generate interval observations from one declared virtual truth.

    Each selected metric is sampled per maternal individual, converted to a mean
    interval, and calibrated jointly with a declared Bonferroni plan.  Lower
    limits are clipped at zero because the compatibility model only accepts
    non-negative biological quantities.
    """

    result = simulate_guide_scenario(truth, settings)
    plan = SimultaneousIntervalPlan(
        design.familywise_confidence,
        len(design.metrics),
    )
    observations: list[ScenarioObservation] = []
    for metric in design.metrics:
        expected_per_maternal = result.metric(metric, year_label)
        values = [
            float(poisson_sample(expected_per_maternal, rng))
            for _ in range(design.maternal_individuals)
        ]
        interval = normal_mean_interval(values, plan.marginal_confidence)
        observations.append(
            ScenarioObservation(
                metric=metric,
                lower=max(0.0, interval.lower),
                upper=interval.upper,
                year_label=year_label,
            )
        )
    return tuple(observations)


def benchmark_scenario_recovery(
    truth: ScenarioSpec,
    candidates: Sequence[ScenarioSpec],
    settings: ScenarioSettings,
    year_label: str,
    design: FiniteSampleRecoveryDesign,
    replicates: int,
    seed: int = 0,
) -> ScenarioRecoverySummary:
    """Estimate recovery performance for a finite-sample virtual field design."""

    if replicates <= 0:
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
    for _ in range(replicates):
        observations = finite_sample_observations(truth, settings, year_label, design, rng)
        compatible = recover_compatible_scenarios(candidates, settings, observations)
        compatible_total += len(compatible)
        scenarios = tuple(report.scenario for report in compatible)
        if truth in scenarios:
            truth_retained += 1
        if scenarios == (truth,):
            unique_truth += 1
        if not scenarios:
            empty += 1

    return ScenarioRecoverySummary(
        truth=truth,
        replicates=replicates,
        truth_retained_rate=truth_retained / replicates,
        unique_truth_recovery_rate=unique_truth / replicates,
        empty_compatible_set_rate=empty / replicates,
        mean_compatible_scenarios=compatible_total / replicates,
    )
