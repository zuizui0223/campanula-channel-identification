"""Joint observation model for outcrossed and selfed viable seed components.

Outcrossed viable seeds, selfed viable seeds, and all remaining ovules are
mutually exclusive outcomes of a shared ovule pool. They must therefore not be
simulated as independent Poisson counts in a finite-sample recovery benchmark.
This module provides a minimal multinomial seed-fate sampler and Wilson
intervals on the declared maternal-individual scale.

It is an operating-characteristic tool, not a final field likelihood. Real
analyses may require maternal random effects, overdispersion, pollen-limitation
treatments, paternity error, seed abortion classes, and repeated years. The
purpose here is narrower: prevent an internally impossible synthetic design
from treating outcross and selfed seed components as independent draws.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
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


@dataclass(frozen=True)
class SeedFateObservationDesign:
    """Declared sampling scale for a joint outcross/selfed seed-fate assay."""

    maternal_individuals: int
    potential_ovules_per_maternal: int
    familywise_confidence: float = 0.95

    def __post_init__(self) -> None:
        if self.maternal_individuals < 1:
            raise ValueError("maternal_individuals must be positive")
        if self.potential_ovules_per_maternal < 1:
            raise ValueError("potential_ovules_per_maternal must be positive")
        if not 0.0 < self.familywise_confidence < 1.0:
            raise ValueError("familywise_confidence must lie in (0, 1)")

    @property
    def total_ovules(self) -> int:
        return self.maternal_individuals * self.potential_ovules_per_maternal

    @property
    def marginal_confidence(self) -> float:
        """Bonferroni calibration for the two jointly reported seed components."""

        return 1.0 - (1.0 - self.familywise_confidence) / 2.0


@dataclass(frozen=True)
class SeedFateCounts:
    """Aggregated mutually exclusive outcomes across all sampled maternal plants."""

    outcross_viable: int
    selfed_viable: int
    other: int
    total_ovules: int

    def __post_init__(self) -> None:
        if min(
            self.outcross_viable,
            self.selfed_viable,
            self.other,
            self.total_ovules,
        ) < 0:
            raise ValueError("seed-fate counts must be non-negative")
        if self.outcross_viable + self.selfed_viable + self.other != self.total_ovules:
            raise ValueError("seed-fate counts must partition total_ovules")


@dataclass(frozen=True)
class JointSeedFateRecoverySummary:
    """Finite-sample recovery performance using coherent seed-fate observations."""

    truth: ScenarioSpec
    replicates: int
    truth_retained_rate: float
    unique_truth_recovery_rate: float
    empty_compatible_set_rate: float
    mean_compatible_scenarios: float


def seed_fate_probabilities(
    outcross_viable_seeds: float,
    selfed_viable_seeds: float,
    potential_ovules_per_maternal: int,
) -> tuple[float, float, float]:
    """Map model expectations to a three-category ovule fate distribution.

    The declared ovule scale is a model calibration input. It must be at least
    the expected total viable output of every candidate scenario to be compared.
    """

    if outcross_viable_seeds < 0.0 or selfed_viable_seeds < 0.0:
        raise ValueError("viable seed expectations must be non-negative")
    total_viable = outcross_viable_seeds + selfed_viable_seeds
    if total_viable > potential_ovules_per_maternal + 1e-12:
        raise ValueError(
            "outcross plus selfed viable seed expectation exceeds the declared "
            "potential ovule scale; calibrate potential_ovules_per_maternal"
        )
    outcross_probability = outcross_viable_seeds / potential_ovules_per_maternal
    selfed_probability = selfed_viable_seeds / potential_ovules_per_maternal
    return (
        outcross_probability,
        selfed_probability,
        1.0 - outcross_probability - selfed_probability,
    )


def sample_seed_fates(
    outcross_probability: float,
    selfed_probability: float,
    total_ovules: int,
    rng: Random,
) -> SeedFateCounts:
    """Draw mutually exclusive outcross, selfed, and other ovule outcomes."""

    if total_ovules < 1:
        raise ValueError("total_ovules must be positive")
    if outcross_probability < 0.0 or selfed_probability < 0.0:
        raise ValueError("seed-fate probabilities must be non-negative")
    if outcross_probability + selfed_probability > 1.0 + 1e-12:
        raise ValueError("outcross and selfed probabilities must sum to at most one")

    outcross = 0
    selfed = 0
    for _ in range(total_ovules):
        draw = rng.random()
        if draw < outcross_probability:
            outcross += 1
        elif draw < outcross_probability + selfed_probability:
            selfed += 1
    return SeedFateCounts(
        outcross_viable=outcross,
        selfed_viable=selfed,
        other=total_ovules - outcross - selfed,
        total_ovules=total_ovules,
    )


def wilson_interval(successes: int, trials: int, confidence: float) -> tuple[float, float]:
    """Return a Wilson interval for a binomial proportion without dependencies."""

    if trials < 1:
        raise ValueError("trials must be positive")
    if not 0 <= successes <= trials:
        raise ValueError("successes must lie between zero and trials")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must lie in (0, 1)")

    proportion = successes / trials
    z_value = NormalDist().inv_cdf((1.0 + confidence) / 2.0)
    denominator = 1.0 + z_value**2 / trials
    centre = (proportion + z_value**2 / (2.0 * trials)) / denominator
    half_width = z_value * sqrt(
        proportion * (1.0 - proportion) / trials + z_value**2 / (4.0 * trials**2)
    ) / denominator
    return max(0.0, centre - half_width), min(1.0, centre + half_width)


def joint_seed_fate_observations(
    truth: ScenarioSpec,
    settings: ScenarioSettings,
    year_label: str,
    design: SeedFateObservationDesign,
    rng: Random,
) -> tuple[ScenarioObservation, ScenarioObservation]:
    """Generate coherent component intervals from one virtual scenario truth."""

    result = simulate_guide_scenario(truth, settings)
    outcross_expected = result.metric(ScenarioMetric.OUTCROSS_VIABLE_SEEDS, year_label)
    selfed_expected = result.metric(ScenarioMetric.SELFED_VIABLE_SEEDS, year_label)
    outcross_probability, selfed_probability, _ = seed_fate_probabilities(
        outcross_expected,
        selfed_expected,
        design.potential_ovules_per_maternal,
    )
    counts = sample_seed_fates(
        outcross_probability,
        selfed_probability,
        design.total_ovules,
        rng,
    )
    outcross_lower, outcross_upper = wilson_interval(
        counts.outcross_viable,
        counts.total_ovules,
        design.marginal_confidence,
    )
    selfed_lower, selfed_upper = wilson_interval(
        counts.selfed_viable,
        counts.total_ovules,
        design.marginal_confidence,
    )
    scale = design.potential_ovules_per_maternal
    return (
        ScenarioObservation(
            ScenarioMetric.OUTCROSS_VIABLE_SEEDS,
            outcross_lower * scale,
            outcross_upper * scale,
            year_label,
        ),
        ScenarioObservation(
            ScenarioMetric.SELFED_VIABLE_SEEDS,
            selfed_lower * scale,
            selfed_upper * scale,
            year_label,
        ),
    )


def benchmark_joint_seed_fate_recovery(
    truth: ScenarioSpec,
    candidates: Sequence[ScenarioSpec],
    settings: ScenarioSettings,
    year_label: str,
    design: SeedFateObservationDesign,
    replicates: int,
    seed: int = 0,
) -> JointSeedFateRecoverySummary:
    """Estimate recovery under a coherent shared-ovule observation model."""

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
    for _ in range(replicates):
        observations = joint_seed_fate_observations(
            truth,
            settings,
            year_label,
            design,
            rng,
        )
        compatible = recover_compatible_scenarios(candidates, settings, observations)
        scenarios = tuple(report.scenario for report in compatible)
        compatible_total += len(scenarios)
        if truth in scenarios:
            truth_retained += 1
        if scenarios == (truth,):
            unique_truth += 1
        if not scenarios:
            empty += 1

    return JointSeedFateRecoverySummary(
        truth=truth,
        replicates=replicates,
        truth_retained_rate=truth_retained / replicates,
        unique_truth_recovery_rate=unique_truth / replicates,
        empty_compatible_set_rate=empty / replicates,
        mean_compatible_scenarios=compatible_total / replicates,
    )
