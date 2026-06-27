"""Late inbreeding-depression layer for guide/selfing comparisons.

Selfed seed output is not treated as fully compensatory merely because it is
present at seed set. This layer converts selfed and outcrossed viable seed to
retained recruits with separate post-seed survival multipliers.
"""

from __future__ import annotations

from dataclasses import dataclass


def _unit_interval(value: float, name: str) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must lie in [0, 1]")


@dataclass(frozen=True)
class PostSeedSurvival:
    """Post-seed survival for outcrossed offspring and late inbreeding depression.

    ``late_inbreeding_depression`` is the proportional reduction of the
    selfed-offspring path relative to the outcrossed path across the declared
    germination-to-recruit census interval.
    """

    outcrossed_survival: float
    late_inbreeding_depression: float

    def __post_init__(self) -> None:
        _unit_interval(self.outcrossed_survival, "outcrossed_survival")
        _unit_interval(self.late_inbreeding_depression, "late_inbreeding_depression")

    @property
    def selfed_survival(self) -> float:
        return self.outcrossed_survival * (1.0 - self.late_inbreeding_depression)


@dataclass(frozen=True)
class PostSeedResult:
    outcrossed_recruits: float
    selfed_recruits: float
    total_recruits: float
    selfed_recruit_fraction: float


def apply_post_seed_survival(
    outcross_viable_seeds: float,
    selfed_viable_seeds: float,
    survival: PostSeedSurvival,
) -> PostSeedResult:
    """Map seed components to recruit components over one declared interval."""

    if outcross_viable_seeds < 0.0 or selfed_viable_seeds < 0.0:
        raise ValueError("seed components must be non-negative")
    outcrossed_recruits = outcross_viable_seeds * survival.outcrossed_survival
    selfed_recruits = selfed_viable_seeds * survival.selfed_survival
    total = outcrossed_recruits + selfed_recruits
    fraction = 0.0 if total == 0.0 else selfed_recruits / total
    return PostSeedResult(
        outcrossed_recruits=outcrossed_recruits,
        selfed_recruits=selfed_recruits,
        total_recruits=total,
        selfed_recruit_fraction=fraction,
    )
