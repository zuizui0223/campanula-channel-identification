"""Bridge empirical spot-trait evidence to declared virtual-gradient scenarios.

This module is deliberately an *anchor layer*, not an empirical mechanism
estimator.  It keeps four evidence types separate:

* population-level spot-trait means define an ordinal trait axis;
* a P_ST--F_ST comparison records whether trait divergence is selection-compatible;
* selfed versus outcrossed fitness records an inbreeding-depression estimate;
* pollinator-guild detection and effort records availability context.

Only the trait axis and a post-seed inbreeding estimate can be mapped directly
into the existing virtual gradient engine.  Guild presence/absence does not
estimate visit rate, and P_ST--F_ST does not identify a visit, handling, or
assurance route.  Those remain explicitly declared scenario assumptions.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable, Sequence

from .guide_inbreeding import PostSeedSurvival
from .guide_scenarios import ScenarioSettings
from .izu_gradient_benchmark import IzuGradientLandscape, IzuGradientSite


POST_SEED_CENSUS_INTERVAL = "post_seed"
TOTAL_LIFETIME_CENSUS_INTERVAL = "total_lifetime"
CENSUS_INTERVALS = (POST_SEED_CENSUS_INTERVAL, TOTAL_LIFETIME_CENSUS_INTERVAL)


@dataclass(frozen=True)
class PopulationTraitAnchor:
    """Population-level observed spot trait used only to order the virtual axis."""

    population_id: str
    spot_trait_mean: float
    trait_n: int
    spot_trait_sd: float | None = None

    def __post_init__(self) -> None:
        if not self.population_id:
            raise ValueError("population_id must be non-empty")
        if self.trait_n < 1:
            raise ValueError("trait_n must be positive")
        if self.spot_trait_sd is not None and self.spot_trait_sd < 0.0:
            raise ValueError("spot_trait_sd must be non-negative when supplied")


@dataclass(frozen=True)
class PstFstAnchor:
    """A reported P_ST--F_ST comparison, retained as evidence metadata.

    ``critical_c_over_h2`` is optional because different P_ST sensitivity
    workflows report this boundary differently.  It is reported, never used as
    a mechanism effect size.
    """

    trait_name: str
    pst: float
    fst: float
    critical_c_over_h2: float | None = None

    def __post_init__(self) -> None:
        if not self.trait_name:
            raise ValueError("trait_name must be non-empty")
        for name, value in (("pst", self.pst), ("fst", self.fst)):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must lie in [0, 1]")
        if self.critical_c_over_h2 is not None and self.critical_c_over_h2 <= 0.0:
            raise ValueError("critical_c_over_h2 must be positive when supplied")

    @property
    def selection_compatible(self) -> bool:
        """Whether the reported point comparison has P_ST above F_ST.

        This does not prove selection and does not replace the underlying
        heritability / c-over-h-squared sensitivity analysis.
        """

        return self.pst > self.fst


@dataclass(frozen=True)
class InbreedingFitnessAnchor:
    """Observed selfed and outcrossed fitness on a declared common census scale."""

    census_interval: str
    selfed_mean_fitness: float
    outcrossed_mean_fitness: float

    def __post_init__(self) -> None:
        if self.census_interval not in CENSUS_INTERVALS:
            raise ValueError(
                "census_interval must be one of " + ", ".join(CENSUS_INTERVALS)
            )
        if self.selfed_mean_fitness < 0.0 or self.outcrossed_mean_fitness <= 0.0:
            raise ValueError("fitness values must be non-negative and outcrossed fitness positive")

    @property
    def relative_selfed_fitness(self) -> float:
        return self.selfed_mean_fitness / self.outcrossed_mean_fitness

    @property
    def inbreeding_depression(self) -> float:
        """Return 1 - selfed/outcrossed fitness on the declared census interval."""

        return 1.0 - self.relative_selfed_fitness

    @property
    def maps_to_post_seed_survival(self) -> bool:
        """Whether this estimate can directly parameterise the existing late-ID layer."""

        return (
            self.census_interval == POST_SEED_CENSUS_INTERVAL
            and 0.0 <= self.inbreeding_depression <= 1.0
        )


@dataclass(frozen=True)
class PollinatorAvailabilityAnchor:
    """Observed guild detection with explicit observation effort.

    ``detected=False`` means not detected during the declared effort.  It must
    never be silently converted into ecological absence or a numerical visit
    rate.
    """

    population_id: str
    guild: str
    detected: bool
    effort_minutes: float

    def __post_init__(self) -> None:
        if not self.population_id or not self.guild:
            raise ValueError("population_id and guild must be non-empty")
        if self.effort_minutes < 0.0:
            raise ValueError("effort_minutes must be non-negative")


@dataclass(frozen=True)
class EmpiricalAnchorBundle:
    """Observed summaries used to constrain, but not identify, virtual scenarios."""

    population_traits: tuple[PopulationTraitAnchor, ...]
    pst_fst: PstFstAnchor
    inbreeding: InbreedingFitnessAnchor
    pollinator_availability: tuple[PollinatorAvailabilityAnchor, ...]

    def __post_init__(self) -> None:
        if len(self.population_traits) < 2:
            raise ValueError("at least two population trait summaries are required")
        population_ids = [record.population_id for record in self.population_traits]
        if len(set(population_ids)) != len(population_ids):
            raise ValueError("population trait IDs must be unique")
        known = set(population_ids)
        unknown = sorted(
            {record.population_id for record in self.pollinator_availability} - known
        )
        if unknown:
            raise ValueError(
                "pollinator records must refer to population traits; unknown="
                + ", ".join(unknown)
            )


@dataclass(frozen=True)
class EmpiricalGradientAssumptions:
    """Declared non-empirical mappings used to generate scenario landscapes.

    The observed trait axis is min--max scaled to ``trait_contrast_min`` and
    ``trait_contrast_max``.  The numerical pollinator services are sensitivity
    assumptions.  Presence/absence records do not estimate them.
    """

    focal_guild: str
    trait_contrast_min: float = 0.0
    trait_contrast_max: float = 1.0
    pollinator_service_low: float = 0.25
    pollinator_service_high: float = 0.75
    establishment_multiplier: float = 1.0

    def __post_init__(self) -> None:
        if not self.focal_guild:
            raise ValueError("focal_guild must be non-empty")
        for name, value in (
            ("trait_contrast_min", self.trait_contrast_min),
            ("trait_contrast_max", self.trait_contrast_max),
            ("pollinator_service_low", self.pollinator_service_low),
            ("pollinator_service_high", self.pollinator_service_high),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must lie in [0, 1]")
        if self.trait_contrast_max <= self.trait_contrast_min:
            raise ValueError("trait_contrast_max must exceed trait_contrast_min")
        if self.pollinator_service_high < self.pollinator_service_low:
            raise ValueError("pollinator_service_high must not be below pollinator_service_low")
        if self.establishment_multiplier < 0.0:
            raise ValueError("establishment_multiplier must be non-negative")


@dataclass(frozen=True)
class AnchoredGradientCase:
    """One declared service-gradient alternative over an empirical trait axis."""

    label: str
    interpretation: str
    sites: tuple[IzuGradientSite, ...]
    landscape: IzuGradientLandscape


def trait_gradient_sites(
    population_traits: Sequence[PopulationTraitAnchor],
) -> tuple[IzuGradientSite, ...]:
    """Create an ordinal site axis from observed population mean spot trait values.

    Site position is a min--max transformed observed trait mean, not geographic
    distance, habitat, or inferred pollinator abundance.  Tied trait values are
    retained as tied positions; all-equal traits cannot define a gradient.
    """

    records = tuple(population_traits)
    if len(records) < 2:
        raise ValueError("at least two population traits are required")
    if len({record.population_id for record in records}) != len(records):
        raise ValueError("population IDs must be unique")
    values = [record.spot_trait_mean for record in records]
    lower, upper = min(values), max(values)
    if lower == upper:
        raise ValueError("observed spot trait means must not all be equal")
    sites = tuple(
        IzuGradientSite(
            record.population_id,
            (record.spot_trait_mean - lower) / (upper - lower),
        )
        for record in records
    )
    return tuple(sorted(sites, key=lambda site: (site.archipelago_position, site.label)))


def apply_inbreeding_anchor(
    template_settings: ScenarioSettings,
    inbreeding: InbreedingFitnessAnchor,
) -> ScenarioSettings:
    """Map an explicitly post-seed inbreeding estimate into scenario settings.

    A seed-set or total-lifetime estimate is not automatically a late survival
    multiplier, so this function refuses that mapping.  The existing outcrossed
    survival in ``template_settings`` is preserved.
    """

    if not inbreeding.maps_to_post_seed_survival:
        raise ValueError(
            "only a non-negative post_seed inbreeding-depression estimate can map "
            "to PostSeedSurvival"
        )
    current = template_settings.post_seed_survival
    return replace(
        template_settings,
        post_seed_survival=PostSeedSurvival(
            outcrossed_survival=current.outcrossed_survival,
            late_inbreeding_depression=inbreeding.inbreeding_depression,
        ),
    )


def focal_guild_availability(
    bundle: EmpiricalAnchorBundle,
    focal_guild: str,
) -> tuple[tuple[str, str, float], ...]:
    """Summarise availability evidence without turning it into a visit-rate estimate.

    Returns one row per trait population as ``(population_id, status, effort)``.
    Status is ``detected``, ``not_detected_with_effort``, or ``unobserved``.
    """

    if not focal_guild:
        raise ValueError("focal_guild must be non-empty")
    output: list[tuple[str, str, float]] = []
    for trait in bundle.population_traits:
        records = tuple(
            record
            for record in bundle.pollinator_availability
            if record.population_id == trait.population_id and record.guild == focal_guild
        )
        total_effort = sum(record.effort_minutes for record in records)
        if any(record.detected for record in records):
            status = "detected"
        elif total_effort > 0.0:
            status = "not_detected_with_effort"
        else:
            status = "unobserved"
        output.append((trait.population_id, status, total_effort))
    return tuple(output)


def empirical_gradient_cases(
    bundle: EmpiricalAnchorBundle,
    assumptions: EmpiricalGradientAssumptions,
) -> tuple[AnchoredGradientCase, ...]:
    """Return bracketing pollinator-service scenarios over the observed spot axis.

    The three cases deliberately avoid inferring a numerical pollinator-service
    slope from guild presence/absence.  They retain flat, trait-aligned, and
    trait-opposed service alternatives so the interpretation does not depend on
    one untested mapping from availability to visitation.
    """

    sites = trait_gradient_sites(bundle.population_traits)
    common = dict(
        guide_contrast_north=assumptions.trait_contrast_min,
        guide_contrast_south=assumptions.trait_contrast_max,
        establishment_multiplier_north=assumptions.establishment_multiplier,
        establishment_multiplier_south=assumptions.establishment_multiplier,
    )
    midpoint = (
        assumptions.pollinator_service_low + assumptions.pollinator_service_high
    ) / 2.0
    return (
        AnchoredGradientCase(
            label="flat_pollinator_service",
            interpretation=(
                "Observed spot-trait differentiation is retained while pollinator "
                "service is held constant; guild availability does not define a "
                "numerical visit gradient."
            ),
            sites=sites,
            landscape=IzuGradientLandscape(
                **common,
                pollinator_service_north=midpoint,
                pollinator_service_south=midpoint,
            ),
        ),
        AnchoredGradientCase(
            label="service_increases_with_spot_axis",
            interpretation=(
                "Sensitivity case in which declared pollinator service increases "
                "along the observed spot-trait axis; this is not estimated from "
                "guild presence/absence."
            ),
            sites=sites,
            landscape=IzuGradientLandscape(
                **common,
                pollinator_service_north=assumptions.pollinator_service_low,
                pollinator_service_south=assumptions.pollinator_service_high,
            ),
        ),
        AnchoredGradientCase(
            label="service_decreases_with_spot_axis",
            interpretation=(
                "Sensitivity case in which declared pollinator service decreases "
                "along the observed spot-trait axis; this is not estimated from "
                "guild presence/absence."
            ),
            sites=sites,
            landscape=IzuGradientLandscape(
                **common,
                pollinator_service_north=assumptions.pollinator_service_high,
                pollinator_service_south=assumptions.pollinator_service_low,
            ),
        ),
    )


def render_empirical_anchor_report(
    bundle: EmpiricalAnchorBundle,
    assumptions: EmpiricalGradientAssumptions,
) -> str:
    """Render a transparent observed-versus-assumed bridge report as Markdown."""

    sites = trait_gradient_sites(bundle.population_traits)
    availability = dict(
        (population_id, (status, effort))
        for population_id, status, effort in focal_guild_availability(
            bundle,
            assumptions.focal_guild,
        )
    )
    cases = empirical_gradient_cases(bundle, assumptions)
    lines = [
        "# Empirical anchor report for spot-trait gradient simulation",
        "",
        "## Observed anchors",
        "",
        f"- Trait: `{bundle.pst_fst.trait_name}`",
        f"- Reported P_ST: `{bundle.pst_fst.pst:.4f}`",
        f"- Reported F_ST: `{bundle.pst_fst.fst:.4f}`",
        "- P_ST exceeds F_ST at the reported point estimate: "
        + ("`yes`" if bundle.pst_fst.selection_compatible else "`no`"),
        "- Critical c/h² sensitivity boundary: "
        + (
            f"`{bundle.pst_fst.critical_c_over_h2:.4g}`"
            if bundle.pst_fst.critical_c_over_h2 is not None
            else "`not supplied`"
        ),
        f"- Inbreeding census interval: `{bundle.inbreeding.census_interval}`",
        f"- Relative selfed fitness: `{bundle.inbreeding.relative_selfed_fitness:.4f}`",
        f"- Inbreeding depression (1 - selfed/outcrossed): `{bundle.inbreeding.inbreeding_depression:.4f}`",
        "- Directly mapped to post-seed survival: "
        + ("`yes`" if bundle.inbreeding.maps_to_post_seed_survival else "`no`"),
        "",
        "## Trait-axis populations",
        "",
        "| population | spot mean | trait n | scaled spot-axis position | focal guild status | effort (min) |",
        "|---|---:|---:|---:|---|---:|",
    ]
    trait_by_id = {record.population_id: record for record in bundle.population_traits}
    for site in sites:
        trait = trait_by_id[site.label]
        status, effort = availability[site.label]
        lines.append(
            "| "
            + " | ".join(
                (
                    site.label,
                    f"{trait.spot_trait_mean:.6g}",
                    str(trait.trait_n),
                    f"{site.archipelago_position:.4f}",
                    status,
                    f"{effort:.1f}",
                )
            )
            + " |"
        )
    lines.extend(
        (
            "",
            "## Declared, non-empirical scenario assumptions",
            "",
            f"- Focal guild for availability context: `{assumptions.focal_guild}`",
            f"- Spot trait → modeled guide contrast: `{assumptions.trait_contrast_min:.3f}` to `{assumptions.trait_contrast_max:.3f}` after min--max scaling.",
            f"- Low/high pollinator-service sensitivity values: `{assumptions.pollinator_service_low:.3f}` / `{assumptions.pollinator_service_high:.3f}`.",
            f"- Establishment multiplier: `{assumptions.establishment_multiplier:.3f}` at both trait-axis endpoints.",
            "",
            "| case | interpretation | pollinator service at low spot axis | pollinator service at high spot axis |",
            "|---|---|---:|---:|",
        )
    )
    for case in cases:
        lines.append(
            "| "
            + " | ".join(
                (
                    case.label,
                    case.interpretation,
                    f"{case.landscape.pollinator_service_north:.3f}",
                    f"{case.landscape.pollinator_service_south:.3f}",
                )
            )
            + " |"
        )
    lines.extend(
        (
            "",
            "## Interpretation boundary",
            "",
            "The observed P_ST--F_ST comparison is evidence about trait divergence, not a visit, handling, or assurance effect size. Pollinator guild presence/absence is availability context, not a visit-rate estimate. The service-gradient cases are deliberately bracketing assumptions. A successful virtual recovery under any case therefore shows only that the declared mechanism is compatible and identifiable under that case; it does not demonstrate that the mechanism generated the observed field pattern.",
            "",
            "Use `trait_gradient_sites`, `empirical_gradient_cases`, and (only when the census interval is `post_seed`) `apply_inbreeding_anchor` as inputs to the existing scenario-recovery or pooled-evidence workflows.",
        )
    )
    return "\n".join(lines) + "\n"


def _read_csv_rows(path: Path, required: Iterable[str]) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"{path.name} must contain a header row")
        missing = [field for field in required if field not in reader.fieldnames]
        if missing:
            raise ValueError(f"{path.name} is missing required columns: {', '.join(missing)}")
        return list(reader)


def _parse_bool(value: str, name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "t", "1", "yes", "y"}:
        return True
    if normalized in {"false", "f", "0", "no", "n"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


def _optional_float(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    return float(value)


def load_empirical_anchor_bundle(directory: str | Path) -> EmpiricalAnchorBundle:
    """Load the four canonical empirical-anchor CSV files from one directory."""

    root = Path(directory)
    trait_rows = _read_csv_rows(
        root / "population_traits.csv",
        ("population_id", "spot_trait_mean", "trait_n"),
    )
    traits = tuple(
        PopulationTraitAnchor(
            population_id=row["population_id"].strip(),
            spot_trait_mean=float(row["spot_trait_mean"]),
            trait_n=int(row["trait_n"]),
            spot_trait_sd=_optional_float(row.get("spot_trait_sd")),
        )
        for row in trait_rows
    )
    pst_rows = _read_csv_rows(
        root / "pst_fst.csv",
        ("trait_name", "pst", "fst"),
    )
    if len(pst_rows) != 1:
        raise ValueError("pst_fst.csv must contain exactly one summary row")
    pst_row = pst_rows[0]
    pst_fst = PstFstAnchor(
        trait_name=pst_row["trait_name"].strip(),
        pst=float(pst_row["pst"]),
        fst=float(pst_row["fst"]),
        critical_c_over_h2=_optional_float(pst_row.get("critical_c_over_h2")),
    )
    inbreeding_rows = _read_csv_rows(
        root / "inbreeding_fitness.csv",
        ("census_interval", "selfed_mean_fitness", "outcrossed_mean_fitness"),
    )
    if len(inbreeding_rows) != 1:
        raise ValueError("inbreeding_fitness.csv must contain exactly one summary row")
    inbreeding_row = inbreeding_rows[0]
    inbreeding = InbreedingFitnessAnchor(
        census_interval=inbreeding_row["census_interval"].strip(),
        selfed_mean_fitness=float(inbreeding_row["selfed_mean_fitness"]),
        outcrossed_mean_fitness=float(inbreeding_row["outcrossed_mean_fitness"]),
    )
    pollinator_rows = _read_csv_rows(
        root / "pollinator_availability.csv",
        ("population_id", "guild", "detected", "effort_minutes"),
    )
    availability = tuple(
        PollinatorAvailabilityAnchor(
            population_id=row["population_id"].strip(),
            guild=row["guild"].strip(),
            detected=_parse_bool(row["detected"], "detected"),
            effort_minutes=float(row["effort_minutes"]),
        )
        for row in pollinator_rows
    )
    return EmpiricalAnchorBundle(traits, pst_fst, inbreeding, availability)


def empirical_anchor_template_readme() -> str:
    """Return the README written alongside blank empirical-anchor CSV files."""

    return """# Empirical gradient-anchor input

