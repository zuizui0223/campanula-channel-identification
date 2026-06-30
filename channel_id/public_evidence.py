"""Auditable public-observation layer for staged island inference.

This module keeps public records in their proper evidentiary role:

* occurrence records document records near declared island buffers;
* environmental values document reproducible raster/vector extraction;
* photographs document trait annotations and measurement uncertainty.

None of these layers is a direct measurement of floral visitation, pollination
success, historical extinction, or selection. They must not be converted into a
pollinator-effectiveness parameter without a separate, reviewed observation
model.
"""

from __future__ import annotations

import csv
import math
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, Mapping


OCCURRENCE_BASES = frozenset(
    {
        "PRESERVED_SPECIMEN",
        "HUMAN_OBSERVATION",
        "MACHINE_OBSERVATION",
        "MATERIAL_SAMPLE",
        "LIVING_SPECIMEN",
        "OBSERVATION",
    }
)
PHOTO_REVIEW_STATES = frozenset({"candidate", "reviewed", "rejected"})
ENVIRONMENT_REVIEW_STATES = frozenset({"candidate", "reviewed", "rejected"})

OCCURRENCE_COLUMNS = (
    "record_id",
    "target_id",
    "scientific_name",
    "event_date",
    "decimal_latitude",
    "decimal_longitude",
    "coordinate_uncertainty_m",
    "basis_of_record",
    "dataset_key",
    "source_url",
    "identification_status",
    "review_status",
    "notes",
)
ISLAND_BUFFER_COLUMNS = (
    "island_id",
    "latitude",
    "longitude",
    "buffer_km",
    "geometry_source",
    "geometry_version",
    "notes",
)
ENVIRONMENT_COLUMNS = (
    "record_id",
    "island_id",
    "variable",
    "value",
    "unit",
    "source_name",
    "source_version",
    "source_locator",
    "extraction_method",
    "extraction_date",
    "review_status",
    "notes",
)
PHOTO_COLUMNS = (
    "annotation_id",
    "image_id",
    "island_id",
    "reported_taxon",
    "image_source_url",
    "image_license",
    "capture_date",
    "spot_present",
    "spot_fraction",
    "spot_position_relative",
    "image_quality",
    "annotator_id",
    "review_status",
    "notes",
)


@dataclass(frozen=True)
class IslandBuffer:
    island_id: str
    latitude: float
    longitude: float
    buffer_km: float
    geometry_source: str
    geometry_version: str
    notes: str

    def __post_init__(self) -> None:
        if not self.island_id:
            raise ValueError("island_id is required")
        if not -90.0 <= self.latitude <= 90.0:
            raise ValueError("latitude must lie in [-90, 90]")
        if not -180.0 <= self.longitude <= 180.0:
            raise ValueError("longitude must lie in [-180, 180]")
        if self.buffer_km <= 0.0:
            raise ValueError("buffer_km must be positive")
        if not self.geometry_source or not self.geometry_version:
            raise ValueError("geometry source and version are required")


@dataclass(frozen=True)
class OccurrenceRecord:
    record_id: str
    target_id: str
    scientific_name: str
    event_date: str
    decimal_latitude: float
    decimal_longitude: float
    coordinate_uncertainty_m: float | None
    basis_of_record: str
    dataset_key: str
    source_url: str
    identification_status: str
    review_status: str
    notes: str

    def __post_init__(self) -> None:
        if not self.record_id or not self.target_id or not self.scientific_name:
            raise ValueError("record_id, target_id, and scientific_name are required")
        if not -90.0 <= self.decimal_latitude <= 90.0:
            raise ValueError("decimal_latitude must lie in [-90, 90]")
        if not -180.0 <= self.decimal_longitude <= 180.0:
            raise ValueError("decimal_longitude must lie in [-180, 180]")
        if self.coordinate_uncertainty_m is not None and self.coordinate_uncertainty_m < 0.0:
            raise ValueError("coordinate_uncertainty_m must be nonnegative")
        if self.basis_of_record not in OCCURRENCE_BASES:
            raise ValueError("basis_of_record is not in the allowed vocabulary")
        if self.review_status not in PHOTO_REVIEW_STATES:
            raise ValueError("review_status must be candidate, reviewed, or rejected")
        if not self.dataset_key or not self.source_url:
            raise ValueError("dataset_key and source_url are required")


