"""Optional recruitment responses for designs with seed-addition or cohort data.

The baseline channel factorisation can use a regime-level establishment factor
``E``.  That approximation is not safe once viable-seed output itself changes
local recruitment through density dependence or capacity limitation.  This
module offers the smallest explicit alternative: a Beverton-Holt response in
which per-seed establishment declines smoothly with viable-seed density.

Do not activate this layer because it is biologically plausible in general.
Activate it only when the study measures viable seed supply together with
seedling/cohort recruitment at a shared spatial and temporal census scale.
"""

from __future__ import annotations

from dataclasses import dataclass


def _unit_interval(value: float, name: str) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must lie in [0, 1]")


@dataclass(frozen=True)
class RecruitmentResult:
    """Recruitment on a declared seed-to-recruit census scale."""

    viable_seeds: float
    establishment_probability: float
    retained_recruits: float


@dataclass(frozen=True)
class ConstantEstablishment:
    """The existing baseline: establishment does not vary with seed supply."""

    probability: float

    def __post_init__(self) -> None:
        _unit_interval(self.probability, "probability")

    def recruit(self, viable_seeds: float) -> RecruitmentResult:
        if viable_seeds < 0.0:
            raise ValueError("viable_seeds must be non-negative")
        return RecruitmentResult(
            viable_seeds=viable_seeds,
            establishment_probability=self.probability,
            retained_recruits=viable_seeds * self.probability,
        )


@dataclass(frozen=True)
class BevertonHoltEstablishment:
    """Density-dependent recruitment with a measurable half-saturation scale.

    ``low_density_probability`` is the per-seed establishment probability near
    zero seed supply.  ``half_saturation_viable_seeds`` is the viable-seed
    supply at which that probability is halved:

    ``E(F) = low_density_probability / (1 + F / half_saturation_viable_seeds)``.

    The resulting ``W = F E(F)`` remains a declared factorisation, but ``E`` is
    now conditional on local seed supply rather than a constant multiplier.
    """

    low_density_probability: float
    half_saturation_viable_seeds: float

    def __post_init__(self) -> None:
        _unit_interval(self.low_density_probability, "low_density_probability")
        if self.half_saturation_viable_seeds <= 0.0:
            raise ValueError("half_saturation_viable_seeds must be positive")

    def establishment_probability(self, viable_seeds: float) -> float:
        if viable_seeds < 0.0:
            raise ValueError("viable_seeds must be non-negative")
        return self.low_density_probability / (
            1.0 + viable_seeds / self.half_saturation_viable_seeds
        )

    def recruit(self, viable_seeds: float) -> RecruitmentResult:
        establishment = self.establishment_probability(viable_seeds)
        return RecruitmentResult(
            viable_seeds=viable_seeds,
            establishment_probability=establishment,
            retained_recruits=viable_seeds * establishment,
        )