These files constrain a virtual spot-trait gradient. They do **not** estimate a
visit, handling, or assurance effect from the supplied summaries.

## Files

- `population_traits.csv`: one population-level mean spot trait per row.
- `pst_fst.csv`: exactly one P_ST--F_ST summary for that trait. The optional
  `critical_c_over_h2` records the sensitivity boundary from the underlying
  P_ST analysis.
- `inbreeding_fitness.csv`: exactly one common-census selfed/outcrossed fitness
  summary. Use `post_seed` only when the estimate is specifically from a
  germination-to-recruit or otherwise post-seed interval. Use `total_lifetime`
  when it cannot directly map to late post-seed survival.
- `pollinator_availability.csv`: guild detection plus observation effort.
  `detected=false` means not detected during the stated effort, not ecological
  absence and not a zero visit rate.

## Intended use

```python
from channel_id.empirical_gradient_anchor import (
    EmpiricalGradientAssumptions,
    apply_inbreeding_anchor,
    empirical_gradient_cases,
    load_empirical_anchor_bundle,
)

anchors = load_empirical_anchor_bundle("data/empirical_anchor")
assumptions = EmpiricalGradientAssumptions(focal_guild="bumblebee")
cases = empirical_gradient_cases(anchors, assumptions)

# Only valid for a post-seed inbreeding estimate.
settings = apply_inbreeding_anchor(template_settings, anchors.inbreeding)
```

The numerical low/high pollinator-service values remain declared sensitivity
assumptions. Run flat, trait-aligned, and trait-opposed cases; do not select one
from presence/absence data alone.
"""


def write_empirical_anchor_templates(output_directory: str | Path) -> tuple[Path, ...]:
    """Write blank, stable CSV templates for empirical gradient anchors."""

    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    files = {
        "population_traits.csv": "population_id,spot_trait_mean,spot_trait_sd,trait_n\n",
        "pst_fst.csv": "trait_name,pst,fst,critical_c_over_h2\n",
        "inbreeding_fitness.csv": "census_interval,selfed_mean_fitness,outcrossed_mean_fitness\n",
        "pollinator_availability.csv": "population_id,guild,detected,effort_minutes\n",
        "README.md": empirical_anchor_template_readme(),
    }
    paths: list[Path] = []
    for filename, content in files.items():
        path = output / filename
        path.write_text(content, encoding="utf-8")
        paths.append(path)
    return tuple(paths)