@dataclass(frozen=True)
class EnvironmentRecord:
    record_id: str
    island_id: str
    variable: str
    value: float
    unit: str
    source_name: str
    source_version: str
    source_locator: str
    extraction_method: str
    extraction_date: str
    review_status: str
    notes: str

    def __post_init__(self) -> None:
        if not self.record_id or not self.island_id or not self.variable:
            raise ValueError("record_id, island_id, and variable are required")
        if not math.isfinite(self.value):
            raise ValueError("environment value must be finite")
        if not self.unit or not self.source_name or not self.source_version:
            raise ValueError("unit and source provenance are required")
        if not self.source_locator or not self.extraction_method or not self.extraction_date:
            raise ValueError("source locator, extraction method, and date are required")
        if self.review_status not in ENVIRONMENT_REVIEW_STATES:
            raise ValueError("review_status must be candidate, reviewed, or rejected")


@dataclass(frozen=True)
class PhotoSpotAnnotation:
    annotation_id: str
    image_id: str
    island_id: str
    reported_taxon: str
    image_source_url: str
    image_license: str
    capture_date: str
    spot_present: bool | None
    spot_fraction: float | None
    spot_position_relative: float | None
    image_quality: float
    annotator_id: str
    review_status: str
    notes: str

    def __post_init__(self) -> None:
        if not self.annotation_id or not self.image_id or not self.island_id:
            raise ValueError("annotation_id, image_id, and island_id are required")
        if not self.reported_taxon or not self.image_source_url or not self.image_license:
            raise ValueError("taxon, source URL, and license are required")
        if not 0.0 <= self.image_quality <= 1.0:
            raise ValueError("image_quality must lie in [0, 1]")
        if self.spot_fraction is not None and not 0.0 <= self.spot_fraction <= 1.0:
            raise ValueError("spot_fraction must lie in [0, 1]")
        if self.spot_position_relative is not None and not 0.0 <= self.spot_position_relative <= 1.0:
            raise ValueError("spot_position_relative must lie in [0, 1]")
        if self.spot_present is False and self.spot_fraction not in (None, 0.0):
            raise ValueError("spot_fraction must be absent or zero when spots are absent")
        if self.review_status not in PHOTO_REVIEW_STATES:
            raise ValueError("review_status must be candidate, reviewed, or rejected")
        if not self.annotator_id:
            raise ValueError("annotator_id is required")


@dataclass(frozen=True)
class IslandOccurrenceSummary:
    island_id: str
    target_id: str
    reviewed_nearby_records: int
    distinct_datasets: int
    earliest_event_date: str | None
    latest_event_date: str | None
    documented_presence: bool
    absence_inference_permitted: bool
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class IslandPhotoSummary:
    island_id: str
    reviewed_annotations: int
    independent_annotators: int
    spot_present_annotations: int
    spot_absent_annotations: int
    image_weighted_spot_fraction: float | None
    agreement_ready: bool
    warnings: tuple[str, ...]


def _as_float(value: str, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} must be numeric") from error


def _optional_float(value: str, field: str) -> float | None:
    text = str(value or "").strip()
    return None if not text else _as_float(text, field)


def _as_bool_or_none(value: str, field: str) -> bool | None:
    text = str(value or "").strip().lower()
    if text in {"", "na", "not_assessable", "unknown"}:
        return None
    if text in {"1", "true", "yes", "present"}:
        return True
    if text in {"0", "false", "no", "absent"}:
        return False
    raise ValueError(f"{field} must be true, false, or not_assessable")


def haversine_km(latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float) -> float:
    """Great-circle distance used only for declared record-to-buffer assignment."""

    radius_km = 6371.0088
    lat_a = math.radians(latitude_a)
    lat_b = math.radians(latitude_b)
    delta_lat = lat_b - lat_a
    delta_lon = math.radians(longitude_b - longitude_a)
    value = math.sin(delta_lat / 2.0) ** 2 + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lon / 2.0) ** 2
    return radius_km * 2.0 * math.asin(math.sqrt(value))


def matching_islands(record: OccurrenceRecord, island_buffers: Iterable[IslandBuffer]) -> tuple[str, ...]:
    """Return island buffers containing a record; no match is interpreted as absence."""

    return tuple(
        island.island_id
        for island in island_buffers
        if haversine_km(record.decimal_latitude, record.decimal_longitude, island.latitude, island.longitude) <= island.buffer_km
    )


