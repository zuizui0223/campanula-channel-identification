"""Build a provenance-preserving empirical evidence matrix for Izu Campanula.

The matrix is a source-aligned summary of direct observations from the supplied
Inoue series. It deliberately does not infer historical event order, treat a
missing measurement as a biological zero, or convert public occurrence records
into pollination effectiveness.

The output is intended to lock down observed patterns before simulation:

- pollinator observations and their effort;
- bagging / autonomous seed-production data;
- outcrossing rates and compatibility labels;
- dichogamy and sex-allocation traits;
- common-garden flower-size summaries and experimental response results.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Iterable


ISLAND_ALIASES = {
    "Kozu": "Kozushima",
    "Kozushima": "Kozushima",
    "Oshima": "Oshima",
    "Toshima": "Toshima",
    "Niijima": "Niijima",
    "Miyake": "Miyake",
    "Hachijo": "Hachijo",
    "Chiba": "Chiba",
    "Shizuoka": "Shizuoka",
}


@dataclass(frozen=True)
class EvidenceCoverage:
    island: str
    has_outcrossing: bool
    has_bagging: bool
    has_dichogamy: bool
    has_sex_allocation: bool
    has_common_garden_flower_size: bool
    has_direct_pollinator_observation: bool
    has_main_pollinator_label: bool
    warnings: tuple[str, ...]


def canonical_island(value: str) -> str:
    """Resolve only explicitly declared aliases; unknown names remain visible."""

    normalized = value.strip()
    return ISLAND_ALIASES.get(normalized, normalized)


def _direct_rate_region(row: dict[str, str]) -> str:
    """Map Table-2 localities to the paper's declared analysis region.

    Locality strings are retained untouched in the source CSV. This mapping is
    only for the island/mainland summary table, where Shizuoka and Chiba each
    have multiple observation localities. It never turns a site-level zero rate
    into a regional absence statement.
    """

    if row["region"] == "Izu":
        return canonical_island(row["locality_or_island"])
    locality = row["locality_or_island"].strip()
    if locality.startswith("Chiba "):
        return "Chiba"
    if locality.startswith("Shizuoka "):
        return "Shizuoka"
    if locality.startswith("Tokyo "):
        return "Tokyo"
    return canonical_island(locality)


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _number(value: str | None) -> float | None:
    text = (value or "").strip()
    return None if not text else float(text)


def _mean(values: Iterable[float]) -> float | None:
    rows = tuple(values)
    return mean(rows) if rows else None


def build_island_matrix(data_dir: str | Path) -> list[dict[str, object]]:
    """Aggregate direct table entries into an island-level view with provenance.

    Aggregation is intentionally limited to simple reported means/rates. It does
    not pool across papers as though rows were independent replicates.
    """

    root = Path(data_dir)
    outcrossing = read_csv(root / "inoue1990_outcrossing.csv")
    bagging = read_csv(root / "inoue1988_bagging.csv")
    dichogamy = read_csv(root / "inoue1990_dichogamy.csv")
    allocation = read_csv(root / "inoue1990_sex_allocation.csv")
    flower_size = read_csv(root / "inoue1995_flower_length.csv")
    direct_rates = read_csv(root / "inoue1986_pollinator_rates.csv")
    main_pollinators = read_csv(root / "inoue1990_pollinator_groups.csv")

    islands: set[str] = set()
    for rows, field in (
        (outcrossing, "island"),
        (bagging, "island_or_mainland"),
        (dichogamy, "island_or_mainland"),
        (allocation, "island_or_mainland"),
        (flower_size, "island"),
        (main_pollinators, "island"),
    ):
        islands.update(canonical_island(row[field]) for row in rows)
    islands.update(_direct_rate_region(row) for row in direct_rates)

    results: list[dict[str, object]] = []
    for island in sorted(islands):
        out_values = [
            _number(row["outcrossing_t"])
            for row in outcrossing
            if canonical_island(row["island"]) == island and _number(row["outcrossing_t"]) is not None
        ]
        bag_rows = [row for row in bagging if canonical_island(row["island_or_mainland"]) == island]
        total_dichogamy = [
            row for row in dichogamy
            if canonical_island(row["island_or_mainland"]) == island and row["weather"] == "total"
        ]
        allocation_rows = [row for row in allocation if canonical_island(row["island_or_mainland"]) == island]
        flower_rows = [row for row in flower_size if canonical_island(row["island"]) == island]
        rate_rows = [row for row in direct_rates if _direct_rate_region(row) == island]
        main_rows = [row for row in main_pollinators if canonical_island(row["island"]) == island]

        results.append(
            {
                "island": island,
                "outcrossing_t_mean": _mean(value for value in out_values if value is not None),
                "outcrossing_populations": len(out_values),
                "bagged_capsule_set_percent": _number(bag_rows[0]["bagged_capsule_set_percent"]) if len(bag_rows) == 1 else None,
                "bagged_mean_seeds_per_capsule": _number(bag_rows[0]["bagged_mean_seeds_per_capsule"]) if len(bag_rows) == 1 else None,
                "open_mean_seeds_per_capsule": _number(bag_rows[0]["nonbagged_mean_seeds_per_capsule"]) if len(bag_rows) == 1 else None,
                "staminate_phase_days_total": _number(next((row["mean_days"] for row in total_dichogamy if row["phase"] == "staminate"), None)),
                "pistillate_phase_days_total": _number(next((row["mean_days"] for row in total_dichogamy if row["phase"] == "pistillate"), None)),
                "male_reproductive_effort_mean": _number(allocation_rows[0]["male_reproductive_effort_mean"]) if len(allocation_rows) == 1 else None,
                "androecium_to_gynoecium_ratio_mean": _number(allocation_rows[0]["androecium_to_gynoecium_ratio_mean"]) if len(allocation_rows) == 1 else None,
                "flower_length_mean_mm": _number(flower_rows[0]["mean_flower_length_mm"]) if len(flower_rows) == 1 else None,
                "flower_length_n": int(flower_rows[0]["n"]) if len(flower_rows) == 1 else None,
                "direct_pollinator_rate_rows": len(rate_rows),
                "direct_pollinator_groups": ";".join(sorted({row["pollinator_taxon_or_group"] for row in rate_rows})),
                "main_pollinator_groups": ";".join(sorted({row["pollinator_group"] for row in main_rows})),
                "source_boundary": "Direct Inoue-series table summaries; missing fields mean no row in the currently digitized source set, not biological absence.",
            }
        )
    return results


def coverage_audit(data_dir: str | Path) -> tuple[EvidenceCoverage, ...]:
    matrix = build_island_matrix(data_dir)
    coverage = []
    for row in matrix:
        island = str(row["island"])
        warnings = []
        if row["outcrossing_t_mean"] is None:
            warnings.append("No digitized outcrossing estimate in the current source set.")
        if row["flower_length_mean_mm"] is None:
            warnings.append("No common-garden flower-length summary in the current source set.")
        if not row["direct_pollinator_groups"]:
            warnings.append("No direct pollinator-rate row in the current source set.")
        if not row["main_pollinator_groups"]:
            warnings.append("No main-pollinator label in the current source set.")
        coverage.append(
            EvidenceCoverage(
                island=island,
                has_outcrossing=row["outcrossing_t_mean"] is not None,
                has_bagging=row["bagged_capsule_set_percent"] is not None,
                has_dichogamy=row["staminate_phase_days_total"] is not None,
                has_sex_allocation=row["male_reproductive_effort_mean"] is not None,
                has_common_garden_flower_size=row["flower_length_mean_mm"] is not None,
                has_direct_pollinator_observation=bool(row["direct_pollinator_groups"]),
                has_main_pollinator_label=bool(row["main_pollinator_groups"]),
                warnings=tuple(warnings),
            )
        )
    return tuple(coverage)


def _format_float(value: object, digits: int = 3) -> str:
    return "" if value is None else f"{float(value):.{digits}f}"


def render_empirical_evidence_markdown(data_dir: str | Path) -> str:
    matrix = build_island_matrix(data_dir)
    coverage = coverage_audit(data_dir)
    lines = [
        "# Empirical evidence lock: Izu Campanula",
        "",
        "This is a provenance-preserving inventory of direct observations from the digitized Inoue series. It is a data-lock report, not a fitted causal model or historical reconstruction.",
        "",
        "| island / region | mean outcrossing t | bagged capsule set (%) | bagged seed mean | open seed mean | flower length (mm) | direct visitor groups | main visitor groups |",
        "|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in matrix:
        lines.append(
            "| {island} | {t} | {bag} | {bagseed} | {openseed} | {flower} | {direct} | {main} |".format(
                island=row["island"],
                t=_format_float(row["outcrossing_t_mean"]),
                bag=_format_float(row["bagged_capsule_set_percent"], 1),
                bagseed=_format_float(row["bagged_mean_seeds_per_capsule"], 1),
                openseed=_format_float(row["open_mean_seeds_per_capsule"], 1),
                flower=_format_float(row["flower_length_mean_mm"], 2),
                direct=row["direct_pollinator_groups"] or "",
                main=row["main_pollinator_groups"] or "",
            )
        )
    lines.extend((
        "",
        "## Coverage gaps retained explicitly",
        "",
        "| island / region | gaps |",
        "|---|---|",
    ))
    for item in coverage:
        if item.warnings:
            lines.append(f"| {item.island} | {' '.join(item.warnings)} |")
    lines.extend(
        (
            "",
            "## Rules for subsequent modelling",
            "",
            "1. These direct field and experiment records can constrain observed channels; GBIF/iNaturalist occurrence remains a separate availability channel.",
            "2. The common-garden response experiment does not measure natural island-specific pollination efficacy.",
            "3. Bagging results measure autonomous capsule/seed production under that experiment; they are not identical to a contemporary realized selfing rate.",
            "4. An empty cell remains missing, never a biological zero or absence.",
        )
    )
    return "\n".join(lines) + "\n"
