"""Scenario synthesis for the Inoue-series island evidence.

This module scores declared scenarios against source-transcribed outcrossing and
flower-length summaries. It is deliberately a constrained compatibility sweep,
not a historical reconstruction and not a causal estimator.

The model keeps three things separate:
- reported observations from the Inoue papers;
- unobserved public-data layers to be added later (occurrence, climate, images);
- sensitivity parameters for pollinator effectiveness and evolutionary history.
"""

from __future__ import annotations

import csv
import math
import random
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from statistics import mean
from typing import Iterable


class IslandScenario(str, Enum):
    ENVIRONMENT_ONLY = "environment_only"
    BODY_SIZE_ONLY = "body_size_only"
    SMALL_BEE_SUBSTITUTION = "small_bee_substitution"
    ARDENS_BRIDGE_LOSS = "ardens_bridge_loss"


class PollinatorRegime(str, Enum):
    MAINLAND_BOMBUS = "mainland_bombus"
    ARDENS_BRIDGE = "ardens_bridge"
    SMALL_BEE_NORTH = "small_bee_north"
    SMALL_BEE_SOUTH = "small_bee_south"


@dataclass(frozen=True)
class IslandOutcrossingObservation:
    population_id: str
    island: str
    outcrossing_t: float
    outcrossing_sd: float | None
    parenthetic_n: int | None
    regime: PollinatorRegime
    chain_position: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.outcrossing_t <= 1.0:
            raise ValueError("outcrossing_t must lie in [0, 1]")
        if self.outcrossing_sd is not None and self.outcrossing_sd < 0.0:
            raise ValueError("outcrossing_sd must be nonnegative")
        if self.parenthetic_n is not None and self.parenthetic_n <= 0:
            raise ValueError("parenthetic_n must be positive")
        if not 0.0 <= self.chain_position <= 1.0:
            raise ValueError("chain_position must lie in [0, 1]")


@dataclass(frozen=True)
class IslandFlowerObservation:
    island: str
    mean_length_mm: float
    sd_mm: float
    n: int
    regime: PollinatorRegime
    chain_position: float

    def __post_init__(self) -> None:
        if self.mean_length_mm <= 0.0:
            raise ValueError("mean_length_mm must be positive")
        if self.sd_mm < 0.0:
            raise ValueError("sd_mm must be nonnegative")
        if self.n <= 0:
            raise ValueError("n must be positive")
        if not 0.0 <= self.chain_position <= 1.0:
            raise ValueError("chain_position must lie in [0, 1]")


@dataclass(frozen=True)
class ScenarioParameters:
    """Sensitivity parameters on observed trait scales.

    These values are never inferred from occurrence records. The terms labelled
    `environment_*` represent a generic north-to-south/insularity gradient only
    until explicit climate and geography covariates are added.
    """

    mainland_t: float
    ardens_t: float
    north_small_bee_t: float
    south_small_bee_t: float
    mainland_flower_mm: float
    ardens_flower_mm: float
    small_bee_flower_mm: float
    environment_t_intercept: float
    environment_t_slope: float
    environment_flower_intercept: float
    environment_flower_slope: float
    model_sd_t: float = 0.12
    model_sd_flower_mm: float = 5.0

    def __post_init__(self) -> None:
        for name in (
            "mainland_t",
            "ardens_t",
            "north_small_bee_t",
            "south_small_bee_t",
            "environment_t_intercept",
        ):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must lie in [0, 1]")
        for name in (
            "mainland_flower_mm",
            "ardens_flower_mm",
            "small_bee_flower_mm",
            "environment_flower_intercept",
            "model_sd_t",
            "model_sd_flower_mm",
        ):
            if getattr(self, name) <= 0.0:
                raise ValueError(f"{name} must be positive")
        if self.environment_t_slope < 0.0 or self.environment_flower_slope < 0.0:
            raise ValueError("environment slopes must be nonnegative")


@dataclass(frozen=True)
class ScenarioFit:
    scenario: IslandScenario
    mean_log_score: float
    outcrossing_mean_log_score: float
    flower_mean_log_score: float
    compatibility_rate: float
    draws: int


