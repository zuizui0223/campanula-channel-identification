"""Explicit spatial recruitment layer for guide-trait scenarios.

This layer is deliberately downstream of local seed production. It prevents a
site-level trait contrast from being silently interpreted as a reproductive
mechanism when dispersal, patch retention, or habitat-specific establishment
could generate the observed recruit pattern.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


def _unit_interval(value: float, name: str) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must lie in [0, 1]")


@dataclass(frozen=True)
class Patch:
    name: str
    establishment_probability: float
    capacity: float

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("patch name must be non-empty")
        _unit_interval(self.establishment_probability, "establishment_probability")
        if self.capacity < 0.0:
            raise ValueError("capacity must be non-negative")


@dataclass(frozen=True)
class SpatialRecruitmentResult:
    recruits_by_patch: tuple[float, ...]
    total_retained_recruits: float


def distribute_seeds_to_patches(
    viable_seeds: float,
    patches: Sequence[Patch],
    dispersal_probabilities: Sequence[float],
) -> SpatialRecruitmentResult:
    """Map viable seed output to capacity-limited patch recruitment.

    Dispersal probabilities must sum to one. Capacity clipping is explicit so
    the user cannot interpret recruitment differences as seed-production
    differences once local saturation is reached.
    """

    if viable_seeds < 0.0:
        raise ValueError("viable_seeds must be non-negative")
    if not patches or len(patches) != len(dispersal_probabilities):
        raise ValueError("patches and dispersal_probabilities must be non-empty and aligned")
    if any(probability < 0.0 for probability in dispersal_probabilities):
        raise ValueError("dispersal probabilities must be non-negative")
    if abs(sum(dispersal_probabilities) - 1.0) > 1e-9:
        raise ValueError("dispersal probabilities must sum to one")
    recruits = tuple(
        min(patch.capacity, viable_seeds * probability * patch.establishment_probability)
        for patch, probability in zip(patches, dispersal_probabilities)
    )
    return SpatialRecruitmentResult(
        recruits_by_patch=recruits,
        total_retained_recruits=sum(recruits),
    )
