"""Auditable public-evidence registry for the two-breakpoint pollinator hypothesis.

The hypothesis distinguishes (1) a shift from large Bombus to *Bombus ardens*,
which can alter floral-size optima while retaining spotted, outcrossed flowers,
from (2) loss of Bombus, after which guide benefit and effective outcross service
may fall together.  This module does not infer that history.  It validates the
provenance and evidentiary status of public records before they are allowed to
constrain a scenario or sensitivity range.

LLMs may create ``candidate`` or ``extracted`` records.  Only a human-reviewed
``verified`` record with a source locator can become an observed anchor.  Public
occurrences and photographs are contextual/derived evidence, never direct proof
of visitation or causal selection.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping


SOURCE_TYPES = frozenset(
    {
        "primary_article",
        "review_article",
        "thesis",
        "checklist",
        "occurrence_dataset",
        "photo_observation",
        "specimen_database",
        "taxonomic_database",
        "other",
    }
)
SOURCE_STATUSES = frozenset({"candidate", "retrieved", "verified", "rejected"})
EXTRACTION_STATUSES = frozenset({"candidate", "extracted", "verified", "rejected"})
HUMAN_REVIEW_STATUSES = frozenset({"not_reviewed", "reviewed", "rejected"})
CLAIM_TYPES = frozenset(
    {
        "pollinator_presence",
        "pollinator_non_detection",
        "pollinator_confirmed_absence",
        "pollinator_interaction",
        "mating_system",
        "selfing_rate",
        "outcrossing_rate",
        "self_compatibility",
        "spot_presence",
        "spot_fraction",
        "spot_position",
        "flower_size",
        "taxonomic_mapping",
        "occurrence_record",
        "photo_trait_measurement",
        "environmental_context",
    }
)
DIRECTNESS = frozenset(
    {
        "direct_measurement",
        "direct_observation",
        "derived_reproducibly",
        "contextual_availability",
        "inferred",
    }
)
CAUSAL_STATUSES = frozenset(
    {
        "manipulated",
        "quasi_experimental",
        "observational",
        "descriptive",
        "not_assessed",
    }
)
SCENARIO_IDS = frozenset(
    {
        "environment_only",
        "body_size_only",
        "small_bee_substitution",
        "ardens_replacement_loss",
    }
)
ASSUMPTION_CLASSES = frozenset(
    {
        "observed_anchor",
        "derived_anchor",
        "sensitivity_only",
        "not_identified",
    }
)

SOURCE_REQUIRED_COLUMNS = frozenset(
    {
        "source_id",
        "citation_or_title",
        "stable_locator",
        "source_type",
        "source_status",
        "retrieval_date",
        "llm_extraction_status",
        "human_review_status",
        "notes",
    }
)
CLAIM_REQUIRED_COLUMNS = frozenset(
    {
        "claim_id",
        "source_id",
        "claim_type",
        "target_taxon",
        "raw_taxon_name",
        "accepted_taxon",
        "geographic_unit",
        "site_or_island",
        "observation_start",
        "observation_end",
        "observation_method",
        "value",
        "value_unit",
        "numerator",
        "denominator_or_effort",
        "uncertainty_lower",
        "uncertainty_upper",
        "source_locator",
        "verbatim_basis",
        "directness",
        "causal_status",
        "extraction_status",
        "human_review_status",
        "notes",
    }
)
CONSTRAINT_REQUIRED_COLUMNS = frozenset(
    {
        "constraint_id",
        "scenario_id",
        "parameter_name",
        "lower",
        "upper",
        "unit",
        "assumption_class",
        "supporting_claim_ids",
        "rationale",
        "status",
        "notes",
    }
)

RATE_CLAIMS = frozenset({"selfing_rate", "outcrossing_rate"})
DIRECT_PARAMETER_CLAIMS = frozenset(
    {
        "selfing_rate",
        "outcrossing_rate",
        "mating_system",
        "self_compatibility",
        "flower_size",
        "spot_fraction",
        "spot_position",
    }
)


@dataclass(frozen=True)
class EvidenceRecordSummary:
    record_id: str
    record_kind: str
    analysis_ready: bool
    observed_anchor_eligible: bool
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceRegistryAudit:
    source_summaries: tuple[EvidenceRecordSummary, ...]
    claim_summaries: tuple[EvidenceRecordSummary, ...]
    constraint_summaries: tuple[EvidenceRecordSummary, ...]
    counts_by_claim_type: dict[str, int]
    anchor_eligible_claims: int
    warnings: tuple[str, ...]


def _text(value: object) -> str:
    return str(value or "").strip()


def _has_value(value: object) -> bool:
    return _text(value).lower() not in {"", "na", "n/a", "none", "not_available", "not_assessed"}


def _as_float(value: object, field: str) -> float:
    try:
        return float(_text(value))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} must be numeric when supplied") from error


def _require_columns(rows: list[dict[str, str]], required: frozenset[str], name: str) -> None:
    if not rows:
        return
    missing = sorted(required.difference(rows[0]))
    if missing:
        raise ValueError(f"{name} registry missing columns: {', '.join(missing)}")


def _check_choice(value: str, allowed: frozenset[str], field: str, warnings: list[str]) -> None:
    if value not in allowed:
        warnings.append(f"{field} is not in the declared vocabulary.")


def classify_source_record(row: Mapping[str, str]) -> EvidenceRecordSummary:
    """Validate provenance for one source before inspecting ecological claims."""

    source_id = _text(row.get("source_id")) or "<missing source_id>"
    warnings: list[str] = []
    for field in ("citation_or_title", "stable_locator", "retrieval_date", "notes"):
        if not _has_value(row.get(field)):
            warnings.append(f"missing {field}")
    _check_choice(_text(row.get("source_type")), SOURCE_TYPES, "source_type", warnings)
    _check_choice(_text(row.get("source_status")), SOURCE_STATUSES, "source_status", warnings)
    _check_choice(
        _text(row.get("llm_extraction_status")), EXTRACTION_STATUSES, "llm_extraction_status", warnings
    )
    _check_choice(
        _text(row.get("human_review_status")), HUMAN_REVIEW_STATUSES, "human_review_status", warnings
    )
    analysis_ready = not warnings and _text(row.get("source_status")) == "verified"
    return EvidenceRecordSummary(source_id, "source", analysis_ready, False, tuple(warnings))


def classify_claim_record(
    row: Mapping[str, str], source_ids: set[str]
) -> EvidenceRecordSummary:
    """Validate one extracted claim without making an ecological inference."""

    claim_id = _text(row.get("claim_id")) or "<missing claim_id>"
    claim_type = _text(row.get("claim_type"))
    warnings: list[str] = []
    if not _text(row.get("source_id")):
        warnings.append("missing source_id")
    elif _text(row.get("source_id")) not in source_ids:
        warnings.append("source_id does not occur in source registry")
    _check_choice(claim_type, CLAIM_TYPES, "claim_type", warnings)
    _check_choice(_text(row.get("directness")), DIRECTNESS, "directness", warnings)
    _check_choice(_text(row.get("causal_status")), CAUSAL_STATUSES, "causal_status", warnings)
    _check_choice(
        _text(row.get("extraction_status")), EXTRACTION_STATUSES, "extraction_status", warnings
    )
    _check_choice(
        _text(row.get("human_review_status")), HUMAN_REVIEW_STATUSES, "human_review_status", warnings
    )
    for field in (
        "target_taxon",
        "raw_taxon_name",
        "accepted_taxon",
        "geographic_unit",
        "site_or_island",
        "observation_method",
        "source_locator",
        "verbatim_basis",
        "notes",
    ):
        if not _has_value(row.get(field)):
            warnings.append(f"missing {field}")

    if claim_type in RATE_CLAIMS:
        for field in ("value", "denominator_or_effort"):
            if not _has_value(row.get(field)):
                warnings.append(f"missing {field} for rate claim")
        if _has_value(row.get("value")):
            try:
                value = _as_float(row["value"], "value")
                if not 0.0 <= value <= 1.0:
                    warnings.append("rate claim value must lie in [0, 1]")
            except ValueError as error:
                warnings.append(str(error))
    if claim_type == "pollinator_non_detection" and not _has_value(row.get("denominator_or_effort")):
        warnings.append("non-detection requires denominator_or_effort; it is not absence")
    if claim_type == "pollinator_confirmed_absence":
        for field in ("denominator_or_effort", "observation_start", "observation_end"):
            if not _has_value(row.get(field)):
                warnings.append(f"confirmed absence requires {field}")
    for field in ("uncertainty_lower", "uncertainty_upper"):
        if _has_value(row.get(field)):
            try:
                _as_float(row[field], field)
            except ValueError as error:
                warnings.append(str(error))
    if _has_value(row.get("uncertainty_lower")) and _has_value(row.get("uncertainty_upper")):
        try:
            if _as_float(row["uncertainty_lower"], "uncertainty_lower") > _as_float(
                row["uncertainty_upper"], "uncertainty_upper"
            ):
                warnings.append("uncertainty_lower cannot exceed uncertainty_upper")
        except ValueError:
            pass

    analysis_ready = not warnings
    observed_anchor_eligible = (
        analysis_ready
        and claim_type in DIRECT_PARAMETER_CLAIMS
        and _text(row.get("directness")) in {"direct_measurement", "derived_reproducibly"}
        and _text(row.get("extraction_status")) == "verified"
        and _text(row.get("human_review_status")) == "reviewed"
    )
    if claim_type in {"pollinator_presence", "pollinator_non_detection", "pollinator_confirmed_absence", "occurrence_record", "pollinator_interaction"}:
        observed_anchor_eligible = False
    return EvidenceRecordSummary(
        claim_id, "claim", analysis_ready, observed_anchor_eligible, tuple(warnings)
    )


def classify_constraint_record(
    row: Mapping[str, str], claim_summaries: Mapping[str, EvidenceRecordSummary]
) -> EvidenceRecordSummary:
    """Validate a scenario range and prevent unreviewed claims becoming facts."""

    constraint_id = _text(row.get("constraint_id")) or "<missing constraint_id>"
    warnings: list[str] = []
    _check_choice(_text(row.get("scenario_id")), SCENARIO_IDS, "scenario_id", warnings)
    _check_choice(
        _text(row.get("assumption_class")), ASSUMPTION_CLASSES, "assumption_class", warnings
    )
    for field in ("parameter_name", "lower", "upper", "unit", "rationale", "status", "notes"):
        if not _has_value(row.get(field)):
            warnings.append(f"missing {field}")
    try:
        lower = _as_float(row.get("lower"), "lower")
        upper = _as_float(row.get("upper"), "upper")
        if lower > upper:
            warnings.append("lower cannot exceed upper")
    except ValueError as error:
        warnings.append(str(error))
    claim_ids = [item.strip() for item in _text(row.get("supporting_claim_ids")).split(";") if item.strip()]
    assumption_class = _text(row.get("assumption_class"))
    if assumption_class in {"observed_anchor", "derived_anchor"}:
        if not claim_ids:
            warnings.append("anchor constraint requires supporting_claim_ids")
        for claim_id in claim_ids:
            summary = claim_summaries.get(claim_id)
            if summary is None:
                warnings.append(f"supporting claim not found: {claim_id}")
            elif not summary.observed_anchor_eligible:
                warnings.append(f"supporting claim is not eligible as observed anchor: {claim_id}")
    if assumption_class in {"sensitivity_only", "not_identified"} and claim_ids:
        warnings.append("sensitivity/not_identified constraint must not present claim IDs as calibration")
    analysis_ready = not warnings
    return EvidenceRecordSummary(constraint_id, "constraint", analysis_ready, False, tuple(warnings))


def audit_two_breakpoint_registries(
    sources: Iterable[Mapping[str, str]],
    claims: Iterable[Mapping[str, str]],
    constraints: Iterable[Mapping[str, str]],
) -> EvidenceRegistryAudit:
    """Audit source, claim, and scenario registries as separate evidence layers."""

    source_rows = [{key: _text(value) for key, value in row.items()} for row in sources]
    claim_rows = [{key: _text(value) for key, value in row.items()} for row in claims]
    constraint_rows = [{key: _text(value) for key, value in row.items()} for row in constraints]
    _require_columns(source_rows, SOURCE_REQUIRED_COLUMNS, "source")
    _require_columns(claim_rows, CLAIM_REQUIRED_COLUMNS, "claim")
    _require_columns(constraint_rows, CONSTRAINT_REQUIRED_COLUMNS, "constraint")

    global_warnings: list[str] = []
    source_summaries: list[EvidenceRecordSummary] = []
    source_ids: set[str] = set()
    for row in source_rows:
        source_id = _text(row.get("source_id"))
        if not source_id:
            global_warnings.append("Source without source_id ignored.")
            continue
        if source_id in source_ids:
            global_warnings.append(f"Duplicate source_id ignored: {source_id}")
            continue
        source_ids.add(source_id)
        source_summaries.append(classify_source_record(row))

    claim_summaries: list[EvidenceRecordSummary] = []
    claim_by_id: dict[str, EvidenceRecordSummary] = {}
    for row in claim_rows:
        claim_id = _text(row.get("claim_id"))
        if not claim_id:
            global_warnings.append("Claim without claim_id ignored.")
            continue
        if claim_id in claim_by_id:
            global_warnings.append(f"Duplicate claim_id ignored: {claim_id}")
            continue
        summary = classify_claim_record(row, source_ids)
        claim_by_id[claim_id] = summary
        claim_summaries.append(summary)

    constraint_summaries: list[EvidenceRecordSummary] = []
    constraint_ids: set[str] = set()
    for row in constraint_rows:
        constraint_id = _text(row.get("constraint_id"))
        if not constraint_id:
            global_warnings.append("Constraint without constraint_id ignored.")
            continue
        if constraint_id in constraint_ids:
            global_warnings.append(f"Duplicate constraint_id ignored: {constraint_id}")
            continue
        constraint_ids.add(constraint_id)
        constraint_summaries.append(classify_constraint_record(row, claim_by_id))

    counts: dict[str, int] = {}
    for row in claim_rows:
        kind = _text(row.get("claim_type")) or "not_declared"
        counts[kind] = counts.get(kind, 0) + 1
    return EvidenceRegistryAudit(
        source_summaries=tuple(sorted(source_summaries, key=lambda item: item.record_id)),
        claim_summaries=tuple(sorted(claim_summaries, key=lambda item: item.record_id)),
        constraint_summaries=tuple(sorted(constraint_summaries, key=lambda item: item.record_id)),
        counts_by_claim_type=dict(sorted(counts.items())),
        anchor_eligible_claims=sum(item.observed_anchor_eligible for item in claim_summaries),
        warnings=tuple(global_warnings),
    )


def read_registry_csv(path: str | Path) -> list[dict[str, str]]:
    """Read a registry CSV without changing values or interpreting missingness."""

    with Path(path).open(encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def audit_two_breakpoint_registry_directory(directory: str | Path) -> EvidenceRegistryAudit:
    """Audit the three canonical CSV registries in one directory."""

    root = Path(directory)
    return audit_two_breakpoint_registries(
        read_registry_csv(root / "sources.csv"),
        read_registry_csv(root / "claims.csv"),
        read_registry_csv(root / "scenario_constraints.csv"),
    )


def evidence_audit_to_dict(report: EvidenceRegistryAudit) -> dict[str, object]:
    """Return a JSON-serialisable audit summary for programmatic review."""

    return {
        "source_summaries": [asdict(summary) for summary in report.source_summaries],
        "claim_summaries": [asdict(summary) for summary in report.claim_summaries],
        "constraint_summaries": [asdict(summary) for summary in report.constraint_summaries],
        "counts_by_claim_type": report.counts_by_claim_type,
        "anchor_eligible_claims": report.anchor_eligible_claims,
        "warnings": list(report.warnings),
    }


def write_two_breakpoint_registry_templates(output_directory: str | Path) -> tuple[Path, ...]:
    """Write blank, stable templates plus the LLM-assisted extraction contract."""

    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    templates = {
        "sources.csv": ",".join(sorted(SOURCE_REQUIRED_COLUMNS)) + "\n",
        "claims.csv": ",".join(sorted(CLAIM_REQUIRED_COLUMNS)) + "\n",
        "scenario_constraints.csv": ",".join(sorted(CONSTRAINT_REQUIRED_COLUMNS)) + "\n",
        "README.md": two_breakpoint_registry_readme(),
        "llm_extraction_prompt.md": llm_extraction_prompt(),
    }
    paths: list[Path] = []
    for filename, content in templates.items():
        path = output / filename
        path.write_text(content, encoding="utf-8")
        paths.append(path)
    return tuple(paths)


def two_breakpoint_registry_readme() -> str:
    """Describe the evidence firewall between public facts and simulations."""

    return """# Two-breakpoint public-evidence registry

