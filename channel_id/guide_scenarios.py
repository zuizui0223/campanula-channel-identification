"""Competing-scenario engine for nectar-guide evolution.

A pre-data design engine: compare restricted mechanism classes, generate
synthetic observations, and retain all compatible classes. It is not posterior
model selection or historical causal inference.

Named scenarios remain available for simple workflows.  ``GuideRoutes`` adds a
small composable layer because a biological process such as visit attraction
and delayed selfing can operate at the same time; forcing those routes to be
mutually exclusive can reject the true mechanism before field data are even
considered.
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
from .nectar_guide import (
    NectarGuideParameters,
    NectarGuideRegime,
    NectarGuideTrait,
    simulate_nectar_guide_life_history,
)


class GuideScenario(str, Enum):
    """Convenient named route restrictions retained for backwards compatibility."""

    NULL = "null"
    VISIT_ATTRACTION = "visit_attraction"
    HANDLING = "handling"
    COST = "cost"
    PATERNAL = "paternal"
    ASSURANCE = "assurance"
    SPATIAL = "spatial"
    MIXED = "mixed"


@dataclass(frozen=True)
class GuideRoutes:
    """An explicit combination of biologically declared mechanism routes.

    The first Izu design should usually compare a small collection of these
    routes rather than every possible combination.  The point is to allow
    biologically plausible combinations (for example visit attraction plus
    delayed-selfing assurance) without automatically activating paternal,
    temporal, or spatial claims for which no intermediate data exist.
    """

    label: str = "custom"
    visit_attraction: bool = False
    handling: bool = False
    guide_cost: bool = False
    assurance: bool = False
    paternal: bool = False
    spatial: bool = False

    def __post_init__(self) -> None:
        if not self.label:
            raise ValueError("route label must be non-empty")


ScenarioSpec = GuideScenario | GuideRoutes


def routes_for(scenario: ScenarioSpec) -> GuideRoutes:
    """Return the active routes for a named scenario or custom route combination."""

    if isinstance(scenario, GuideRoutes):
        return scenario
    if scenario is GuideScenario.NULL:
        return GuideRoutes("null")
    if scenario is GuideScenario.VISIT_ATTRACTION:
        return GuideRoutes("visit_attraction", visit_attraction=True)
    if scenario is GuideScenario.HANDLING:
        return GuideRoutes("handling", handling=True)
    if scenario is GuideScenario.COST:
        return GuideRoutes("cost", guide_cost=True)
    if scenario is GuideScenario.PATERNAL:
        return GuideRoutes("paternal", paternal=True)
    if scenario is GuideScenario.ASSURANCE:
        return GuideRoutes("assurance", assurance=True)
    if scenario is GuideScenario.SPATIAL:
        return GuideRoutes("spatial", spatial=True)
    if scenario is GuideScenario.MIXED:
        return GuideRoutes(
            "mixed",
            visit_attraction=True,
            handling=True,
            guide_cost=True,
            assurance=True,
            paternal=True,
            spatial=True,
        )
    raise ValueError(f"unknown scenario {scenario!r}")


def core_maternal_scenarios() -> tuple[ScenarioSpec, ...]:
    """Return a small, explicitly declared starting set for an Izu campaign.

    It includes both single routes and the two compound alternatives most likely
    to be confused with them in a one-season maternal data set.  Paternal and
    spatial routes remain off until their specific intermediate observations are
    available.
    """

    return (
        GuideScenario.NULL,
        GuideScenario.VISIT_ATTRACTION,
        GuideScenario.HANDLING,
        GuideScenario.COST,
        GuideScenario.ASSURANCE,
        GuideRoutes("visit_assurance", visit_attraction=True, assurance=True),
        GuideRoutes("handling_assurance", handling=True, assurance=True),
        GuideRoutes("visit_cost", visit_attraction=True, guide_cost=True),
        GuideRoutes("handling_cost", handling=True, guide_cost=True),
        GuideRoutes("visit_handling", visit_attraction=True, handling=True),
        GuideRoutes(
            "visit_handling_assurance",
            visit_attraction=True,
            handling=True,
            assurance=True,
        ),
    )


class ScenarioMetric(str, Enum):
    EXPECTED_VISITS = "expected_visits"
    LEGITIMATE_CONTACT_FRACTION = "legitimate_contact_fraction"
    EXPECTED_LEGITIMATE_CONTACTS = "expected_legitimate_contacts"
    STIGMA_POLLEN_DEPOSITION = "stigma_pollen_deposition"
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
    """Scenario quantities for one year and one maternal-flower scale.

    ``stigma_pollen_deposition`` is a model-scale effective deposition pressure;
    it is not automatically equivalent to a raw count of pollen grains in field
    assays.
    """

    label: str
    expected_visits: float
    legitimate_contact_fraction: float
    expected_legitimate_contacts: float
    stigma_pollen_deposition: float
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
    scenario: ScenarioSpec
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
    scenario: ScenarioSpec
    compatible: bool
    failures: tuple[str, ...]
    result: ScenarioResult


def _maternal_parameters(routes: GuideRoutes, p: NectarGuideParameters) -> NectarGuideParameters:
    """Switch only undeclared guide routes off, retaining all declared pathways."""

    return replace(
        p,
        guide_visit_gain=p.guide_visit_gain if routes.visit_attraction else 0.0,
        guide_handling_gain=p.guide_handling_gain if routes.handling else 0.0,
        guide_cost=p.guide_cost if routes.guide_cost else 0.0,
    )


def _trait(routes: GuideRoutes, trait: NectarGuideTrait) -> NectarGuideTrait:
    return trait if routes.assurance else replace(trait, assurance=0.0)


def _paternal(
    routes: GuideRoutes,
    visits: float,
    trait: NectarGuideTrait,
    p: PaternalGuideParameters,
) -> float:
    if not routes.paternal:
        return 0.0
    export = visits * (
        p.baseline_pollen_export
        + p.display_export_gain * trait.display
        + p.guide_export_gain * trait.guide_contrast
    )
    siring = 1.0 - exp(
        -export * (p.baseline_siring_success + p.guide_siring_gain * trait.guide_contrast)
    )
    return p.male_weight * export * siring


def _female(
    routes: GuideRoutes,
    outcross: float,
    selfed: float,
    settings: ScenarioSettings,
) -> float:
    recruits = apply_post_seed_survival(outcross, selfed, settings.post_seed_survival).total_recruits
    if not routes.spatial:
        return recruits
    if not settings.spatial_patches:
        raise ValueError("spatial routes require spatial patches and dispersal")
    return distribute_seeds_to_patches(
        recruits,
        settings.spatial_patches,
        settings.spatial_dispersal,
    ).total_retained_recruits


def simulate_guide_scenario(scenario: ScenarioSpec, settings: ScenarioSettings) -> ScenarioResult:
    """Run one restricted named scenario or custom route combination across years."""

    routes = routes_for(scenario)
    maternal_parameters = _maternal_parameters(routes, settings.maternal_parameters)
    trait = _trait(routes, settings.trait)
    by_year: dict[str, ScenarioYearResult] = {}
    temporal: list[YearPerformance] = []
    for year in settings.years:
        maternal = simulate_nectar_guide_life_history(
            trait,
            NectarGuideRegime(year.pollinator_service, year.establishment_multiplier),
            maternal_parameters,
        )
        female = _female(
            routes,
            maternal.outcross_viable_seeds,
            maternal.selfed_viable_seeds,
            settings,
        )
        paternal = _paternal(routes, maternal.expected_visits, trait, settings.paternal_parameters)
        total = female + paternal
        by_year[year.label] = ScenarioYearResult(
            year.label,
            maternal.expected_visits,
            maternal.legitimate_contact_fraction,
            maternal.expected_legitimate_contacts,
            maternal.stigma_pollen_deposition,
            maternal.outcross_viable_seeds,
            maternal.selfed_viable_seeds,
            female,
            paternal,
            total,
        )
        temporal.append(YearPerformance(year.label, total, year.probability))
    summary = summarise_temporal_fitness(temporal)
    return ScenarioResult(
        scenario,
        by_year,
        summary.arithmetic_mean,
        summary.geometric_mean,
    )


def assess_scenario_compatibility(
    scenario: ScenarioSpec,
    settings: ScenarioSettings,
    observations: Sequence[ScenarioObservation],
) -> ScenarioCompatibility:
    result = simulate_guide_scenario(scenario, settings)
    failures: list[str] = []
    for obs in observations:
        value = result.metric(obs.metric, obs.year_label)
        if not obs.contains(value):
            failures.append(
                f"{obs.year_label or 'summary'}:{obs.metric.value}={value:.6g} outside "
                f"[{obs.lower:.6g}, {obs.upper:.6g}]"
            )
    return ScenarioCompatibility(scenario, not failures, tuple(failures), result)


def recover_compatible_scenarios(
    scenarios: Sequence[ScenarioSpec],
    settings: ScenarioSettings,
    observations: Sequence[ScenarioObservation],
) -> tuple[ScenarioCompatibility, ...]:
    """Retain every named or composable route specification compatible with data."""

    return tuple(
        report
        for scenario in scenarios
        if (report := assess_scenario_compatibility(scenario, settings, observations)).compatible
    )
