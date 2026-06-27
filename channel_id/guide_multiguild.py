"""Functional-guild extension for nectar-guide fitness.

Guilds remain explicit rather than being averaged into one visitor count. Each
can respond differently to guide contrast in visit rate, legitimate handling,
and pollen export.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp
from typing import Sequence

from .nectar_guide import NectarGuideTrait


def _nonnegative(value: float, name: str) -> None:
    if value < 0.0:
        raise ValueError(f"{name} must be non-negative")


def _unit(value: float, name: str) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must lie in [0, 1]")


@dataclass(frozen=True)
class PollinatorGuild:
    """One functionally distinct visitor guild.

    `service` is a regime-specific abundance/activity scaling. The remaining
    terms are phenotype-response coefficients that should later be informed by
    guild-resolved observations, not inferred from a pooled visit count.
    """

    name: str
    service: float
    baseline_visit_rate: float
    guide_visit_gain: float
    baseline_legitimate_fraction: float
    guide_handling_gain: float
    pollen_deposition_per_contact: float
    pollen_export_per_visit: float
    guide_export_gain: float = 0.0
    siring_conversion: float = 0.0

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("guild name must be non-empty")
        for name, value in self.__dict__.items():
            if name != "name":
                _nonnegative(value, name)
        _unit(self.baseline_legitimate_fraction, "baseline_legitimate_fraction")


@dataclass(frozen=True)
class MultiguildGuideResult:
    expected_visits: float
    deposition_pressure: float
    outcross_fraction: float
    pollen_export: float
    paternal_success: float


def simulate_multiguild_guide_response(
    trait: NectarGuideTrait,
    guilds: Sequence[PollinatorGuild],
) -> MultiguildGuideResult:
    """Aggregate guild-resolved pathways into outcross and paternal indices.

    This is intentionally a mechanistic intermediate layer rather than a full
    seed-budget model. It can be supplied to the maternal/paternal layers after
    data determine the appropriate conversion scales.
    """

    if not guilds:
        raise ValueError("at least one pollinator guild is required")
    visits = 0.0
    deposition = 0.0
    export = 0.0
    paternal_pressure = 0.0
    for guild in guilds:
        guild_visits = guild.service * (guild.baseline_visit_rate + guild.guide_visit_gain * trait.guide_contrast)
        handling = min(1.0, guild.baseline_legitimate_fraction + guild.guide_handling_gain * trait.guide_contrast)
        visits += guild_visits
        deposition += guild_visits * handling * guild.pollen_deposition_per_contact
        guild_export = guild_visits * (guild.pollen_export_per_visit + guild.guide_export_gain * trait.guide_contrast)
        export += guild_export
        paternal_pressure += guild_export * guild.siring_conversion
    return MultiguildGuideResult(
        expected_visits=visits,
        deposition_pressure=deposition,
        outcross_fraction=1.0 - exp(-deposition),
        pollen_export=export,
        paternal_success=1.0 - exp(-paternal_pressure),
    )
