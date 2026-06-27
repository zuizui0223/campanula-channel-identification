"""Constrained life-history simulation for Campanula trait hypotheses.

This module is deliberately a *compatibility* engine, not an automatic causal
inference engine.  It maps declared trait values and environmental regimes to
observable life-history quantities, then retains only parameter settings that
are compatible with predeclared measurement intervals.

The intended use is to ask questions such as:

    Which combinations of attraction cost, assurance cost, and selfing
    viability can reproduce the observed seed output and recruit pattern?

It must not be used to turn an unmeasured cost into a point estimate.  A
candidate survives only relative to the observations and intervals supplied by
the user.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from itertools import product
from typing import Iterable, Mapping, Sequence


class Metric(str, Enum):
    """Observable quantities on the declared maternal-individual scale."""

    OUTCROSS_VIABLE_SEEDS = "outcross_viable_seeds"
    SELFED_VIABLE_SEEDS = "selfed_viable_seeds"
    LOCAL_VIABLE_SEED_OUTPUT = "local_viable_seed_output"
    ESTABLISHMENT = "establishment"
    RETAINED_RECRUITS = "retained_recruits"


def _unit_interval(value: float, name: str) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must lie in [0, 1]")


def _nonnegative(value: float, name: str) -> None:
    if value < 0.0:
        raise ValueError(f"{name} must be non-negative")


@dataclass(frozen=True)
class TraitState:
    """Scaled investment in the two initially modelled Campanula modules.

    ``attraction`` may later be mapped to a predeclared composite of floral
    display, colour contrast, nectar guide, flower size, or nectar.  It is not
    a claim that those traits are interchangeable.

    ``assurance`` represents autonomous or delayed selfing capacity.  Its
    biological measurement must be declared separately for each study.
    """

    attraction: float
    assurance: float

    def __post_init__(self) -> None:
        _unit_interval(self.attraction, "attraction")
        _unit_interval(self.assurance, "assurance")


@dataclass(frozen=True)
class Regime:
    """Exogenous conditions measured or declared for a comparison."""

    pollinator_service: float
    establishment_multiplier: float = 1.0

    def __post_init__(self) -> None:
        _unit_interval(self.pollinator_service, "pollinator_service")
        _nonnegative(self.establishment_multiplier, "establishment_multiplier")


@dataclass(frozen=True)
class LifeHistoryParameters:
    """Mechanistic and potentially unknown parameters for one candidate model.

    Parameters are intentionally dimensionless until a study supplies a
    calibration. ``attraction_cost`` and ``assurance_cost`` are the hidden
    quantities usually explored by a grid or prior sweep; they are not
    estimated merely by constructing this object.
    """

    seed_budget: float
    baseline_outcross_fraction: float
    attraction_pollination_gain: float
    attraction_cost: float
    assurance_cost: float
    selfing_viability: float
    baseline_establishment: float

    def __post_init__(self) -> None:
        _nonnegative(self.seed_budget, "seed_budget")
        _unit_interval(self.baseline_outcross_fraction, "baseline_outcross_fraction")
        _nonnegative(self.attraction_pollination_gain, "attraction_pollination_gain")
        _nonnegative(self.attraction_cost, "attraction_cost")
        _nonnegative(self.assurance_cost, "assurance_cost")
        _unit_interval(self.selfing_viability, "selfing_viability")
        _unit_interval(self.baseline_establishment, "baseline_establishment")


@dataclass(frozen=True)
class LifeHistoryResult:
    """Simulation output on a common maternal-individual census scale."""

    outcross_viable_seeds: float
    selfed_viable_seeds: float
    local_viable_seed_output: float
    establishment: float
    retained_recruits: float

    def metric(self, metric: Metric) -> float:
        return getattr(self, metric.value)


def simulate_life_history(
    trait: TraitState,
    regime: Regime,
    parameters: LifeHistoryParameters,
) -> LifeHistoryResult:
    """Simulate one trait--regime combination.

    The declared life cycle is:

    1. investment costs reduce a potential viable-seed budget;
    2. pollinator service and attraction determine the outcrossed fraction;
    3. assurance converts some un-outcrossed ovules into selfed viable seeds;
    4. a regime-specific establishment probability maps viable seeds to
       retained recruits.

    This is a minimal, falsifiable model, not a universal Campanula life cycle.
    In particular, it assumes that attraction and assurance affect local seed
    production only. A direct trait effect on establishment should be added
    only after a study has a biological and measurement rationale for it.
    """

    remaining_budget = max(
        0.0,
        parameters.seed_budget
        - parameters.attraction_cost * trait.attraction**2
        - parameters.assurance_cost * trait.assurance**2,
    )
    outcross_fraction = min(
        1.0,
        regime.pollinator_service
        * (
            parameters.baseline_outcross_fraction
            + parameters.attraction_pollination_gain * trait.attraction
        ),
    )
    outcross_viable_seeds = remaining_budget * outcross_fraction
    selfed_viable_seeds = (
        remaining_budget
        * (1.0 - outcross_fraction)
        * trait.assurance
        * parameters.selfing_viability
    )
    local_viable_seed_output = outcross_viable_seeds + selfed_viable_seeds
    establishment = min(
        1.0,
        parameters.baseline_establishment * regime.establishment_multiplier,
    )
    retained_recruits = local_viable_seed_output * establishment

    return LifeHistoryResult(
        outcross_viable_seeds=outcross_viable_seeds,
        selfed_viable_seeds=selfed_viable_seeds,
        local_viable_seed_output=local_viable_seed_output,
        establishment=establishment,
        retained_recruits=retained_recruits,
    )


@dataclass(frozen=True)
class ObservationInterval:
    """Predeclared compatible interval for one observable quantity."""

    metric: Metric
    lower: float
    upper: float

    def __post_init__(self) -> None:
        _nonnegative(self.lower, "lower")
        _nonnegative(self.upper, "upper")
        if self.lower > self.upper:
            raise ValueError("lower must not exceed upper")

    def contains(self, value: float) -> bool:
        return self.lower <= value <= self.upper


@dataclass(frozen=True)
class SimulationCase:
    """A trait--regime comparison plus the observables it must reproduce."""

    name: str
    trait: TraitState
    regime: Regime
    observations: tuple[ObservationInterval, ...]

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("name must be non-empty")
        if not self.observations:
            raise ValueError("at least one observation interval is required")


@dataclass(frozen=True)
class CompatibilityResult:
    """Whether one candidate reproduces every declared case interval."""

    parameters: LifeHistoryParameters
    compatible: bool
    failures: tuple[str, ...]
    predictions: Mapping[str, LifeHistoryResult]


def assess_compatibility(
    parameters: LifeHistoryParameters,
    cases: Sequence[SimulationCase],
) -> CompatibilityResult:
    """Test a candidate only against declared observables and intervals."""

    failures: list[str] = []
    predictions: dict[str, LifeHistoryResult] = {}
    for case in cases:
        result = simulate_life_history(case.trait, case.regime, parameters)
        predictions[case.name] = result
        for observation in case.observations:
            value = result.metric(observation.metric)
            if not observation.contains(value):
                failures.append(
                    f"{case.name}: {observation.metric.value}={value:.6g} is outside "
                    f"[{observation.lower:.6g}, {observation.upper:.6g}]"
                )

    return CompatibilityResult(
        parameters=parameters,
        compatible=not failures,
        failures=tuple(failures),
        predictions=predictions,
    )


@dataclass(frozen=True)
class ParameterGrid:
    """Finite candidate values for a transparent compatibility sweep."""

    seed_budget: tuple[float, ...]
    baseline_outcross_fraction: tuple[float, ...]
    attraction_pollination_gain: tuple[float, ...]
    attraction_cost: tuple[float, ...]
    assurance_cost: tuple[float, ...]
    selfing_viability: tuple[float, ...]
    baseline_establishment: tuple[float, ...]

    def candidates(self) -> Iterable[LifeHistoryParameters]:
        """Yield all candidates; grids should be kept intentionally small."""

        fields = (
            self.seed_budget,
            self.baseline_outcross_fraction,
            self.attraction_pollination_gain,
            self.attraction_cost,
            self.assurance_cost,
            self.selfing_viability,
            self.baseline_establishment,
        )
        if any(not values for values in fields):
            raise ValueError("every parameter grid axis must contain at least one value")
        for values in product(*fields):
            yield LifeHistoryParameters(*values)


def retain_compatible_candidates(
    grid: ParameterGrid,
    cases: Sequence[SimulationCase],
) -> tuple[CompatibilityResult, ...]:
    """Return the full compatible set rather than a single privileged solution."""

    return tuple(
        report
        for parameters in grid.candidates()
        if (report := assess_compatibility(parameters, cases)).compatible
    )