def summarize_occurrences(
    records: Iterable[OccurrenceRecord], island_buffers: Iterable[IslandBuffer]
) -> tuple[IslandOccurrenceSummary, ...]:
    """Summarize documented nearby records without estimating occupancy or absence."""

    buffers = tuple(island_buffers)
    reviewed = [row for row in records if row.review_status == "reviewed"]
    summaries: list[IslandOccurrenceSummary] = []
    target_ids = sorted({row.target_id for row in reviewed})
    for island in buffers:
        for target_id in target_ids:
            hits = [
                row for row in reviewed
                if row.target_id == target_id and island.island_id in matching_islands(row, buffers)
            ]
            dates = sorted(row.event_date for row in hits if row.event_date)
            warnings: list[str] = []
            if not hits:
                warnings.append("No reviewed nearby record; this is not evidence of absence.")
            if any(row.coordinate_uncertainty_m is None for row in hits):
                warnings.append("At least one record has unknown coordinate uncertainty.")
            summaries.append(
                IslandOccurrenceSummary(
                    island_id=island.island_id,
                    target_id=target_id,
                    reviewed_nearby_records=len(hits),
                    distinct_datasets=len({row.dataset_key for row in hits}),
                    earliest_event_date=dates[0] if dates else None,
                    latest_event_date=dates[-1] if dates else None,
                    documented_presence=bool(hits),
                    absence_inference_permitted=False,
                    warnings=tuple(warnings),
                )
            )
    return tuple(summaries)


def summarize_photo_annotations(annotations: Iterable[PhotoSpotAnnotation]) -> tuple[IslandPhotoSummary, ...]:
    """Summarize reviewed image annotations while preserving missing assessability."""

    rows = [row for row in annotations if row.review_status == "reviewed"]
    summaries: list[IslandPhotoSummary] = []
    for island_id in sorted({row.island_id for row in rows}):
        selected = [row for row in rows if row.island_id == island_id]
        present = sum(row.spot_present is True for row in selected)
        absent = sum(row.spot_present is False for row in selected)
        measurable = [row for row in selected if row.spot_fraction is not None]
        total_weight = sum(row.image_quality for row in measurable)
        weighted = None if total_weight == 0.0 else sum(row.image_quality * row.spot_fraction for row in measurable) / total_weight
        annotators = {row.annotator_id for row in selected}
        image_counts: dict[str, set[str]] = {}
        for row in selected:
            image_counts.setdefault(row.image_id, set()).add(row.annotator_id)
        agreement_ready = any(len(ids) >= 2 for ids in image_counts.values())
        warnings: list[str] = []
        if not agreement_ready:
            warnings.append("No image has two independent reviewed annotations.")
        if not measurable:
            warnings.append("No reviewed measurable spot fraction for this island.")
        summaries.append(
            IslandPhotoSummary(
                island_id=island_id,
                reviewed_annotations=len(selected),
                independent_annotators=len(annotators),
                spot_present_annotations=present,
                spot_absent_annotations=absent,
                image_weighted_spot_fraction=weighted,
                agreement_ready=agreement_ready,
                warnings=tuple(warnings),
            )
        )
    return tuple(summaries)


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def load_island_buffers(path: str | Path) -> tuple[IslandBuffer, ...]:
    return tuple(
        IslandBuffer(
            island_id=row["island_id"].strip(),
            latitude=_as_float(row["latitude"], "latitude"),
            longitude=_as_float(row["longitude"], "longitude"),
            buffer_km=_as_float(row["buffer_km"], "buffer_km"),
            geometry_source=row["geometry_source"].strip(),
            geometry_version=row["geometry_version"].strip(),
            notes=row.get("notes", "").strip(),
        )
        for row in read_csv_rows(path)
    )


def load_occurrences(path: str | Path) -> tuple[OccurrenceRecord, ...]:
    return tuple(
        OccurrenceRecord(
            record_id=row["record_id"].strip(),
            target_id=row["target_id"].strip(),
            scientific_name=row["scientific_name"].strip(),
            event_date=row.get("event_date", "").strip(),
            decimal_latitude=_as_float(row["decimal_latitude"], "decimal_latitude"),
            decimal_longitude=_as_float(row["decimal_longitude"], "decimal_longitude"),
            coordinate_uncertainty_m=_optional_float(row.get("coordinate_uncertainty_m", ""), "coordinate_uncertainty_m"),
            basis_of_record=row["basis_of_record"].strip(),
            dataset_key=row["dataset_key"].strip(),
            source_url=row["source_url"].strip(),
            identification_status=row.get("identification_status", "").strip(),
            review_status=row.get("review_status", "candidate").strip(),
            notes=row.get("notes", "").strip(),
        )
        for row in read_csv_rows(path)
    )


def load_environment(path: str | Path) -> tuple[EnvironmentRecord, ...]:
    return tuple(
        EnvironmentRecord(
            record_id=row["record_id"].strip(),
            island_id=row["island_id"].strip(),
            variable=row["variable"].strip(),
            value=_as_float(row["value"], "value"),
            unit=row["unit"].strip(),
            source_name=row["source_name"].strip(),
            source_version=row["source_version"].strip(),
            source_locator=row["source_locator"].strip(),
            extraction_method=row["extraction_method"].strip(),
            extraction_date=row["extraction_date"].strip(),
            review_status=row.get("review_status", "candidate").strip(),
            notes=row.get("notes", "").strip(),
        )
        for row in read_csv_rows(path)
    )