def default_island_observations() -> tuple[tuple[IslandOutcrossingObservation, ...], tuple[IslandFlowerObservation, ...]]:
    """Return direct table transcriptions from Inoue (1990) and Inoue et al. (1995).

    Chain positions are an explicitly declared ordinal geographic scaffold used
    only for sensitivity sweeps: Oshima -> Toshima -> Niijima -> Kozu -> Miyake
    -> Hachijo. They are not distances, chronology, or climate values.
    """

    pos = {"Oshima": 0.00, "Toshima": 0.20, "Niijima": 0.35, "Kozu": 0.50, "Miyake": 0.70, "Hachijo": 1.00}
    observations = (
        IslandOutcrossingObservation("oshima_1", "Oshima", 0.624, 0.217, 7, PollinatorRegime.ARDENS_BRIDGE, pos["Oshima"]),
        IslandOutcrossingObservation("oshima_2", "Oshima", 0.758, 0.197, 8, PollinatorRegime.ARDENS_BRIDGE, pos["Oshima"]),
        IslandOutcrossingObservation("toshima", "Toshima", 0.535, 0.318, 5, PollinatorRegime.SMALL_BEE_NORTH, pos["Toshima"]),
        IslandOutcrossingObservation("niijima_1", "Niijima", 0.458, 0.292, 5, PollinatorRegime.SMALL_BEE_NORTH, pos["Niijima"]),
        IslandOutcrossingObservation("niijima_2", "Niijima", 0.566, 0.367, 6, PollinatorRegime.SMALL_BEE_NORTH, pos["Niijima"]),
        IslandOutcrossingObservation("kozu", "Kozu", 0.366, 0.200, 3, PollinatorRegime.SMALL_BEE_NORTH, pos["Kozu"]),
        IslandOutcrossingObservation("miyake", "Miyake", 0.157, 0.048, 3, PollinatorRegime.SMALL_BEE_SOUTH, pos["Miyake"]),
        IslandOutcrossingObservation("hachijo_1", "Hachijo", 0.169, None, 2, PollinatorRegime.SMALL_BEE_SOUTH, pos["Hachijo"]),
        IslandOutcrossingObservation("hachijo_2", "Hachijo", 0.236, None, 2, PollinatorRegime.SMALL_BEE_SOUTH, pos["Hachijo"]),
        IslandOutcrossingObservation("hachijo_3", "Hachijo", 0.251, None, 2, PollinatorRegime.SMALL_BEE_SOUTH, pos["Hachijo"]),
    )
    flowers = (
        IslandFlowerObservation("Oshima", 39.31, 4.75, 48, PollinatorRegime.ARDENS_BRIDGE, pos["Oshima"]),
        IslandFlowerObservation("Toshima", 35.27, 5.08, 77, PollinatorRegime.SMALL_BEE_NORTH, pos["Toshima"]),
        IslandFlowerObservation("Niijima", 28.62, 2.38, 2, PollinatorRegime.SMALL_BEE_NORTH, pos["Niijima"]),
        IslandFlowerObservation("Hachijo", 23.14, 3.16, 120, PollinatorRegime.SMALL_BEE_SOUTH, pos["Hachijo"]),
    )
    return observations, flowers


def _normal_log_density(value: float, expected: float, sd: float) -> float:
    variance = sd * sd
    return -0.5 * (math.log(2.0 * math.pi * variance) + ((value - expected) ** 2) / variance)


def _expected_outcrossing(scenario: IslandScenario, observation: IslandOutcrossingObservation, parameters: ScenarioParameters) -> float:
    if scenario is IslandScenario.ENVIRONMENT_ONLY:
        return max(0.001, min(0.999, parameters.environment_t_intercept - parameters.environment_t_slope * observation.chain_position))
    if scenario is IslandScenario.BODY_SIZE_ONLY:
        return max(0.001, min(0.999, parameters.environment_t_intercept - parameters.environment_t_slope * observation.chain_position))
    if scenario is IslandScenario.SMALL_BEE_SUBSTITUTION:
        if observation.regime is PollinatorRegime.ARDENS_BRIDGE:
            return parameters.ardens_t
        return parameters.north_small_bee_t
    if scenario is IslandScenario.ARDENS_BRIDGE_LOSS:
        if observation.regime is PollinatorRegime.ARDENS_BRIDGE:
            return parameters.ardens_t
        if observation.regime is PollinatorRegime.SMALL_BEE_NORTH:
            return parameters.north_small_bee_t
        return parameters.south_small_bee_t
    raise ValueError(scenario)