This registry supports comparison of four **declared** explanations for island
variation in floral size, spotting, and mating system:

- `environment_only`
- `body_size_only`
- `small_bee_substitution`
- `ardens_replacement_loss`

It does not turn occurrence records, photographs, or LLM summaries into proof
of pollination, selection, or historical change.

## Evidence layers

1. `sources.csv` records what was retrieved and reviewed.
2. `claims.csv` records one source-locatable claim at a time.
3. `scenario_constraints.csv` records either a verified observed/derived anchor
   or an explicitly non-empirical sensitivity range.

A verified direct trait or mating-system measurement can become an observed
anchor. Pollinator occurrence, non-detection, and photograph records remain
contextual/derived evidence: they can motivate a scenario comparison but do not
calibrate pollinator effectiveness.

## Non-detection rule

`pollinator_non_detection` requires observation effort. It means only that a
taxon was not detected under the recorded effort. It must never be rewritten as
absence. `pollinator_confirmed_absence` requires a stated sampling interval and
effort, and should be used rarely.

## LLM role

An LLM may identify candidate sources and transcribe candidate claims only when
it retains the exact source locator and a short verbatim basis. Human review is
required before a record receives `verified` status. Do not ask an LLM to infer
missing denominators, transform an ambiguous mating statistic into a selfing
rate, or declare a historical pollinator loss from a present-day occurrence map.

