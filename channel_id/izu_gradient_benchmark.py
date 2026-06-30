"""Virtual Izu-gradient benchmark for the full maternal observation pipeline.

This module does **not** claim to contain empirical climate, occurrence, or
pollinator data for the Izu Islands. It provides an explicit synthetic
landscape scaffold: ordered island labels, a declared north-to-south position,
and user-controlled gradients in floral guide contrast, pollinator service,
and establishment conditions.

The purpose is to ask a pre-data design question before field data exist:
can the combined camera and seed/paternity assays recover a declared guide
mechanism across a plausible island gradient, and what happens if that
background gradient is ignored during analysis?

A multi-island recovery requires a candidate mechanism to be compatible with
all observed sites. Its interval calibration must therefore be study-wide, not
only per site. This module Bonferroni-calibrates the two camera observations
and two seed/paternity observations across the declared set of virtual sites.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from random import Random
from typing import Sequence

from .camera_visit_handling import (
    CameraVisitHandlingDesign,
    CameraVisitHandlingObservation,
    simulate_camera_visit_handling_observation,
)
from .guide_scenarios import (
    ScenarioSettings,
    ScenarioSpec,
    ScenarioYear,
    assess_scenario_compatibility,
)
from .nectar_guide import NectarGuideTrait
from .seed_set_paternity import (
    SeedSetPaternityDesign,
    SeedSetPaternityObservation,
    simulate_seed_set_paternity_observation,
)


@dataclass(frozen=True)
class IzuGradientSite:
    """One ordered position in a synthetic Izu-archipelago scaffold.

    ``archipelago_position`` is an ordinal axis from 0 (northern end) to 1
    (southern end). It is deliberately not a geographic distance, climate
    variable, or assertion that the focal taxon occurs on this island.
    """

    label: str
    archipelago_position: float

    def __post_init__(self) -> None:
        if not self.label:
            raise ValueError("site label must be non-empty")
        if not 0.0 <= self.archipelago_position <= 1.0:
            raise ValueError("archipelago_position must lie in [0, 1]")


def default_izu_gradient_sites() -> tuple[IzuGradientSite, ...]:
    """Return an ordinal north-to-south island scaffold for sensitivity tests.

    The labels only provide a recognisable archipelago ordering. Users should
    subset, relabel, or replace the scaffold with confirmed focal-taxon sites
    before interpreting it as a field sampling frame.
    """

    return (
        IzuGradientSite("oshima", 0.00),
        IzuGradientSite("toshima", 0.14),
        IzuGradientSite("niijima", 0.28),
        IzuGradientSite("kozushima", 0.42),
        IzuGradientSite("miyake", 0.60),
        IzuGradientSite("mikura", 0.68),
        IzuGradientSite("hachijo", 0.86),
        IzuGradientSite("aogashima", 1.00),
    )


@dataclass(frozen=True)
class IzuGradientLandscape:
    """Declared trait and environmental endpoints along the synthetic gradient."""

    guide_contrast_north: float
    guide_contrast_south: float
    pollinator_service_north: float
    pollinator_service_south: float
    establishment_multiplier_north: float = 1.0
    establishment_multiplier_south: float = 1.0

    def __post_init__(self) -> None:
        for name, value in (
            ("guide_contrast_north", self.guide_contrast_north),
            ("guide_contrast_south", self.guide_contrast_south),
            ("pollinator_service_north", self.pollinator_service_north),
            ("pollinator_service_south", self.pollinator_service_south),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must lie in [0, 1]")
        for name, value in (
            ("establishment_multiplier_north", self.establishment_multiplier_north),
            ("establishment_multiplier_south", self.establishment_multiplier_south),
        ):
            if value < 0.0:
                raise ValueError(f"{name} must be non-negative")


class GradientAnalysisMode(str, Enum):
    """Whether candidate recovery uses or ignores the declared environment slope."""

    CALIBRATED = "calibrated"
    FLAT_ENVIRONMENT = "flat_environment"


@dataclass(frozen=True)
class IzuGradientSiteObservation:
    """Virtual camera and seed/paternity assays from one gradient position."""

    site: IzuGradientSite
    truth_settings: ScenarioSettings
    camera: CameraVisitHandlingObservation
    seed_set_paternity: SeedSetPaternityObservation

    @property
    def observations(self):
        """Return the four observed components used for compatibility checks."""

        return self.camera.observations + self.seed_set_paternity.observations


@dataclass(frozen=True)
class IzuGradientDataset:
    """One virtual multi-island dataset generated under a declared scenario truth."""

    truth: ScenarioSpec
    sites: tuple[IzuGradientSiteObservation, ...]


@dataclass(frozen=True)
class IzuGradientRecoverySummary:
    """Multi-island scenario-recovery performance over virtual replicates."""

    truth: ScenarioSpec
    analysis_mode: GradientAnalysisMode
    replicates: int
    truth_retained_rate: float
    unique_truth_recovery_rate: float
    empty_compatible_set_rate: float
    mean_compatible_scenarios: float


def _interpolate(north: float, south: float, position: float) -> float:
    return north + (south - north) * position


def study_calibrated_observation_designs(
    camera_design: CameraVisitHandlingDesign,
    seed_design: SeedSetPaternityDesign,
    site_count: int,
    study_familywise_confidence: float = 0.95,
) -> tuple[CameraVisitHandlingDesign, SeedSetPaternityDesign]:
    """Allocate one study-wide error budget across all site-level intervals.

    Each site contributes two camera intervals and two seed/paternity intervals.
    Both design classes already split their own familywise error over two
    component intervals. Setting each module's familywise confidence to

    ``1 - (1 - study_familywise_confidence) / (2 * site_count)``

    therefore gives every one of the ``4 * site_count`` intervals the same
    Bonferroni error budget. This avoids treating an eight-island conjunction
    of nominally local 95% intervals as though it still had 95% coverage.
    """

    if site_count < 1:
        raise ValueError("site_count must be positive")
    if not 0.0 < study_familywise_confidence < 1.0:
        raise ValueError("study_familywise_confidence must lie in (0, 1)")
    module_familywise_confidence = 1.0 - (
        (1.0 - study_familywise_confidence) / (2.0 * site_count)
    )
    return (
        replace(camera_design, familywise_confidence=module_familywise_confidence),
        replace(seed_design, familywise_confidence=module_familywise_confidence),
    )


def settings_for_izu_gradient_site(
    template: ScenarioSettings,
    site: IzuGradientSite,
    landscape: IzuGradientLandscape,
    analysis_mode: GradientAnalysisMode = GradientAnalysisMode.CALIBRATED,
) -> ScenarioSettings:
    """Build one site-specific scenario setting from a common template.

    Under ``FLAT_ENVIRONMENT``, candidates are evaluated at the mean declared
    pollinator service and establishment multiplier while trait contrast still
    changes across the archipelago. This intentionally tests an analysis that
    ignores the island background gradient.
    """

    guide_contrast = _interpolate(
        landscape.guide_contrast_north,
        landscape.guide_contrast_south,
        site.archipelago_position,
    )
    trait = NectarGuideTrait(
        guide_contrast=guide_contrast,
        display=template.trait.display,
        assurance=template.trait.assurance,
    )
    if analysis_mode is GradientAnalysisMode.CALIBRATED:
        pollinator_service = _interpolate(
            landscape.pollinator_service_north,
            landscape.pollinator_service_south,
            site.archipelago_position,
        )
        establishment_multiplier = _interpolate(
            landscape.establishment_multiplier_north,
            landscape.establishment_multiplier_south,
            site.archipelago_position,
        )
    else:
        pollinator_service = (landscape.pollinator_service_north + landscape.pollinator_service_south) / 2.0
        establishment_multiplier = (
            landscape.establishment_multiplier_north
            + landscape.establishment_multiplier_south
        ) / 2.0
    return replace(
        template,
        trait=trait,
        years=(
            ScenarioYear(
                label=site.label,
                pollinator_service=pollinator_service,
                establishment_multiplier=establishment_multiplier,
            ),
        ),
    )


def simulate_izu_gradient_dataset(
    truth: ScenarioSpec,
    template_settings: ScenarioSettings,
    landscape: IzuGradientLandscape,
    camera_design: CameraVisitHandlingDesign,
    seed_design: SeedSetPaternityDesign,
    sites: Sequence[IzuGradientSite] | None = None,
    seed: int = 0,
    study_familywise_confidence: float = 0.95,
) -> IzuGradientDataset:
    """Generate joint camera and seed/paternity data across a virtual island axis.

    Interval confidence is allocated over all declared site-level observation
    components, so a truth-retention rate can be interpreted at the study level.
    """

    selected_sites = tuple(default_izu_gradient_sites() if sites is None else sites)
    if not selected_sites:
        raise ValueError("at least one gradient site is required")
    if len({site.label for site in selected_sites}) != len(selected_sites):
        raise ValueError("gradient-site labels must be unique")
    calibrated_camera_design, calibrated_seed_design = study_calibrated_observation_designs(
        camera_design,
        seed_design,
        len(selected_sites),
        study_familywise_confidence,
    )

    rng = Random(seed)
    observed_sites: list[IzuGradientSiteObservation] = []
    for site in selected_sites:
        truth_settings = settings_for_izu_gradient_site(
            template_settings,
            site,
            landscape,
            GradientAnalysisMode.CALIBRATED,
        )
        camera = simulate_camera_visit_handling_observation(
            truth,
            truth_settings,
            site.label,
            calibrated_camera_design,
            rng,
        )
        seed_set_paternity = simulate_seed_set_paternity_observation(
            truth,
            truth_settings,
            site.label,
            calibrated_seed_design,
            rng,
        )
        observed_sites.append(
            IzuGradientSiteObservation(
                site=site,
                truth_settings=truth_settings,
                camera=camera,
                seed_set_paternity=seed_set_paternity,
            )
        )
    return IzuGradientDataset(truth=truth, sites=tuple(observed_sites))


def recover_izu_gradient_scenarios(
    candidates: Sequence[ScenarioSpec],
    dataset: IzuGradientDataset,
    template_settings: ScenarioSettings,
    landscape: IzuGradientLandscape,
    analysis_mode: GradientAnalysisMode = GradientAnalysisMode.CALIBRATED,
) -> tuple[ScenarioSpec, ...]:
    """Retain scenarios compatible with every site's joint virtual observations."""

    compatible: list[ScenarioSpec] = []
    for candidate in candidates:
        survives_all_sites = True
        for site_observation in dataset.sites:
            candidate_settings = settings_for_izu_gradient_site(
                template_settings,
                site_observation.site,
                landscape,
                analysis_mode,
            )
            report = assess_scenario_compatibility(
                candidate,
                candidate_settings,
                site_observation.observations,
            )
            if not report.compatible:
                survives_all_sites = False
                break
        if survives_all_sites:
            compatible.append(candidate)
    return tuple(compatible)


