"""Temporal fitness summaries for nectar-guide strategies.

Arithmetic mean performance alone can be misleading under fluctuating pollinator
service. This module reports both arithmetic and geometric means over declared
year states, with explicit zero handling.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, log
from typing import Sequence


@dataclass(frozen=True)
class YearPerformance:
    """Fitness contribution in one environmental state or observed year."""

    label: str
    contribution: float
    probability: float = 1.0

    def __post_init__(self) -> None:
        if not self.label:
            raise ValueError("year label must be non-empty")
        if self.contribution < 0.0:
            raise ValueError("contribution must be non-negative")
        if self.probability <= 0.0:
            raise ValueError("probability must be positive")


@dataclass(frozen=True)
class TemporalFitnessSummary:
    arithmetic_mean: float
    geometric_mean: float
    log_geometric_mean: float | None
    zero_contribution_states: tuple[str, ...]


def summarise_temporal_fitness(years: Sequence[YearPerformance]) -> TemporalFitnessSummary:
    """Compute probability-weighted arithmetic and geometric mean fitness.

    A zero contribution in a state of positive probability yields geometric
    mean zero and log geometric mean ``None``. That is intentional: an
    occasional complete reproductive failure cannot be silently averaged away.
    """

    if not years:
        raise ValueError("at least one year or state is required")
    total_probability = sum(year.probability for year in years)
    arithmetic = sum(year.probability * year.contribution for year in years) / total_probability
    zeros = tuple(year.label for year in years if year.contribution == 0.0)
    if zeros:
        return TemporalFitnessSummary(
            arithmetic_mean=arithmetic,
            geometric_mean=0.0,
            log_geometric_mean=None,
            zero_contribution_states=zeros,
        )
    log_mean = sum(year.probability * log(year.contribution) for year in years) / total_probability
    return TemporalFitnessSummary(
        arithmetic_mean=arithmetic,
        geometric_mean=exp(log_mean),
        log_geometric_mean=log_mean,
        zero_contribution_states=(),
    )
