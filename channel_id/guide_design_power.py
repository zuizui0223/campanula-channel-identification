"""Simulation-based design power for competing nectar-guide scenarios.

This module asks a pre-data question: for a declared measurement plan, its
effective sample size, and a declared individual-level measurement variation,
how often will the planned observations retain the virtual truth and eliminate
competing scenario classes?

It is not a posterior model-selection engine. Its results are conditional on
the scenario restrictions, the observation-error model, and the chosen
interval multiplier.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import sqrt
from random import Random
from typing import Sequence

from .guide_scenarios import (
    GuideScenario,
    ScenarioMetric,
    ScenarioObservation,
    ScenarioResult,
    ScenarioSettings,
    simulate_guide_scenario,
)


@dataclass(frozen=True)
class MeasurementDesign:
    """Sampling model for one planned observable.

    ``individual_standard_deviation`` is the total SD across independent
    sampling units on the observable's scale. It must include biological
    heterogeneity and measurement error. ``sample_size`` is the *effective*
    number of independent units, not automatically the number of videos,
    flowers, or pollen grains collected.

    A virtual observed mean is drawn from a normal approximation with
    ``SE = SD / sqrt(n)``. The compatibility interval is then the observed
    mean plus/minus ``interval_multiplier * SE``, clipped at zero because all
    currently supported scenario metrics are non-negative.
    """

    metric: ScenarioMetric
    sample_size: int
    individual_standard_deviation: float
    year_label: str | None = None
    interval_multiplier: float = 1.96
    label: str | None = None

    def __post_init__(self) -> None:
        if self.sample_size < 1:
            raise ValueError("sample_size must be at least one")
        if self.individual_standard_deviation < 0.0:
            raise ValueError("individual_standard_deviation must be non-negative")
        if self.interval_multiplier < 0.0:
            raise ValueError("interval_multiplier must be non-negative")
        if self.metric is ScenarioMetric.GEOMETRIC_MEAN_CONTRIBUTION:
            if self.year_label is not None:
                raise ValueError("geometric mean is a summary metric and cannot take year_label")
        elif not self.year_label:
            raise ValueError("year_label is required for year-level metrics")

    @property
    def standard_error(self) -> float:
        return self.individual_standard_deviation / sqrt(self.sample_size)

    @property
    def display_name(self) -> str:
        if self.label:
            return self.label
        suffix = "summary" if self.year_label is None else self.year_label
        return f"{self.metric.value}:{suffix}:n={self.sample_size}"

    def simulate_observation(self, truth: ScenarioResult, rng: Random) -> ScenarioObservation:
        """Generate one predeclared interval observation from virtual truth."""

        expected = truth.metric(self.metric, self.year_label)
        standard_error = self.standard_error
        observed_mean = max(0.0, rng.gauss(expected, standard_error))
        half_width = self.interval_multiplier * standard_error
        return ScenarioObservation(
            metric=self.metric,
            lower=max(0.0, observed_mean - half_width),
            upper=observed_mean + half_width,
            year_label=self.year_label,
        )


@dataclass(frozen=True)
class MeasurementPlan:
    """One candidate field measurement plan evaluated as a whole."""

    name: str
    measurements: tuple[MeasurementDesign, ...]

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("plan name must be non-empty")
        if not self.measurements:
            raise ValueError("a measurement plan must contain at least one measurement")
        identities = [(m.metric, m.year_label) for m in self.measurements]
        if len(set(identities)) != len(identities):
            raise ValueError("a plan cannot repeat the same metric/year combination")


@dataclass(frozen=True)
class ScenarioSurvivalRate:
    """Fraction of virtual datasets for which a scenario remains compatible."""

    scenario: GuideScenario
    survival_rate: float


@dataclass(frozen=True)
class DesignPowerResult:
    """Recovery properties of one virtual measurement plan."""

    plan_name: str
    truth_scenario: GuideScenario
    replicates: int
    truth_retention_rate: float
    unique_truth_recovery_rate: float
    unique_truth_given_retained_rate: float
    no_compatible_scenario_rate: float
    mean_compatible_scenarios: float
    mean_false_survivors: float
    scenario_survival_rates: tuple[ScenarioSurvivalRate, ...]


@dataclass(frozen=True)
class MeasurementPlanRanking:
    """One plan, its simulated recovery result, and its rank among plans."""

    rank: int
    result: DesignPowerResult


def _validate_scenarios(
    truth_scenario: GuideScenario,
    candidate_scenarios: Sequence[GuideScenario],
) -> tuple[GuideScenario, ...]:
    candidates = tuple(candidate_scenarios)
    if not candidates:
        raise ValueError("at least one candidate scenario is required")
    if len(set(candidates)) != len(candidates):
        raise ValueError("candidate scenarios must be unique")
    if truth_scenario not in candidates:
        raise ValueError("truth_scenario must be included among candidate_scenarios")
    return candidates


def _is_compatible(result: ScenarioResult, observations: Sequence[ScenarioObservation]) -> bool:
    return all(
        observation.contains(result.metric(observation.metric, observation.year_label))
        for observation in observations
    )


def evaluate_measurement_plan(
    truth_scenario: GuideScenario,
    candidate_scenarios: Sequence[GuideScenario],
    settings: ScenarioSettings,
    plan: MeasurementPlan,
    *,
    replicates: int = 1_000,
    random_seed: int = 0,
) -> DesignPowerResult:
    """Simulate recovery power for one plan under one declared virtual truth.

    ``unique_truth_recovery_rate`` is deliberately strict: it counts only
    replicates in which the true class is the sole compatible class. Report
    ``truth_retention_rate`` alongside it, because a plan can eliminate false
    classes by also excluding its own truth too often.
    """

    if replicates < 1:
        raise ValueError("replicates must be at least one")
    candidates = _validate_scenarios(truth_scenario, candidate_scenarios)
    scenario_results = {
        scenario: simulate_guide_scenario(scenario, settings)
        for scenario in candidates
    }
    truth = scenario_results[truth_scenario]
    rng = Random(random_seed)
    retained_truth = 0
    unique_truth = 0
    no_compatible = 0
    compatible_counts = 0
    false_survivors = 0
    survivor_counts = {scenario: 0 for scenario in candidates}

    for _ in range(replicates):
        observations = tuple(
            measurement.simulate_observation(truth, rng)
            for measurement in plan.measurements
        )
        compatible = tuple(
            scenario
            for scenario, result in scenario_results.items()
            if _is_compatible(result, observations)
        )
        compatible_counts += len(compatible)
        if not compatible:
            no_compatible += 1
        if truth_scenario in compatible:
            retained_truth += 1
        if compatible == (truth_scenario,):
            unique_truth += 1
        false_survivors += sum(scenario is not truth_scenario for scenario in compatible)
        for scenario in compatible:
            survivor_counts[scenario] += 1

    truth_retention = retained_truth / replicates
    return DesignPowerResult(
        plan_name=plan.name,
        truth_scenario=truth_scenario,
        replicates=replicates,
        truth_retention_rate=truth_retention,
        unique_truth_recovery_rate=unique_truth / replicates,
        unique_truth_given_retained_rate=(unique_truth / retained_truth if retained_truth else 0.0),
        no_compatible_scenario_rate=no_compatible / replicates,
        mean_compatible_scenarios=compatible_counts / replicates,
        mean_false_survivors=false_survivors / replicates,
        scenario_survival_rates=tuple(
            ScenarioSurvivalRate(scenario, survivor_counts[scenario] / replicates)
            for scenario in candidates
        ),
    )


def rank_measurement_plans(
    truth_scenario: GuideScenario,
    candidate_scenarios: Sequence[GuideScenario],
    settings: ScenarioSettings,
    plans: Sequence[MeasurementPlan],
    *,
    replicates: int = 1_000,
    random_seed: int = 0,
) -> tuple[MeasurementPlanRanking, ...]:
    """Rank plans by strict recovery, then truth retention and parsimony.

    The ranking is relative to this virtual truth, candidate set, error model,
    and sample-size declaration. It is a design comparison, not a universal
    field-priority ranking.
    """

    if not plans:
        raise ValueError("at least one measurement plan is required")
    if len({plan.name for plan in plans}) != len(plans):
        raise ValueError("measurement plan names must be unique")
    results = tuple(
        evaluate_measurement_plan(
            truth_scenario,
            candidate_scenarios,
            settings,
            plan,
            replicates=replicates,
            random_seed=random_seed + index,
        )
        for index, plan in enumerate(plans)
    )
    ranked = sorted(
        results,
        key=lambda result: (
            -result.unique_truth_recovery_rate,
            -result.truth_retention_rate,
            result.mean_compatible_scenarios,
            result.mean_false_survivors,
            result.plan_name,
        ),
    )
    return tuple(
        MeasurementPlanRanking(rank=index, result=result)
        for index, result in enumerate(ranked, start=1)
    )


def sweep_common_sample_sizes(
    base_plan: MeasurementPlan,
    sample_sizes: Sequence[int],
) -> tuple[MeasurementPlan, ...]:
    """Create plans that apply one effective sample size to every measurement.

    This is convenient for early field planning. Use manually constructed
    plans when visits, pollen deposition, and seed-set components will have
    different effective sample sizes.
    """

    if not sample_sizes:
        raise ValueError("at least one sample size is required")
    if any(sample_size < 1 for sample_size in sample_sizes):
        raise ValueError("sample sizes must be at least one")
    if len(set(sample_sizes)) != len(sample_sizes):
        raise ValueError("sample sizes must be unique")
    return tuple(
        MeasurementPlan(
            name=f"{base_plan.name}; n={sample_size}",
            measurements=tuple(
                replace(measurement, sample_size=sample_size)
                for measurement in base_plan.measurements
            ),
        )
        for sample_size in sample_sizes
    )
