"""Rank proposed observations by how strongly they split compatible candidates.

The constrained life-history layer keeps every parameter candidate that is
compatible with existing observations.  This module asks a strictly narrower
next question:

    Given that compatible set, which *declared future measurement* would most
    reduce it at the stated measurement resolution?

The ranking is conditional on the candidate grid, a uniform weight over its
surviving candidates, and the stated resolution.  It is a design heuristic,
not a posterior probability calculation and not a substitute for replication,
field feasibility, or biological importance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .life_history import CompatibilityResult, Metric


@dataclass(frozen=True)
class MeasurementOption:
    """One measurable quantity in one declared simulation case.

    ``resolution`` is the minimum absolute separation in model predictions
    treated as distinguishable by the proposed assay. It should be chosen from
    a predeclared uncertainty target (for example an expected confidence or
    credible interval width), not from the model output after seeing it.
    """

    case_name: str
    metric: Metric
    resolution: float
    label: str | None = None

    def __post_init__(self) -> None:
        if not self.case_name:
            raise ValueError("case_name must be non-empty")
        if self.resolution <= 0.0:
            raise ValueError("resolution must be positive")

    @property
    def display_name(self) -> str:
        return self.label or f"{self.case_name}:{self.metric.value}"


@dataclass(frozen=True)
class MeasurementRanking:
    """Compatibility-set reduction expected from an idealised measurement."""

    option: MeasurementOption
    candidate_count: int
    outcome_class_sizes: tuple[int, ...]
    prediction_min: float
    prediction_max: float
    expected_remaining_candidates: float
    expected_eliminated_candidates: float

    @property
    def outcome_class_count(self) -> int:
        return len(self.outcome_class_sizes)

    @property
    def largest_outcome_class(self) -> int:
        return max(self.outcome_class_sizes)

    @property
    def prediction_span(self) -> float:
        return self.prediction_max - self.prediction_min


def _outcome_class_sizes(values: Sequence[float], resolution: float) -> tuple[int, ...]:
    """Group predictions into non-overlapping resolution-limited outcome classes.

    Predictions are sorted. A class may span at most ``resolution`` from its
    first value, preventing a chained series of individually close values from
    being treated as a misleadingly broad single outcome.
    """

    if not values:
        raise ValueError("at least one prediction is required")

    ordered = sorted(values)
    sizes: list[int] = []
    class_start = ordered[0]
    class_size = 1
    for value in ordered[1:]:
        if value - class_start <= resolution:
            class_size += 1
        else:
            sizes.append(class_size)
            class_start = value
            class_size = 1
    sizes.append(class_size)
    return tuple(sizes)


def rank_measurements(
    compatible: Sequence[CompatibilityResult],
    options: Sequence[MeasurementOption],
) -> tuple[MeasurementRanking, ...]:
    """Rank measurement options by expected compatible-set reduction.

    For each option, candidates whose predictions fall into the same
    resolution-limited outcome class remain indistinguishable. Under equal
    weight for each compatible candidate, the expected size left after an
    observation is ``sum(n_i**2) / N``.  The expected reduction is ``N`` minus
    that quantity.

    All reports must be compatible and must carry predictions for each named
    case. This avoids accidentally ranking a measurement against candidate
    settings already excluded by current data.
    """

    if not compatible:
        raise ValueError("at least one compatible candidate is required")
    if not options:
        return ()
    if any(not report.compatible for report in compatible):
        raise ValueError("all reports must be compatible candidates")

    count = len(compatible)
    rankings: list[MeasurementRanking] = []
    for option in options:
        values: list[float] = []
        for report in compatible:
            try:
                result = report.predictions[option.case_name]
            except KeyError as error:
                raise ValueError(
                    f"case {option.case_name!r} is absent from a compatible report"
                ) from error
            values.append(result.metric(option.metric))

        sizes = _outcome_class_sizes(values, option.resolution)
        expected_remaining = sum(size * size for size in sizes) / count
        rankings.append(
            MeasurementRanking(
                option=option,
                candidate_count=count,
                outcome_class_sizes=sizes,
                prediction_min=min(values),
                prediction_max=max(values),
                expected_remaining_candidates=expected_remaining,
                expected_eliminated_candidates=count - expected_remaining,
            )
        )

    return tuple(
        sorted(
            rankings,
            key=lambda ranking: (
                -ranking.expected_eliminated_candidates,
                -ranking.outcome_class_count,
                -ranking.prediction_span,
                ranking.option.display_name,
            ),
        )
    )