def benchmark_izu_gradient_recovery(
    truth: ScenarioSpec,
    candidates: Sequence[ScenarioSpec],
    template_settings: ScenarioSettings,
    landscape: IzuGradientLandscape,
    camera_design: CameraVisitHandlingDesign,
    seed_design: SeedSetPaternityDesign,
    sites: Sequence[IzuGradientSite] | None = None,
    analysis_mode: GradientAnalysisMode = GradientAnalysisMode.CALIBRATED,
    replicates: int = 100,
    seed: int = 0,
    study_familywise_confidence: float = 0.95,
) -> IzuGradientRecoverySummary:
    """Estimate multi-island recovery with calibrated or ignored gradients."""

    if replicates < 1:
        raise ValueError("replicates must be positive")
    if truth not in candidates:
        raise ValueError("truth must be included in candidates")
    selected_sites = tuple(default_izu_gradient_sites() if sites is None else sites)
    if not selected_sites:
        raise ValueError("at least one gradient site is required")

    rng = Random(seed)
    truth_retained = 0
    unique_truth = 0
    empty = 0
    compatible_total = 0
    for _ in range(replicates):
        dataset = simulate_izu_gradient_dataset(
            truth,
            template_settings,
            landscape,
            camera_design,
            seed_design,
            selected_sites,
            seed=rng.randrange(2**63),
            study_familywise_confidence=study_familywise_confidence,
        )
        scenarios = recover_izu_gradient_scenarios(
            candidates,
            dataset,
            template_settings,
            landscape,
            analysis_mode,
        )
        compatible_total += len(scenarios)
        if truth in scenarios:
            truth_retained += 1
        if scenarios == (truth,):
            unique_truth += 1
        if not scenarios:
            empty += 1

    return IzuGradientRecoverySummary(
        truth=truth,
        analysis_mode=analysis_mode,
        replicates=replicates,
        truth_retained_rate=truth_retained / replicates,
        unique_truth_recovery_rate=unique_truth / replicates,
        empty_compatible_set_rate=empty / replicates,
        mean_compatible_scenarios=compatible_total / replicates,
    )
