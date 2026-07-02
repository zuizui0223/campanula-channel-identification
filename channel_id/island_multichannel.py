"""Evidence-constrained, multichannel island scenario comparison.

This module joins source-locked island summaries without pretending that a
public occurrence record measures pollination.  It uses prior Monte Carlo
integration to compare restricted scenarios against separate observation
channels: outcrossing, bagging/autonomous seed production, flower length, and
optional ordinal guide/spot constraints.

It is intentionally a small-island, partial-identification tool.  Its scores
are prior-sensitive compatibility summaries, not estimates of historical
causal effects or Bayes factors for evolution.
"""

from __future__ import annotations

import csv
import math
import random
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from statistics import mean, pstdev
from typing import Iterable, Sequence


class IslandScenario(str, Enum):
    """Restricted causal explanations compared on the same data channels."""

    ENVIRONMENT_ONLY = "environment_only"
    BODY_SIZE_ONLY = "body_size_only"
    SMALL_BEE_SUBSTITUTION = "small_bee_substitution"
    ARDENS_BRIDGE_LOSS = "ardens_bridge_loss"


class EvidenceChannel(str, Enum):
    OUTCROSSING = "outcrossing"
    BAGGING = "bagging"
    FLOWER = "flower"
    GUIDE_ORDER = "guide_order"


@dataclass(frozen=True)
class IslandEvidence:
    """One island-level evidence row.

    Pollinator fields are source-locked occurrence/visitor-regime indicators.
    They are inputs to a *candidate availability* model, not records of
    flower-specific visitation effectiveness.
    """

    island_id: str
    bombus_diversus: float
    bombus_ardens: float
    halictid_pollinator: float
    megachilid_pollinator: float
    outcrossing_mid: float | None
    bagged_capsule_fraction: float | None
    flower_length_mm: float | None
    environment: tuple[float | None, ...]
    source_row: int | None = None

    def __post_init__(self) -> None:
        if not self.island_id:
            raise ValueError("island_id is required")
        for field in (
            "bombus_diversus",
            "bombus_ardens",
            "halictid_pollinator",
            "megachilid_pollinator",
        ):
            value = getattr(self, field)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{field} must lie in [0, 1]")
        if self.outcrossing_mid is not None and not 0.0 <= self.outcrossing_mid <= 1.0:
            raise ValueError("outcrossing_mid must lie in [0, 1]")
        if self.bagged_capsule_fraction is not None and not 0.0 <= self.bagged_capsule_fraction <= 1.0:
            raise ValueError("bagged_capsule_fraction must lie in [0, 1]")
        if self.flower_length_mm is not None and self.flower_length_mm <= 0.0:
            raise ValueError("flower_length_mm must be positive")


@dataclass(frozen=True)
class GuideOrderConstraint:
    """A reviewable directional guide/spot comparison.

    `relation` is `gt` when left is judged stronger than right, and `lt` for
    the reverse.  This supports image/literature information that can be
    inspected but cannot honestly be reduced to a continuous spot fraction.
    """

    constraint_id: str
    left_island: str
    right_island: str
    relation: str
    source_id: str
    source_noise: float = 1.0
    notes: str = ""

    def __post_init__(self) -> None:
        if self.relation not in {"gt", "lt"}:
            raise ValueError("relation must be 'gt' or 'lt'")
        if not self.constraint_id or not self.left_island or not self.right_island or not self.source_id:
            raise ValueError("constraint_id, islands, and source_id are required")
        if self.left_island == self.right_island:
            raise ValueError("guide constraint must compare different islands")
        if self.source_noise <= 0.0:
            raise ValueError("source_noise must be positive")


@dataclass(frozen=True)
class ObservationScale:
    """Declared observational uncertainty on each measurement scale."""

    outcrossing_logit_sd: float = 0.85
    bagging_logit_sd: float = 1.10
    flower_sd_mm: float = 7.5
    guide_latent_sd: float = 1.0

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            if value <= 0.0 or not math.isfinite(value):
                raise ValueError(f"{name} must be finite and positive")


