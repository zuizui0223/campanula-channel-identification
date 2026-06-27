"""Competing-scenario engine for nectar-guide evolution.

A pre-data design engine: compare restricted mechanism classes, generate
synthetic observations, and retain all compatible classes. It is not posterior
model selection or historical causal inference.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from math import exp
from typing import Mapping, Sequence

from .guide_inbreeding import PostSeedSurvival, apply_post_seed_survival
from .guide_paternal import PaternalGuideParameters
from .guide_spatial import Patch, distribute_seeds_to_patches
from .guide_temporal import YearPerformance, summarise_temporal_fitness
from .nectar_guide import NectarGuideParameters, NectarGuideRegime, NectarGuideTrait, simulate_nectar_guide_life_history


class GuideScenario(str, Enum):
    NULL = "null"
    VISIT_ATTRACTION = "visit_attraction"
    HANDLING = "handling"
    PATERNAL = "paternal"
    ASSURANCE = "assurance"
    SPATIAL = "spatial"
    MIXED = "mixed"


class ScenarioMetric(str, Enum):
    EXPECTED_VISITS = "expected_visits"
    OUTCROSS_VIABLE_SEEDS = "outcross_viable_seeds"
    SELFED_VIABLE_SEEDS = "selfed_viable_seeds"
    FEMALE_RECRUITS = "female_recruits"
    PATERNAL_CONTRIBUTION = "paternal_contribution"
    TOTAL_CONTRIBUTION = "total_contribution"
    GEOMETRIC_MEAN_CONTRIBUTION = "geometric_mean_contribution"


@dataclass(frozen=True)
class ScenarioYear:
    label: str
    pollinator_service: float
    establishment_multiplier: float = 1.0
    probability: float = 1.0
    def __post_init__(self) -> None:
        if not self.label:
            raise ValueError("year label must be non-empty")
        if not 0.0 <= self.pollinator_service <= 1.0:
            raise ValueError("pollinator_service must lie in [0, 1]")
        if self.establishment_multiplier < 0.0 or self.probability <= 0.0:
            raise ValueError("establishment_multiplier must be non-negative and probability positive")


@dataclass(frozen=True)
class ScenarioSettings:
    trait: NectarGuideTrait
    maternal_parameters: NectarGuideParameters
    paternal_parameters: PaternalGuideParameters
    post_seed_survival: PostSeedSurvival
    years: tuple[ScenarioYear, ...]
    spatial_patches: tuple[Patch, ...] = ()
    spatial_dispersal: tuple[float, ...] = ()
    def __post_init__(self) -> None:
        if not self.years:
            raise ValueError("at least one year is required")
        if bool(self.spatial_patches) != bool(self.spatial_dispersal):
            raise ValueError("spatial patches and dispersal must be supplied together")
        if self.spatial_patches and len(self.spatial_patches) != len(self.spatial_dispersal):
            raise ValueError("spatial patches and dispersal must align")


@dataclass(frozen=True)
class ScenarioYearResult:
    label: str
    expected_visits: float
    outcross_viable_seeds: float
    selfed_viable_seeds: float
    female_recruits: float
    paternal_contribution: float
    total_contribution: float
    def metric(self, metric: ScenarioMetric) -> float:
        if metric is ScenarioMetric.GEOMETRIC_MEAN_CONTRIBUTION:
            raise ValueError("geometric mean is summary-level")
        return getattr(self, metric.value)


@dataclass(frozen=True)
class ScenarioResult:
    scenario: GuideScenario
    by_year: Mapping[str, ScenarioYearResult]
    arithmetic_mean_contribution: float
    geometric_mean_contribution: float
    def metric(self, metric: ScenarioMetric, year_label: str | None = None) -> float:
        if metric is ScenarioMetric.GEOMETRIC_MEAN_CONTRIBUTION:
            return self.geometric_mean_contribution
        if year_label is None:
            raise ValueError("year_label is required for year-level metrics")
        try:
            return self.by_year[year_label].metric(metric)
        except KeyError as error:
            raise ValueError(f"unknown year label {year_label!r}") from error


@dataclass(frozen=True)
class ScenarioObservation:
    metric: ScenarioMetric
    lower: float
    upper: float
    year_label: str | None = None
    def __post_init__(self) -> None:
        if self.lower < 0.0 or self.upper < self.lower:
            raise ValueError("observation bounds must be non-negative and ordered")
        if self.metric is not ScenarioMetric.GEOMETRIC_MEAN_CONTRIBUTION and not self.year_label:
            raise ValueError("year_label is required for year-level metrics")
    def contains(self, value: float) -> bool:
        return self.lower <= value <= self.upper


@dataclass(frozen=True)
class ScenarioCompatibility:
    scenario: GuideScenario
    compatible: bool
    failures: tuple[str, ...]
    result: ScenarioResult


def _maternal_parameters(scenario: GuideScenario, p: NectarGuideParameters) -> NectarGuideParameters:
    if scenario is GuideScenario.NULL:
        return replace(p, guide_visit_gain=0.0, guide_handling_gain=0.0, guide_cost=0.0)
    if scenario is GuideScenario.VISIT_ATTRACTION:
        return replace(p, guide_handling_gain=0.0, guide_cost=0.0)
    if scenario is GuideScenario.HANDLING:
        return replace(p, guide_visit_gain=0.0, guide_cost=0.0)
    if scenario in {GuideScenario.PATERNAL, GuideScenario.ASSURANCE, GuideScenario.SPATIAL}:
        return replace(p, guide_visit_gain=0.0, guide_handling_gain=0.0, guide_cost=0.0)
    return p


def _trait(scenario: GuideScenario, trait: NectarGuideTrait) -> NectarGuideTrait:
    return trait if scenario in {GuideScenario.ASSURANCE, GuideScenario.MIXED} else replace(trait, assurance=0.0)


def _paternal(scenario: GuideScenario, visits: float, trait: NectarGuideTrait, p: PaternalGuideParameters) -> float:
    if scenario not in {GuideScenario.PATERNAL, GuideScenario.MIXED}:
        return 0.0
    export = visits * (p.baseline_pollen_export + p.display_export_gain * trait.display + p.guide_export_gain * trait.guide_contrast)
    siring = 1.0 - exp(-export * (p.baseline_siring_success + p.guide_siring_gain * trait.guide_contrast))
    return p.male_weight * export * siring


def _female(scenario: GuideScenario, outcross: float, selfed: float, settings: ScenarioSettings) -> float:
    recruits = apply_post_seed_survival(outcross, selfed, settings.post_seed_survival).total_recruits
    if scenario not in {GuideScenario.SPATIAL, GuideScenario.MIXED}:
        return recruits
    if not settings.spatial_patches:
        raise ValueError("spatial and mixed scenarios require spatial patches and dispersal")
    return distribute_seeds_to_patches(recruits, settings.spatial_patches, settings.spatial_dispersal).total_retained_recruits


def simulate_guide_scenario(scenario: GuideScenario, settings: ScenarioSettings) -> ScenarioResult:
    """Run one restricted scenario across declared temporal states."""
    p = _maternal_parameters(scenario, settings.maternal_parameters)
    trait = _trait(scenario, settings.trait)
    by_year: dict[str, ScenarioYearResult] = {}
    temporal: list[YearPerformance] = []
    for year in settings.years:
        maternal = simulate_nectar_guide_life_history(trait, NectarGuideRegime(year.pollinator_service, year.establishment_multiplier), p)
        female = _female(scenario, maternal.outcross_viable_seeds, maternal.selfed_viable_seeds, settings)
        paternal = _paternal(scenario, maternal.expected_visits, trait, settings.paternal_parameters)
        total = female + paternal
        by_year[year.label] = ScenarioYearResult(year.label, maternal.expected_visits, maternal.outcross_viable_seeds, maternal.selfed_viable_seeds, female, paternal, total)
        temporal.append(YearPerformance(year.label, total, year.probability))
    summary = summarise_temporal_fitness(temporal)
    return ScenarioResult(scenario, by_year, summary.arithmetic_mean, summary.geometric_mean)


def assess_scenario_compatibility(scenario: GuideScenario, settings: ScenarioSettings, observations: Sequence[ScenarioObservation]) -> ScenarioCompatibility:
    result = simulate_guide_scenario(scenario, settings)
    failures: list[str] = []
    for obs in observations:
        value = result.metric(obs.metric, obs.year_label)
        if not obs.contains(value):
            failures.append(f"{obs.year_label or 'summary'}:{obs.metric.value}={value:.6g} outside [{obs.lower:.6g}, {obs.upper:.6g}]")
    return ScenarioCompatibility(scenario, not failures, tuple(failures), result)


def recover_compatible_scenarios(scenarios: Sequence[GuideScenario], settings: ScenarioSettings, observations: Sequence[ScenarioObservation]) -> tuple[ScenarioCompatibility, ...]:
    return tuple(report for scenario in scenarios if (report := assess_scenario_compatibility(scenario, settings, observations)).compatible)
