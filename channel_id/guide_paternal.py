"""Paternal-fitness extension for the nectar-guide mechanism model.

This module deliberately separates maternal and paternal genetic contribution.
A nectar guide can increase female success by improving receipt of outcross
pollen, paternal success by increasing export/siring, both, or neither.

The model is conditional on a declared currency.  ``male_weight`` represents
the conversion from successful siring events to the maternal-equivalent census
used for the comparison; it is not universally fixed at one.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp

from .nectar_guide import (
    NectarGuideParameters,
    NectarGuideRegime,
    NectarGuideTrait,
    simulate_nectar_guide_life_history,
)


def _nonnegative(value: float, name: str) -> None:
    if value < 0.0:
        raise ValueError(f"{name} must be non-negative")


@dataclass(frozen=True)
class PaternalGuideParameters:
    """Parameters for pollen export and realised siring.

    ``guide_export_gain`` affects pollen export independently of receipt.
    ``baseline_siring_success`` converts exported pollen to realised paternal
    recruits in the declared recipient population.  This conversion is a
    summary parameter and must later be constrained by paternity or pollen
    transfer data.
    """

    baseline_pollen_export: float
    display_export_gain: float
    guide_export_gain: float
    baseline_siring_success: float
    guide_siring_gain: float = 0.0
    male_weight: float = 1.0

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            _nonnegative(value, name)


@dataclass(frozen=True)
class PaternalGuideResult:
    """Maternal, paternal, and combined genetic contribution."""

    maternal_retained_recruits: float
    expected_pollen_export: float
    realised_siring_success: float
    paternal_retained_recruits: float
    total_genetic_contribution: float


def simulate_guide_paternal_fitness(
    trait: NectarGuideTrait,
    regime: NectarGuideRegime,
    maternal_parameters: NectarGuideParameters,
    paternal_parameters: PaternalGuideParameters,
) -> PaternalGuideResult:
    """Evaluate a joint maternal/paternal performance contrast.

    Pollen export is tied to expected visits but is distinct from maternal
    pollen receipt. A guide can therefore improve the paternal component even
    when it has no effect on the plant's own outcross fraction.
    """

    maternal = simulate_nectar_guide_life_history(trait, regime, maternal_parameters)
    expected_pollen_export = maternal.expected_visits * (
        paternal_parameters.baseline_pollen_export
        + paternal_parameters.display_export_gain * trait.display
        + paternal_parameters.guide_export_gain * trait.guide_contrast
    )
    realised_siring_success = 1.0 - exp(
        -expected_pollen_export
        * (
            paternal_parameters.baseline_siring_success
            + paternal_parameters.guide_siring_gain * trait.guide_contrast
        )
    )
    paternal_retained_recruits = expected_pollen_export * realised_siring_success
    total = maternal.retained_recruits + paternal_parameters.male_weight * paternal_retained_recruits
    return PaternalGuideResult(
        maternal_retained_recruits=maternal.retained_recruits,
        expected_pollen_export=expected_pollen_export,
        realised_siring_success=realised_siring_success,
        paternal_retained_recruits=paternal_retained_recruits,
        total_genetic_contribution=total,
    )