def _expected_flower_length(scenario: IslandScenario, observation: IslandFlowerObservation, parameters: ScenarioParameters) -> float:
    if scenario is IslandScenario.ENVIRONMENT_ONLY:
        return parameters.environment_flower_intercept - parameters.environment_flower_slope * observation.chain_position
    if scenario is IslandScenario.BODY_SIZE_ONLY:
        if observation.regime is PollinatorRegime.ARDENS_BRIDGE:
            return parameters.ardens_flower_mm
        return parameters.small_bee_flower_mm
    if scenario is IslandScenario.SMALL_BEE_SUBSTITUTION:
        if observation.regime is PollinatorRegime.ARDENS_BRIDGE:
            return parameters.ardens_flower_mm
        return parameters.small_bee_flower_mm
    if scenario is IslandScenario.ARDENS_BRIDGE_LOSS:
        if observation.regime is PollinatorRegime.ARDENS_BRIDGE:
            return parameters.ardens_flower_mm
        return parameters.small_bee_flower_mm
    raise ValueError(scenario)


def score_scenario(
    scenario: IslandScenario,
    parameters: ScenarioParameters,
    outcrossing: Iterable[IslandOutcrossingObservation],
    flowers: Iterable[IslandFlowerObservation],
) -> tuple[float, float, float]:
    """Return joint and channel-specific log scores under a declared scenario."""

    outcross_scores = []
    for row in outcrossing:
        reported_sd = row.outcrossing_sd if row.outcrossing_sd is not None else 0.25
        sd = math.sqrt(reported_sd * reported_sd + parameters.model_sd_t * parameters.model_sd_t)
        outcross_scores.append(_normal_log_density(row.outcrossing_t, _expected_outcrossing(scenario, row, parameters), sd))
    flower_scores = []
    for row in flowers:
        sem = row.sd_mm / math.sqrt(row.n)
        sd = math.sqrt(sem * sem + parameters.model_sd_flower_mm * parameters.model_sd_flower_mm)
        flower_scores.append(_normal_log_density(row.mean_length_mm, _expected_flower_length(scenario, row, parameters), sd))
    out_mean = mean(outcross_scores) if outcross_scores else 0.0
    flower_mean = mean(flower_scores) if flower_scores else 0.0
    return out_mean + flower_mean, out_mean, flower_mean


def draw_parameters(rng: random.Random) -> ScenarioParameters:
    """Draw broad declared sensitivity values; no draw is a field estimate."""

    return ScenarioParameters(
        mainland_t=rng.uniform(0.65, 0.90),
        ardens_t=rng.uniform(0.50, 0.85),
        north_small_bee_t=rng.uniform(0.25, 0.70),
        south_small_bee_t=rng.uniform(0.05, 0.45),
        mainland_flower_mm=rng.uniform(42.0, 60.0),
        ardens_flower_mm=rng.uniform(34.0, 45.0),
        small_bee_flower_mm=rng.uniform(18.0, 38.0),
        environment_t_intercept=rng.uniform(0.50, 0.90),
        environment_t_slope=rng.uniform(0.05, 0.70),
        environment_flower_intercept=rng.uniform(34.0, 55.0),
        environment_flower_slope=rng.uniform(5.0, 30.0),
        model_sd_t=rng.uniform(0.05, 0.25),
        model_sd_flower_mm=rng.uniform(2.0, 10.0),
    )


