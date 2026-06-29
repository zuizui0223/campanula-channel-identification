"""Finite-sample observation helpers for pre-data operating-characteristic checks.

The compatibility engine deliberately consumes intervals rather than a full
likelihood.  When several observed quantities are compared to their own
marginal intervals, however, the chance that *all* intervals retain the true
mechanism can be much lower than the nominal confidence of each one.  This
module makes a conservative Bonferroni calibration explicit.

These functions do not turn the compatibility sweep into posterior inference.
They only make the intended family-wise coverage of supplied intervals auditable
and provide lightweight, dependency-free helpers for synthetic benchmarks.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, sqrt
from random import Random
from statistics import NormalDist, fmean, stdev
from typing import Mapping, Sequence


def bonferroni_marginal_confidence(
    familywise_confidence: float,
    observation_count: int,
) -> float:
    """Return the marginal confidence needed for Bonferroni family-wise control.

    If ``m`` intervals are each constructed at ``1 - alpha / m``, the union
    bound guarantees at least ``1 - alpha`` simultaneous coverage irrespective
    of dependence among the observations.  It is conservative, but that is
    preferable to silently treating several 95% marginal intervals as one 95%
    joint observation.
    """

    if not 0.0 < familywise_confidence < 1.0:
        raise ValueError("familywise_confidence must lie in (0, 1)")
    if observation_count <= 0:
        raise ValueError("observation_count must be positive")
    alpha = 1.0 - familywise_confidence
    return 1.0 - alpha / observation_count


@dataclass(frozen=True)
class SimultaneousIntervalPlan:
    """A declared interval calibration for one joint observation set."""

    familywise_confidence: float
    observation_count: int
    method: str = "bonferroni"

    def __post_init__(self) -> None:
        if self.method != "bonferroni":
            raise ValueError("only the conservative 'bonferroni' method is implemented")
        # Reuse the validation in the public helper.
        bonferroni_marginal_confidence(self.familywise_confidence, self.observation_count)

    @property
    def marginal_confidence(self) -> float:
        """Confidence to use for each supplied interval."""

        return bonferroni_marginal_confidence(
            self.familywise_confidence,
            self.observation_count,
        )

    @property
    def marginal_alpha(self) -> float:
        return 1.0 - self.marginal_confidence

    def describe(self) -> str:
        return (
            f"{self.method} family-wise {self.familywise_confidence:.3f}; "
            f"{self.observation_count} observables; "
            f"marginal confidence {self.marginal_confidence:.6f}"
        )


@dataclass(frozen=True)
class MeanInterval:
    """A normal-approximation interval for one per-maternal-individual mean."""

    mean: float
    lower: float
    upper: float
    confidence: float
    sample_size: int

    def contains(self, value: float) -> bool:
        return self.lower <= value <= self.upper


def normal_mean_interval(values: Sequence[float], confidence: float) -> MeanInterval:
    """Construct a transparent normal interval for a synthetic benchmark.

    This is intentionally a convenience helper, not a recommended production
    observation model for all count data.  Real field analyses should replace it
    with a count, binomial, beta-binomial, or hierarchical model appropriate to
    the assay.  It is useful here because it makes the multiple-interval issue
    reproducible without adding external dependencies.
    """

    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must lie in (0, 1)")
    if len(values) < 2:
        raise ValueError("at least two values are required to estimate a standard error")
    sample_mean = fmean(values)
    standard_error = stdev(values) / sqrt(len(values))
    z_value = NormalDist().inv_cdf((1.0 + confidence) / 2.0)
    return MeanInterval(
        mean=sample_mean,
        lower=sample_mean - z_value * standard_error,
        upper=sample_mean + z_value * standard_error,
        confidence=confidence,
        sample_size=len(values),
    )


def simultaneous_mean_intervals(
    observations: Mapping[str, Sequence[float]],
    plan: SimultaneousIntervalPlan,
) -> dict[str, MeanInterval]:
    """Create equally calibrated mean intervals for a declared set of observables."""

    if len(observations) != plan.observation_count:
        raise ValueError(
            "number of observation series must equal plan.observation_count "
            "so the declared family-wise calibration is auditable"
        )
    return {
        label: normal_mean_interval(values, plan.marginal_confidence)
        for label, values in observations.items()
    }


def poisson_sample(rate: float, rng: Random) -> int:
    """Draw one Poisson count for lightweight synthetic operating checks.

    Knuth's exact algorithm is used for the low-to-moderate rates typical of
    per-flower or per-maternal visitation summaries.  A continuity-corrected
    normal approximation keeps the helper practical at very large rates.  The
    function is for benchmark generation, not for fitting field data.
    """

    if rate < 0.0:
        raise ValueError("rate must be non-negative")
    if rate == 0.0:
        return 0
    if rate < 30.0:
        threshold = exp(-rate)
        product = 1.0
        count = 0
        while product > threshold:
            count += 1
            product *= rng.random()
        return count - 1
    return max(0, int(round(rng.gauss(rate, sqrt(rate)))))