def load_photo_annotations(path: str | Path) -> tuple[PhotoSpotAnnotation, ...]:
    return tuple(
        PhotoSpotAnnotation(
            annotation_id=row["annotation_id"].strip(),
            image_id=row["image_id"].strip(),
            island_id=row["island_id"].strip(),
            reported_taxon=row["reported_taxon"].strip(),
            image_source_url=row["image_source_url"].strip(),
            image_license=row["image_license"].strip(),
            capture_date=row.get("capture_date", "").strip(),
            spot_present=_as_bool_or_none(row.get("spot_present", ""), "spot_present"),
            spot_fraction=_optional_float(row.get("spot_fraction", ""), "spot_fraction"),
            spot_position_relative=_optional_float(row.get("spot_position_relative", ""), "spot_position_relative"),
            image_quality=_as_float(row["image_quality"], "image_quality"),
            annotator_id=row["annotator_id"].strip(),
            review_status=row.get("review_status", "candidate").strip(),
            notes=row.get("notes", "").strip(),
        )
        for row in read_csv_rows(path)
    )


def write_public_observation_templates(directory: str | Path) -> tuple[Path, ...]:
    """Write schemas and the boundary contract for public evidence collection."""

    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    files = {
        "island_buffers.csv": ",".join(ISLAND_BUFFER_COLUMNS) + "\n",
        "occurrences.csv": ",".join(OCCURRENCE_COLUMNS) + "\n",
        "environment.csv": ",".join(ENVIRONMENT_COLUMNS) + "\n",
        "photo_spot_annotations.csv": ",".join(PHOTO_COLUMNS) + "\n",
        "README.md": public_observation_readme(),
    }
    paths = []
    for name, content in files.items():
        path = root / name
        path.write_text(content, encoding="utf-8")
        paths.append(path)
    return tuple(paths)


def public_observation_readme() -> str:
    return """# Public observation layer

## Purpose

This folder holds public evidence for the staged island analysis. It is not a
single pooled dataset. Each layer has its own observation process.

- `occurrences.csv`: documented records near declared island buffers.
- `environment.csv`: reproducibly extracted covariates such as CHELSA values.
- `photo_spot_annotations.csv`: independently reviewable spot annotations.
- `island_buffers.csv`: source-versioned island reference points/buffers.

## Strict interpretation rules

1. No occurrence within a buffer is evidence of documented presence only.
2. No occurrence record is not evidence of absence, visitation, or effectiveness.
3. A climate covariate is a competing explanatory variable, not a pollinator proxy.
4. A photo annotation is an observation with image and annotator error; it is not
   a population frequency unless sampling and coverage justify that claim.
5. A photo with unassessable spots must retain missingness rather than being
   labelled spot-absent.

## Recommended collection order

1. Download and retain raw GBIF/Darwin Core records with exact query metadata.
2. Map historical taxon names to the query taxon in a separate source claim.
3. Enter island buffers from a versioned GIS source.
4. Extract climate/topography at the same reference geometry, retaining raster
   version, extraction method, and date.
5. Independently annotate each usable flower image twice before aggregating
   spot fraction.

The resulting summaries inform scenario compatibility and sensitivity analyses.
They do not calibrate pollen transfer or establish the proposed history.
"""


def public_evidence_report(
    occurrences: Iterable[OccurrenceRecord],
    buffers: Iterable[IslandBuffer],
    photos: Iterable[PhotoSpotAnnotation],
    environment: Iterable[EnvironmentRecord],
) -> dict[str, object]:
    """Return JSON-serialisable coverage summaries without a causal score."""

    occurrence_rows = tuple(occurrences)
    buffer_rows = tuple(buffers)
    photo_rows = tuple(photos)
    environment_rows = tuple(environment)
    environment_by_island: dict[str, int] = {}
    for row in environment_rows:
        if row.review_status == "reviewed":
            environment_by_island[row.island_id] = environment_by_island.get(row.island_id, 0) + 1
    return {
        "occurrence_summaries": [asdict(row) for row in summarize_occurrences(occurrence_rows, buffer_rows)],
        "photo_summaries": [asdict(row) for row in summarize_photo_annotations(photo_rows)],
        "reviewed_environment_records_by_island": dict(sorted(environment_by_island.items())),
        "boundary": "Occurrence is availability evidence; photos are imperfect trait observations; neither is direct pollination effectiveness.",
    }