def sweep_scenarios(
    draws: int = 5000,
    seed: int = 20260630,
    compatibility_delta: float = 1.5,
) -> tuple[ScenarioFit, ...]:
    """Compare broad scenario compatibility over shared parameter draws.

    `compatibility_delta` is a model-scale tolerance relative to the best score
    in each draw. It is a sensitivity threshold, not a Bayes-factor cutoff.
    """

    if draws <= 0:
        raise ValueError("draws must be positive")
    if compatibility_delta < 0.0:
        raise ValueError("compatibility_delta must be nonnegative")
    outcrossing, flowers = default_island_observations()
    rng = random.Random(seed)
    scenario_scores = {scenario: [] for scenario in IslandScenario}
    channel_scores = {scenario: [[], []] for scenario in IslandScenario}
    compatible = {scenario: 0 for scenario in IslandScenario}
    for _ in range(draws):
        parameters = draw_parameters(rng)
        scores = {}
        for scenario in IslandScenario:
            joint, out_score, flower_score = score_scenario(scenario, parameters, outcrossing, flowers)
            scores[scenario] = joint
            scenario_scores[scenario].append(joint)
            channel_scores[scenario][0].append(out_score)
            channel_scores[scenario][1].append(flower_score)
        best = max(scores.values())
        for scenario, value in scores.items():
            if value >= best - compatibility_delta:
                compatible[scenario] += 1
    return tuple(
        ScenarioFit(
            scenario=scenario,
            mean_log_score=mean(scenario_scores[scenario]),
            outcrossing_mean_log_score=mean(channel_scores[scenario][0]),
            flower_mean_log_score=mean(channel_scores[scenario][1]),
            compatibility_rate=compatible[scenario] / draws,
            draws=draws,
        )
        for scenario in IslandScenario
    )


def render_scenario_sweep_markdown(results: Iterable[ScenarioFit]) -> str:
    rows = sorted(results, key=lambda row: row.mean_log_score, reverse=True)
    lines = [
        "# Source-only staged-island scenario sweep",
        "",
        "This report uses direct table transcriptions from the Inoue-series papers only: estimated outcrossing and common-garden flower-length summaries. It does not yet include occurrence, climate, image-derived spot traits, genomic structure, direct handling, or dated history.",
        "",
        "| scenario | mean joint log score | outcrossing channel | flower-length channel | compatibility rate | draws |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row.scenario.value} | {row.mean_log_score:.3f} | {row.outcrossing_mean_log_score:.3f} | {row.flower_mean_log_score:.3f} | {row.compatibility_rate:.3f} | {row.draws} |"
        )
    lines.extend(
        (
            "",
            "## Boundary",
            "",
            "A higher compatibility rate means that a declared scenario more often comes close to the best source-only score under broad shared sensitivity draws. It is not evidence that a historical event occurred, and it cannot establish the role of spots until island-resolved spot observations are added.",
        )
    )
    return "\n".join(lines) + "\n"


def load_outcrossing_csv(path: str | Path) -> tuple[IslandOutcrossingObservation, ...]:
    """Load the direct-transcription CSV without silently changing uncertainty."""

    positions = {"Oshima": 0.00, "Toshima": 0.20, "Niijima": 0.35, "Kozu": 0.50, "Miyake": 0.70, "Hachijo": 1.00}
    regime = {
        "Oshima": PollinatorRegime.ARDENS_BRIDGE,
        "Toshima": PollinatorRegime.SMALL_BEE_NORTH,
        "Niijima": PollinatorRegime.SMALL_BEE_NORTH,
        "Kozu": PollinatorRegime.SMALL_BEE_NORTH,
        "Miyake": PollinatorRegime.SMALL_BEE_SOUTH,
        "Hachijo": PollinatorRegime.SMALL_BEE_SOUTH,
    }
    rows = []
    with Path(path).open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            island = row["island"]
            rows.append(
                IslandOutcrossingObservation(
                    row["population_id"], island, float(row["outcrossing_t"]),
                    float(row["outcrossing_sd"]) if row["outcrossing_sd"] else None,
                    int(row["parenthetic_n"]) if row["parenthetic_n"] else None,
                    regime[island], positions[island],
                )
            )
    return tuple(rows)