## Audit

```bash
python scripts/audit_two_breakpoint_evidence.py \\
  --input-dir data/two_breakpoint_evidence \\
  --output artifacts/two_breakpoint_evidence_audit.json
```

The audit reports which records are structurally ready and which claims are
eligible as observed anchors. It does not judge whether the hypothesis is true.
"""


def llm_extraction_prompt() -> str:
    """Return a reusable, deliberately conservative extraction prompt."""

    return """# LLM extraction contract: two-breakpoint pollinator hypothesis

You are assisting a human reviewer. Extract **candidate evidence only** from the
single source supplied to you. Do not synthesize across sources, infer a missing
value, or decide whether a hypothesis is true.

For every candidate claim, output one row with:

- `claim_type`
- raw and accepted taxon names exactly as reported / mapped
- island or site exactly as reported
- dates, method, value, units, numerator, denominator or observation effort
- uncertainty when reported
- exact page/table/figure/supplement locator
- a short verbatim basis (not a paraphrase)
- `directness` and `causal_status`
- `extraction_status=candidate`
- `human_review_status=not_reviewed`

Rules:

1. A failure to mention a pollinator is not absence.
2. A GBIF or photo occurrence is not a visitation or effectiveness record.
3. `selfing_rate`, `outcrossing_rate`, self-compatibility, autonomous selfing,
   and fruit set are distinct quantities. Never substitute one for another.
4. Do not convert historical names into accepted names unless a separate cited
   taxonomic mapping is supplied; preserve both names.
5. Do not create numerical scenario parameters. Scenario parameters belong in
   `scenario_constraints.csv` and must be explicitly labelled sensitivity-only
   unless a reviewed claim supports the mapping.
6. Return `not_reported` rather than guessing.
"""