@dataclass(frozen=True)
class ScenarioDraw:
    """One prior draw. Values are model-scale quantities, not field estimates."""

    large_bombus_effectiveness: float
    ardens_effectiveness: float
    small_bee_effectiveness: float
    environment_weights: tuple[float, ...]
    outcrossing_intercept: float
    outcrossing_service: float
    outcrossing_assurance: float
    outcrossing_environment: float
    assurance_intercept: float
    assurance_service: float
    assurance_environment: float
    bagging_intercept: float
    bagging_assurance: float
    bagging_environment: float
    flower_intercept: float
    flower_service: float
    flower_environment: float
    guide_intercept: float
    guide_service: float
    guide_assurance: float
    guide_environment: float

    def __post_init__(self) -> None:
        for name in (
            "large_bombus_effectiveness",
            "ardens_effectiveness",
            "small_bee_effectiveness",
        ):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must lie in [0, 1]")
        if not self.environment_weights:
            raise ValueError("environment_weights cannot be empty")
        for name, value in self.__dict__.items():
            if name == "environment_weights":
                if not all(math.isfinite(v) for v in value):
                    raise ValueError("environment_weights must be finite")
            elif not math.isfinite(value):
                raise ValueError(f"{name} must be finite")


@dataclass(frozen=True)
class IslandPrediction:
    island_id: str
    effective_outcross_service: float | None
    assurance: float
    expected_outcrossing: float
    expected_bagging: float
    expected_flower_length_mm: float
    latent_guide: float


@dataclass(frozen=True)
class ScenarioSummary:
    scenario: IslandScenario
    draws: int
    log_marginal_compatibility: float
    mean_log_likelihood: float
    mean_outcrossing_log_likelihood: float
    mean_bagging_log_likelihood: float
    mean_flower_log_likelihood: float
    mean_guide_log_likelihood: float
    posterior_best_draw_fraction: float
    expected_predictions: tuple[IslandPrediction, ...]
    included_channels: tuple[EvidenceChannel, ...]
    boundary: str


@dataclass(frozen=True)
class _DrawResult:
    log_likelihood: float
    by_channel: dict[EvidenceChannel, float]
    predictions: tuple[IslandPrediction, ...]


def _safe_float(value: str | None) -> float | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    parsed = float(text)
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite numeric value: {value!r}")
    return parsed


def _clamp_probability(value: float) -> float:
    return min(1.0 - 1e-6, max(1e-6, value))


def _logit(value: float) -> float:
    value = _clamp_probability(value)
    return math.log(value / (1.0 - value))


def _expit(value: float) -> float:
    if value >= 0:
        exp_neg = math.exp(-value)
        return 1.0 / (1.0 + exp_neg)
    exp_pos = math.exp(value)
    return exp_pos / (1.0 + exp_pos)


