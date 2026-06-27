"""Separate genetic guide value from environmentally induced guide expression.

This is a measurement/design layer, not a quantitative-genetic inference
engine. It ensures that evolutionary comparisons can declare whether selection
is being evaluated on a breeding value, a plastic phenotype, or both.
"""

from __future__ import annotations

from dataclasses import dataclass


def _unit_interval(value: float, name: str) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must lie in [0, 1]")


@dataclass(frozen=True)
class GuideReactionNorm:
    """A bounded guide phenotype from genetic baseline and environment.

    The environmental driver must be declared (e.g. light, nutrient status,
    water stress, herbivory, or developmental condition). ``plastic_slope``
    is intentionally not interpreted as adaptive without common-environment or
    family-level evidence.
    """

    genetic_baseline: float
    plastic_slope: float
    environment: float

    def __post_init__(self) -> None:
        _unit_interval(self.genetic_baseline, "genetic_baseline")
        _unit_interval(self.environment, "environment")

    @property
    def expressed_guide_contrast(self) -> float:
        return min(1.0, max(0.0, self.genetic_baseline + self.plastic_slope * (self.environment - 0.5)))


@dataclass(frozen=True)
class FamilyGuideObservation:
    """Minimal family/common-environment input needed to separate components."""

    family_id: str
    environment_id: str
    expressed_guide_contrast: float

    def __post_init__(self) -> None:
        if not self.family_id or not self.environment_id:
            raise ValueError("family_id and environment_id must be non-empty")
        _unit_interval(self.expressed_guide_contrast, "expressed_guide_contrast")
