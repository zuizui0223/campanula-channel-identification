"""Observation model for seed set plus partial paternity assignment.

A field campaign rarely knows the cross type of every viable seed.  More often
it counts mature seeds for a set of fruits, genotypes a fixed or capped subset
of those mature seeds, and obtains selfed, outcrossed, or unresolved calls.

This module turns that actual sampling hierarchy into virtual observations for
scenario-recovery design.  It builds on the shared-ovule model in
:mod:`joint_seed_fates`, while keeping three assumptions explicit:

* one scenario maternal unit maps to one sampled fruit (or an explicitly
  rescaled equivalent);
* unresolved paternity calls occur independently of cross type;
* the supplied directional paternity-error rates are known from calibration.

It is a planning model, not a final parentage likelihood.  It does not yet
model maternal random effects, paternal candidate coverage, correlated genotype
failure, seed-abortion stages, or year/site variation.
"""

from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import Sequence

from .guide_scenarios import (
    ScenarioMetric,
    ScenarioObservation,
    ScenarioSettings,
    ScenarioSpec,
    recover_compatible_scenarios,
    simulate_guide_scenario,
)
from .joint_seed_fates import (
    SeedFateCounts,
    sample_seed_fates,
    seed_fate_probabilities,
    wilson_interval,
)


@dataclass(frozen=True)
class SeedSetPaternityDesign:
    """Declared fruit sampling and paternity-assignment design.

    ``potential_ovules_per_fruit`` must use the same per-fruit scale as the
    maternal scenario output.  For a pooled infructescence or a different unit,
    rescale the scenario before using this design rather than silently treating
    several flowers as one independent fruit.
    """

    maternal_individuals: int
    fruits_per_maternal: int
    potential_ovules_per_fruit: int
    genotyped_mature_seeds_per_fruit: int
    unresolved_probability: float = 0.0
    outcross_to_self_error: float = 0.0
    self_to_outcross_error: float = 0.0
    familywise_confidence: float = 0.95

    def __post_init__(self) -> None:
        if self.maternal_individuals < 1:
            raise ValueError("maternal_individuals must be positive")
        if self.fruits_per_maternal < 1:
            raise ValueError("fruits_per_maternal must be positive")
        if self.potential_ovules_per_fruit < 1:
            raise ValueError("potential_ovules_per_fruit must be positive")
        if self.genotyped_mature_seeds_per_fruit < 0:
            raise ValueError("genotyped_mature_seeds_per_fruit must be non-negative")
        for name, value in (
            ("unresolved_probability", self.unresolved_probability),
            ("outcross_to_self_error", self.outcross_to_self_error),
            ("self_to_outcross_error", self.self_to_outcross_error),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must lie in [0, 1]")
        if self.outcross_to_self_error + self.self_to_outcross_error >= 1.0:
            raise ValueError("directional paternity-error rates must sum to less than one")
        if not 0.0 < self.familywise_confidence < 1.0:
            raise ValueError("familywise_confidence must lie in (0, 1)")

    @property
    def fruit_count(self) -> int:
        return self.maternal_individuals * self.fruits_per_maternal

    @property
    def total_ovules(self) -> int:
        return self.fruit_count * self.potential_ovules_per_fruit

    @property
    def marginal_confidence(self) -> float:
        """Bonferroni level for mature seed set and paternity composition."""

        return 1.0 - (1.0 - self.familywise_confidence) / 2.0


@dataclass(frozen=True)
class PaternityCalls:
    """Observed paternity calls for the genotyped mature-seed subsample."""

    outcross_calls: int
    self_calls: int
    unresolved_calls: int
    sampled_mature_seeds: int

    def __post_init__(self) -> None:
        if min(
            self.outcross_calls,
            self.self_calls,
            self.unresolved_calls,
            self.sampled_mature_seeds,
        ) < 0:
            raise ValueError("paternity-call counts must be non-negative")
        if self.outcross_calls + self.self_calls + self.unresolved_calls != self.sampled_mature_seeds:
            raise ValueError("paternity calls must partition sampled mature seeds")

    @property
    def resolved_calls(self) -> int:
        return self.outcross_calls + self.self_calls


@dataclass(frozen=True)
class SeedSetPaternityObservation:
    """One virtual field dataset and its component compatibility intervals."""

    seed_fates: SeedFateCounts
    paternity_calls: PaternityCalls
    observations: tuple[ScenarioObservation, ScenarioObservation]


@dataclass(frozen=True)
class SeedSetPaternityRecoverySummary:
    """Recovery properties under fruit-level seed set plus paternity sampling."""

    truth: ScenarioSpec
    replicates: int
    truth_retained_rate: float
    unique_truth_recovery_rate: float
    empty_compatible_set_rate: float
    mean_compatible_scenarios: float
    mean_resolved_paternity_calls: float


def _sample_mature_cross_types(
    outcross: int,
    selfed: int,
    draws: int,
    rng: Random,
) -> tuple[int, int]:
    """Sample cross types without replacement from one fruit's mature seeds."""

    if min(outcross, selfed, draws) < 0:
        raise ValueError("cross-type counts and draws must be non-negative")
    if draws > outcross + selfed:
        raise ValueError("cannot genotype more seeds than mature seeds")

    outcross_remaining = outcross
    selfed_remaining = selfed
    sampled_outcross = 0
    sampled_selfed = 0
    for _ in range(draws):
        total_remaining = outcross_remaining + selfed_remaining
        if rng.random() < outcross_remaining / total_remaining:
            sampled_outcross += 1
            outcross_remaining -= 1
        else:
            sampled_selfed += 1
            selfed_remaining -= 1
    return sampled_outcross, sampled_selfed


def _classify_paternity_calls(
    sampled_outcross: int,
    sampled_selfed: int,
    design: SeedSetPaternityDesign,
    rng: Random,
) -> PaternityCalls:
    """Apply unresolved calls and calibrated directional misclassification."""

    outcross_calls = 0
    self_calls = 0
    unresolved = 0
    for _ in range(sampled_outcross):
        if rng.random() < design.unresolved_probability:
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


def corrected_outcross_fraction_interval(
    calls: PaternityCalls,
    design: SeedSetPaternityDesign,
) -> tuple[float, float]:
    """Return an error-corrected Wilson interval for outcross fraction of mature seed.

    The correction inverts the two-class call matrix.  It is valid only when
    the supplied error rates are externally calibrated and call resolution is
    independent of true cross type; otherwise use a parentage likelihood that
    estimates these quantities jointly.
    """

    if calls.resolved_calls == 0:
        return 0.0, 1.0
    observed_lower, observed_upper = wilson_interval(
        calls.outcross_calls,
        calls.resolved_calls,
        design.marginal_confidence,
    )
    denominator = 1.0 - design.outcross_to_self_error - design.self_to_outcross_error
    lower = (observed_lower - design.self_to_outcross_error) / denominator
    upper = (observed_upper - design.self_to_outcross_error) / denominator
    return max(0.0, lower), min(1.0, upper)


def _component_observations(
    seed_fates: SeedFateCounts,
    paternity_calls: PaternityCalls,
    design: SeedSetPaternityDesign,
    year_label: str,
) -> tuple[ScenarioObservation, ScenarioObservation]:
    """Construct conservative per-fruit component intervals from the two stages."""

    mature = seed_fates.outcross_viable + seed_fates.selfed_viable
    mature_lower, mature_upper = wilson_interval(
        mature,
        seed_fates.total_ovules,
        design.marginal_confidence,
    )
    outcross_lower, outcross_upper = corrected_outcross_fraction_interval(
        paternity_calls,
        design,
    )
    scale = design.potential_ovules_per_fruit
    return (
        ScenarioObservation(
            ScenarioMetric.OUTCROSS_VIABLE_SEEDS,
            mature_lower * outcross_lower * scale,
            mature_upper * outcross_upper * scale,
            year_label,
        ),
        ScenarioObservation(
            ScenarioMetric.SELFED_VIABLE_SEEDS,
            mature_lower * (1.0 - outcross_upper) * scale,
            mature_upper * (1.0 - outcross_lower) * scale,
            year_label,
        ),
    )


def simulate_seed_set_paternity_observation(
    truth: ScenarioSpec,
    settings: ScenarioSettings,
    year_label: str,
    design: SeedSetPaternityDesign,
    rng: Random,
) -> SeedSetPaternityObservation:
    """Generate a fruit-level seed-set and partial-paternity virtual dataset."""

    result = simulate_guide_scenario(truth, settings)
    outcross_expected = result.metric(ScenarioMetric.OUTCROSS_VIABLE_SEEDS, year_label)
    selfed_expected = result.metric(ScenarioMetric.SELFED_VIABLE_SEEDS, year_label)
    outcross_probability, selfed_probability, _ = seed_fate_probabilities(
        outcross_expected,
        selfed_expected,
        design.potential_ovules_per_fruit,
    )

    total_outcross = 0
    total_selfed = 0
    total_other = 0
    total_sampled = 0
    total_outcross_calls = 0
    total_self_calls = 0
    total_unresolved = 0
    for _ in range(design.fruit_count):
        fruit = sample_seed_fates(
            outcross_probability,
            selfed_probability,
            design.potential_ovules_per_fruit,
            rng,
        )
        total_outcross += fruit.outcross_viable
        total_selfed += fruit.selfed_viable
        total_other += fruit.other
        sampled_outcross, sampled_selfed = _sample_mature_cross_types(
            fruit.outcross_viable,
            fruit.selfed_viable,
            min(design.genotyped_mature_seeds_per_fruit, fruit.outcross_viable + fruit.selfed_viable),
            rng,
        )
        calls = _classify_paternity_calls(sampled_outcross, sampled_selfed, design, rng)
        total_sampled += calls.sampled_mature_seeds
        total_outcross_calls += calls.outcross_calls
        total_self_calls += calls.self_calls
        total_unresolved += calls.unresolved_calls

    seed_fates = SeedFateCounts(
        outcross_viable=total_outcross,
        selfed_viable=total_selfed,
        other=total_other,
        total_ovules=design.total_ovules,
    )
    paternity_calls = PaternityCalls(
        outcross_calls=total_outcross_calls,
        self_calls=total_self_calls,
        unresolved_calls=total_unresolved,
        sampled_mature_seeds=total_sampled,
    )
    return SeedSetPaternityObservation(
        seed_fates=seed_fates,
        paternity_calls=paternity_calls,
        observations=_component_observations(seed_fates, paternity_calls, design, year_label),
    )


def benchmark_seed_set_paternity_recovery(
    truth: ScenarioSpec,
    candidates: Sequence[ScenarioSpec],
    settings: ScenarioSettings,
    year_label: str,
    design: SeedSetPaternityDesign,
    replicates: int,
    seed: int = 0,
) -> SeedSetPaternityRecoverySummary:
    """Estimate scenario recovery under the declared seed-set/paternity design."""

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
    resolved_total = 0
    for _ in range(replicates):
        virtual_observation = simulate_seed_set_paternity_observation(
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
        resolved_total += virtual_observation.paternity_calls.resolved_calls
        if truth in scenarios:
            truth_retained += 1
        if scenarios == (truth,):
            unique_truth += 1
        if not scenarios:
            empty += 1

    return SeedSetPaternityRecoverySummary(
        truth=truth,
        replicates=replicates,
        truth_retained_rate=truth_retained / replicates,
        unique_truth_recovery_rate=unique_truth / replicates,
        empty_compatible_set_rate=empty / replicates,
        mean_compatible_scenarios=compatible_total / replicates,
        mean_resolved_paternity_calls=resolved_total / replicates,
    )