def _normal_logpdf(value: float, expected: float, sd: float) -> float:
    variance = sd * sd
    return -0.5 * (math.log(2.0 * math.pi * variance) + ((value - expected) ** 2) / variance)


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def _logsumexp(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("values cannot be empty")
    maximum = max(values)
    return maximum + math.log(sum(math.exp(value - maximum) for value in values))


def _standardize_environment(evidence: Sequence[IslandEvidence]) -> dict[str, tuple[float, ...]]:
    """Standardize each declared environment field without inventing missing data."""
    dimensions = {len(row.environment) for row in evidence}
    if len(dimensions) != 1:
        raise ValueError("all evidence rows must have the same number of environment fields")
    dim = dimensions.pop()
    columns: list[list[float]] = [[] for _ in range(dim)]
    for row in evidence:
        for index, value in enumerate(row.environment):
            if value is not None:
                columns[index].append(value)
    moments: list[tuple[float, float] | None] = []
    for values in columns:
        if len(values) < 2 or pstdev(values) == 0.0:
            moments.append(None)
        else:
            moments.append((mean(values), pstdev(values)))
    result: dict[str, tuple[float, ...]] = {}
    for row in evidence:
        standardized: list[float] = []
        for value, moment in zip(row.environment, moments):
            if value is None or moment is None:
                standardized.append(0.0)
            else:
                standardized.append((value - moment[0]) / moment[1])
        result[row.island_id] = tuple(standardized)
    return result


def _environment_score(standardized: tuple[float, ...], weights: tuple[float, ...]) -> float:
    if len(standardized) != len(weights):
        raise ValueError("environment dimensions do not match parameter weights")
    return sum(value * weight for value, weight in zip(standardized, weights))


def _effective_service(
    scenario: IslandScenario,
    row: IslandEvidence,
    draw: ScenarioDraw,
) -> float | None:
    if scenario is IslandScenario.ENVIRONMENT_ONLY:
        return None
    small_availability = max(row.halictid_pollinator, row.megachilid_pollinator)
    small_effectiveness = draw.small_bee_effectiveness
    if scenario is IslandScenario.SMALL_BEE_SUBSTITUTION:
        small_effectiveness = max(small_effectiveness, draw.ardens_effectiveness)
    service = (
        row.bombus_diversus * draw.large_bombus_effectiveness
        + row.bombus_ardens * draw.ardens_effectiveness
        + small_availability * small_effectiveness
    )
    return min(1.0, max(0.0, service))


def _predict(
    scenario: IslandScenario,
    row: IslandEvidence,
    draw: ScenarioDraw,
    standardized_environment: tuple[float, ...],
) -> IslandPrediction:
    environment = _environment_score(standardized_environment, draw.environment_weights)
    service = _effective_service(scenario, row, draw)
    service_for_equations = 0.5 if service is None else service

    if scenario is IslandScenario.ENVIRONMENT_ONLY:
        assurance = _expit(draw.assurance_intercept + draw.assurance_environment * environment)
        outcrossing = _expit(
            draw.outcrossing_intercept
            - draw.outcrossing_assurance * assurance
            + draw.outcrossing_environment * environment
        )
        flower = draw.flower_intercept + draw.flower_environment * environment
        guide = (
            draw.guide_intercept
            - draw.guide_assurance * assurance
            + draw.guide_environment * environment
        )
    elif scenario is IslandScenario.BODY_SIZE_ONLY:
        assurance = _expit(draw.assurance_intercept + draw.assurance_environment * environment)
        outcrossing = _expit(
            draw.outcrossing_intercept
            - draw.outcrossing_assurance * assurance
            + draw.outcrossing_environment * environment
        )
        flower = (
            draw.flower_intercept
            + draw.flower_service * service_for_equations
            + draw.flower_environment * environment
        )
        guide = (
            draw.guide_intercept
            - draw.guide_assurance * assurance
            + draw.guide_environment * environment
        )
    else:
        assurance = _expit(
            draw.assurance_intercept
            - draw.assurance_service * service_for_equations
            + draw.assurance_environment * environment
        )
        outcrossing = _expit(
            draw.outcrossing_intercept
            + draw.outcrossing_service * service_for_equations
            - draw.outcrossing_assurance * assurance
            + draw.outcrossing_environment * environment
        )
        flower = (
            draw.flower_intercept
            + draw.flower_service * service_for_equations
            + draw.flower_environment * environment
        )
        guide = (
            draw.guide_intercept
            + draw.guide_service * service_for_equations
            - draw.guide_assurance * assurance
            + draw.guide_environment * environment
        )

    bagging = _expit(
        draw.bagging_intercept
        + draw.bagging_assurance * assurance
        + draw.bagging_environment * environment
    )
    return IslandPrediction(
        island_id=row.island_id,
        effective_outcross_service=service,
        assurance=assurance,
        expected_outcrossing=outcrossing,
        expected_bagging=bagging,
        expected_flower_length_mm=max(1.0, flower),
        latent_guide=guide,
    )


def draw_scenario_parameters(
    scenario: IslandScenario,
    environment_dimensions: int,
    rng: random.Random,
) -> ScenarioDraw:
    """Draw conservative scenario parameters from declared, shrinkage-like priors."""
    if environment_dimensions <= 0:
        raise ValueError("environment_dimensions must be positive")

    large = rng.uniform(0.55, 1.0)
    ardens = rng.uniform(0.35, 0.95)
    small = rng.uniform(0.05, 0.70)
    if scenario is IslandScenario.SMALL_BEE_SUBSTITUTION:
        small = max(small, ardens)
    elif scenario is IslandScenario.ARDENS_BRIDGE_LOSS:
        # The bridge hypothesis is only tested in the regime where ardens
        # is more effective than the small-bee composite.
        ardens = max(ardens, small + 0.05)
        ardens = min(0.98, ardens)

    return ScenarioDraw(
        large_bombus_effectiveness=large,
        ardens_effectiveness=ardens,
        small_bee_effectiveness=small,
        environment_weights=tuple(rng.gauss(0.0, 0.45) for _ in range(environment_dimensions)),
        outcrossing_intercept=rng.gauss(0.2, 1.2),
        outcrossing_service=abs(rng.gauss(1.6, 0.8)),
        outcrossing_assurance=abs(rng.gauss(1.0, 0.6)),
        outcrossing_environment=rng.gauss(0.0, 0.45),
        assurance_intercept=rng.gauss(-0.2, 1.2),
        assurance_service=abs(rng.gauss(1.5, 0.7)),
        assurance_environment=rng.gauss(0.0, 0.45),
        bagging_intercept=rng.gauss(-0.1, 1.3),
        bagging_assurance=abs(rng.gauss(1.7, 0.8)),
        bagging_environment=rng.gauss(0.0, 0.45),
        flower_intercept=rng.gauss(35.0, 9.0),
        flower_service=abs(rng.gauss(14.0, 7.0)),
        flower_environment=rng.gauss(0.0, 4.0),
        guide_intercept=rng.gauss(0.0, 1.5),
        guide_service=abs(rng.gauss(1.2, 0.8)),
        guide_assurance=abs(rng.gauss(0.8, 0.6)),
        guide_environment=rng.gauss(0.0, 0.5),
    )


def _score_draw(
    scenario: IslandScenario,
    evidence: Sequence[IslandEvidence],
    guide_constraints: Sequence[GuideOrderConstraint],
    draw: ScenarioDraw,
    standardized_environment: dict[str, tuple[float, ...]],
    scale: ObservationScale,
    included_channels: set[EvidenceChannel],
) -> _DrawResult:
    by_channel = {channel: 0.0 for channel in EvidenceChannel}
    predictions = tuple(
        _predict(scenario, row, draw, standardized_environment[row.island_id])
        for row in evidence
    )
    by_island = {prediction.island_id: prediction for prediction in predictions}

    for row, prediction in zip(evidence, predictions):
        if EvidenceChannel.OUTCROSSING in included_channels and row.outcrossing_mid is not None:
            by_channel[EvidenceChannel.OUTCROSSING] += _normal_logpdf(
                _logit(row.outcrossing_mid),
                _logit(prediction.expected_outcrossing),
                scale.outcrossing_logit_sd,
            )
        if EvidenceChannel.BAGGING in included_channels and row.bagged_capsule_fraction is not None:
            by_channel[EvidenceChannel.BAGGING] += _normal_logpdf(
                _logit(row.bagged_capsule_fraction),
                _logit(prediction.expected_bagging),
                scale.bagging_logit_sd,
            )
        if EvidenceChannel.FLOWER in included_channels and row.flower_length_mm is not None:
            by_channel[EvidenceChannel.FLOWER] += _normal_logpdf(
                row.flower_length_mm,
                prediction.expected_flower_length_mm,
                scale.flower_sd_mm,
            )

    if EvidenceChannel.GUIDE_ORDER in included_channels:
        for constraint in guide_constraints:
            left = by_island.get(constraint.left_island)
            right = by_island.get(constraint.right_island)
            if left is None or right is None:
                raise ValueError(
                    f"guide constraint {constraint.constraint_id!r} uses an island absent from evidence"
                )
            difference = left.latent_guide - right.latent_guide
            if constraint.relation == "lt":
                difference *= -1.0
            sd = math.sqrt(2.0 * scale.guide_latent_sd**2 + constraint.source_noise**2)
            probability = max(1e-12, _normal_cdf(difference / sd))
            by_channel[EvidenceChannel.GUIDE_ORDER] += math.log(probability)

    return _DrawResult(
        log_likelihood=sum(by_channel[channel] for channel in included_channels),
        by_channel=by_channel,
        predictions=predictions,
    )


def compare_scenarios(
    evidence: Sequence[IslandEvidence],
    guide_constraints: Sequence[GuideOrderConstraint] = (),
    *,
    draws: int = 10_000,
    seed: int = 20260702,
    scale: ObservationScale = ObservationScale(),
    included_channels: Iterable[EvidenceChannel] = tuple(EvidenceChannel),
) -> tuple[ScenarioSummary, ...]:
    """Integrate restricted scenarios over declared priors.

    The output ranks *compatibility under this model and its priors*.  It is not
    a reconstruction of history and should be accompanied by channel-ablation
    and prior-sensitivity analyses.
    """
    if draws <= 0:
        raise ValueError("draws must be positive")
    rows = tuple(evidence)
    if len(rows) < 2:
        raise ValueError("at least two evidence rows are required")
    if len({row.island_id for row in rows}) != len(rows):
        raise ValueError("island_id must be unique in an island-level comparison")
    selected = set(included_channels)
    if not selected:
        raise ValueError("at least one evidence channel is required")
    standardized = _standardize_environment(rows)
    env_dim = len(rows[0].environment)
    results: list[ScenarioSummary] = []
    for scenario_index, scenario in enumerate(IslandScenario):
        rng = random.Random(seed + scenario_index * 1009)
        draw_results: list[_DrawResult] = []
        for _ in range(draws):
            draw = draw_scenario_parameters(scenario, env_dim, rng)
            draw_results.append(
                _score_draw(
                    scenario,
                    rows,
                    guide_constraints,
                    draw,
                    standardized,
                    scale,
                    selected,
                )
            )
        log_likelihoods = [result.log_likelihood for result in draw_results]
        normalizer = _logsumexp(log_likelihoods)
        log_evidence = normalizer - math.log(draws)
        weights = [math.exp(value - normalizer) for value in log_likelihoods]
        prediction_by_island: dict[str, list[float]] = {}
        for row_index, row in enumerate(rows):
            # [service (nullable->0), assurance, outcrossing, bagging, flower, guide]
            prediction_by_island[row.island_id] = [0.0] * 6
            for weight, result in zip(weights, draw_results):
                prediction = result.predictions[row_index]
                service = prediction.effective_outcross_service
                if service is not None:
                    prediction_by_island[row.island_id][0] += weight * service
                prediction_by_island[row.island_id][1] += weight * prediction.assurance
                prediction_by_island[row.island_id][2] += weight * prediction.expected_outcrossing
                prediction_by_island[row.island_id][3] += weight * prediction.expected_bagging
                prediction_by_island[row.island_id][4] += weight * prediction.expected_flower_length_mm
                prediction_by_island[row.island_id][5] += weight * prediction.latent_guide
        expected_predictions = tuple(
            IslandPrediction(
                island_id=row.island_id,
                effective_outcross_service=(
                    None if scenario is IslandScenario.ENVIRONMENT_ONLY else prediction_by_island[row.island_id][0]
                ),
                assurance=prediction_by_island[row.island_id][1],
                expected_outcrossing=prediction_by_island[row.island_id][2],
                expected_bagging=prediction_by_island[row.island_id][3],
                expected_flower_length_mm=prediction_by_island[row.island_id][4],
                latent_guide=prediction_by_island[row.island_id][5],
            )
            for row in rows
        )

        def channel_mean(channel: EvidenceChannel) -> float:
            return mean(result.by_channel[channel] for result in draw_results)

        results.append(
            ScenarioSummary(
                scenario=scenario,
                draws=draws,
                log_marginal_compatibility=log_evidence,
                mean_log_likelihood=mean(log_likelihoods),
                mean_outcrossing_log_likelihood=channel_mean(EvidenceChannel.OUTCROSSING),
                mean_bagging_log_likelihood=channel_mean(EvidenceChannel.BAGGING),
                mean_flower_log_likelihood=channel_mean(EvidenceChannel.FLOWER),
                mean_guide_log_likelihood=channel_mean(EvidenceChannel.GUIDE_ORDER),
                # This is an importance-sampling diagnostic, not a scenario probability.
                posterior_best_draw_fraction=max(weights),
                expected_predictions=expected_predictions,
                included_channels=tuple(channel for channel in EvidenceChannel if channel in selected),
                boundary=(
                    "Prior-Monte-Carlo compatibility comparison only. It preserves "
                    "channel-specific observation models but does not establish "
                    "historical causation, pollinator effectiveness, or guide evolution."
                ),
            )
        )
    return tuple(sorted(results, key=lambda result: result.log_marginal_compatibility, reverse=True))


def load_island_evidence(
    path: Path,
    *,
    environment_columns: Sequence[str] = (
        "mean_temp_c",
        "annual_precip_mm",
        "precip_cv",
    ),
) -> tuple[IslandEvidence, ...]:
    """Load the source-locked island summary without merging missing values."""
    rows: list[IslandEvidence] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {
            "island_id",
            "bombus_diversus",
            "bombus_ardens",
            "halictid_pollinator",
            "megachilid_pollinator",
            "outcrossing_rate_min",
            "outcrossing_rate_max",
            "bagged_capsule_set_pct",
            "flower_length_mm",
            *environment_columns,
        }
        fieldnames = set(reader.fieldnames or ())
        missing = sorted(required - fieldnames)
        if missing:
            raise ValueError("input is missing required columns: " + ", ".join(missing))
        for line_number, raw in enumerate(reader, start=2):
            lo = _safe_float(raw["outcrossing_rate_min"])
            hi = _safe_float(raw["outcrossing_rate_max"])
            if (lo is None) != (hi is None):
                raise ValueError(f"row {line_number}: outcrossing range needs both bounds or neither")
            midpoint = None if lo is None else (lo + hi) / 2.0
            bagged_pct = _safe_float(raw["bagged_capsule_set_pct"])
            rows.append(
                IslandEvidence(
                    island_id=raw["island_id"].strip(),
                    bombus_diversus=float(raw["bombus_diversus"]),
                    bombus_ardens=float(raw["bombus_ardens"]),
                    halictid_pollinator=float(raw["halictid_pollinator"]),
                    megachilid_pollinator=float(raw["megachilid_pollinator"]),
                    outcrossing_mid=midpoint,
                    bagged_capsule_fraction=None if bagged_pct is None else bagged_pct / 100.0,
                    flower_length_mm=_safe_float(raw["flower_length_mm"]),
                    environment=tuple(_safe_float(raw[column]) for column in environment_columns),
                    source_row=line_number,
                )
            )
    return tuple(rows)


def load_guide_order_constraints(path: Path) -> tuple[GuideOrderConstraint, ...]:
    """Load human-reviewed ordinal comparisons from a provenance-preserving CSV."""
    constraints: list[GuideOrderConstraint] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {
            "constraint_id",
            "left_island",
            "right_island",
            "relation",
            "source_id",
            "source_noise",
            "notes",
        }
        fieldnames = set(reader.fieldnames or ())
        missing = sorted(required - fieldnames)
        if missing:
            raise ValueError("guide-constraint file is missing columns: " + ", ".join(missing))
        for line_number, raw in enumerate(reader, start=2):
            if not raw["constraint_id"].strip():
                continue
            noise = _safe_float(raw["source_noise"])
            constraints.append(
                GuideOrderConstraint(
                    constraint_id=raw["constraint_id"].strip(),
                    left_island=raw["left_island"].strip(),
                    right_island=raw["right_island"].strip(),
                    relation=raw["relation"].strip(),
                    source_id=raw["source_id"].strip(),
                    source_noise=1.0 if noise is None else noise,
                    notes=raw["notes"].strip(),
                )
            )
    return tuple(constraints)


def render_markdown(results: Sequence[ScenarioSummary]) -> str:
    """Render a concise reproducible report with scenario and channel boundaries."""
    if not results:
        raise ValueError("results cannot be empty")
    first = results[0]
    lines = [
        "# Island multichannel compatibility analysis",
        "",
        first.boundary,
        "",
        "## Scenario ranking",
        "",
        "| rank | scenario | log marginal compatibility | mean log likelihood | max importance weight |",
        "|---:|---|---:|---:|---:|",
    ]
    for rank, result in enumerate(results, start=1):
        lines.append(
            f"| {rank} | {result.scenario.value} | "
            f"{result.log_marginal_compatibility:.3f} | "
            f"{result.mean_log_likelihood:.3f} | "
            f"{result.posterior_best_draw_fraction:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Channel contribution: prior-draw mean log likelihood",
            "",
            "| scenario | outcrossing | bagging | flower | guide order |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for result in results:
        lines.append(
            f"| {result.scenario.value} | {result.mean_outcrossing_log_likelihood:.3f} | "
            f"{result.mean_bagging_log_likelihood:.3f} | "
            f"{result.mean_flower_log_likelihood:.3f} | "
            f"{result.mean_guide_log_likelihood:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Posterior-weighted expected island summaries",
            "",
            "These are model-implied summaries conditional on the selected scenario and priors; they are not observed states.",
        ]
    )
    for result in results:
        lines.extend(
            [
                "",
                f"### {result.scenario.value}",
                "",
                "| island | effective outcross service | assurance | outcrossing | bagging | flower length mm | latent guide |",
                "|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for prediction in result.expected_predictions:
            service = "NA" if prediction.effective_outcross_service is None else f"{prediction.effective_outcross_service:.3f}"
            lines.append(
                f"| {prediction.island_id} | {service} | {prediction.assurance:.3f} | "
                f"{prediction.expected_outcrossing:.3f} | {prediction.expected_bagging:.3f} | "
                f"{prediction.expected_flower_length_mm:.2f} | {prediction.latent_guide:.3f} |"
            )
    return "\n".join(lines) + "\n"
