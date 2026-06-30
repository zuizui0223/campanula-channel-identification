"""Raw-record schema and calibration audits for an Izu field study.

The virtual field-stress tests show why island-level totals are not enough for
an eventual empirical analysis: camera detection can vary with wind/light,
legitimate contacts can be differently detectable, and parentage resolution can
vary by cross type.  This module defines the minimum *row-level* record
architecture needed to retain those effects rather than averaging them away.

It intentionally does not fit a hierarchical model.  Its responsibilities are:

* write stable CSV templates for field/laboratory records;
* validate identifiers, count accounting, and cross-table links;
* audit whether camera calibration clips cover every observed wind × light
  stratum;
* audit double-scored legitimate-handling annotations;
* summarise external parentage-validation outcomes separately for known
  outcrossed and selfed seeds.

The numerical calibration thresholds are protocol defaults, not universal
biological requirements.  They are designed to make missing calibration visible
before an idealised pooled likelihood is used on field data.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping, Sequence


HANDLING_LABELS = frozenset({"legitimate", "non_legitimate", "uncertain", "not_assessable"})
PARENTAGE_OUTCOMES = frozenset({"outcross", "self", "unresolved"})
TRUE_CROSS_TYPES = frozenset({"outcross", "self"})
UNRESOLVED_REASONS = frozenset(
    {
        "low_dna_yield",
        "low_coverage",
        "ambiguous_parentage",
        "no_candidate_parent",
        "contamination",
        "technical_failure",
        "other",
    }
)
WIND_CLASSES = frozenset({"calm", "breezy", "windy", "unknown"})
LIGHT_CLASSES = frozenset({"bright", "shade", "low_light", "backlit", "night", "unknown"})
CALIBRATION_SELECTION_METHODS = frozenset({"random", "stratified_random", "targeted"})


@dataclass(frozen=True)
class CameraWindowRecord:
    """One camera exposure interval on one focal flower.

    ``exposure_seconds`` must represent usable observation time, not nominal
    deployment time.  Interrupted, blurred, or obstructed periods therefore
    need to be excluded before this row is finalised.
    """

    window_id: str
    site_id: str
    plant_id: str
    flower_id: str
    device_id: str
    started_at: str
    ended_at: str
    exposure_seconds: float
    wind_class: str
    light_class: str
    rain_present: bool
    field_notes: str = ""


@dataclass(frozen=True)
class VisitAnnotationRecord:
    """One detected visit event and its primary/secondary handling labels.

    Secondary labels are optional for ordinary events, but a calibration subset
    should contain independent second scoring.  ``adjudicated_handling_label``
    is filled only when two scorers disagree or a formal adjudication is made.
    """

    event_id: str
    window_id: str
    event_offset_seconds: float
    primary_handling_label: str
    primary_scorer_id: str
    secondary_handling_label: str = ""
    secondary_scorer_id: str = ""
    adjudicated_handling_label: str = ""
    event_notes: str = ""


@dataclass(frozen=True)
class CameraCalibrationClipRecord:
    """A preselected clip used to estimate detection and handling-label quality.

    The reference scorer should use the best available source material and work
    independently of the primary scorer.  This table stores count-level audits;
    event-level double scoring belongs in :class:`VisitAnnotationRecord`.
    """

    clip_id: str
    window_id: str
    clip_start_seconds: float
    clip_duration_seconds: float
    selection_method: str
    primary_visit_count: int
    reference_visit_count: int
    primary_legitimate_count: int
    reference_legitimate_count: int
    primary_scorer_id: str
    reference_scorer_id: str
    audit_notes: str = ""


@dataclass(frozen=True)
class FruitRecord:
    """One fruit from a known maternal plant, retained through seed processing."""

    fruit_id: str
    site_id: str
    maternal_id: str
    collection_date: str
    mature_seed_count: int
    genotyped_seed_target: int
    genotyped_seed_count: int
    fruit_notes: str = ""


@dataclass(frozen=True)
class PaternityCallRecord:
    """One genotyped mature seed and its paternity-call result."""

    seed_id: str
    fruit_id: str
    called_outcome: str
    unresolved_reason: str
    call_confidence: float
    genotype_replicate_count: int
    call_notes: str = ""


@dataclass(frozen=True)
class PaternityValidationRecord:
    """One external validation seed with known true cross type.

    The true class may come from a controlled cross, an independently verified
    high-confidence panel, or another prespecified validation source.  It must
    not be inferred solely from the call being evaluated.
    """

    validation_seed_id: str
    true_cross_type: str
    called_outcome: str
    unresolved_reason: str
    validation_source: str
    call_confidence: float
    validation_notes: str = ""


@dataclass(frozen=True)
class IzuRawRecordBundle:
    """The six linked field/laboratory tables used by the protocol."""

    camera_windows: tuple[CameraWindowRecord, ...]
    visit_annotations: tuple[VisitAnnotationRecord, ...]
    calibration_clips: tuple[CameraCalibrationClipRecord, ...]
    fruits: tuple[FruitRecord, ...]
    paternity_calls: tuple[PaternityCallRecord, ...]
    paternity_validation: tuple[PaternityValidationRecord, ...]


@dataclass(frozen=True)
class RawRecordValidationIssue:
    """One actionable schema or accounting issue."""

    severity: str
    code: str
    message: str
    record_id: str = ""


@dataclass(frozen=True)
class RawRecordValidationReport:
    """Validation output with independent errors and warnings."""

    issues: tuple[RawRecordValidationIssue, ...]

    @property
    def errors(self) -> tuple[RawRecordValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def warnings(self) -> tuple[RawRecordValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "warning")

    @property
    def valid(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class CameraCalibrationRequirements:
    """Minimum coverage targets per observed wind × light stratum."""

    minimum_clips_per_stratum: int = 5
    minimum_reference_visits_per_stratum: int = 20
    minimum_reference_legitimate_events_per_stratum: int = 10

    def __post_init__(self) -> None:
        for name, value in (
            ("minimum_clips_per_stratum", self.minimum_clips_per_stratum),
            ("minimum_reference_visits_per_stratum", self.minimum_reference_visits_per_stratum),
            (
                "minimum_reference_legitimate_events_per_stratum",
                self.minimum_reference_legitimate_events_per_stratum,
            ),
        ):
            if value < 0:
                raise ValueError(f"{name} must be non-negative")


@dataclass(frozen=True)
class CameraCalibrationStratumCoverage:
    """Calibration coverage for one observed wind × light stratum."""

    wind_class: str
    light_class: str
    observation_windows: int
    calibration_clips: int
    reference_visits: int
    reference_legitimate_events: int
    requirements: CameraCalibrationRequirements

    @property
    def covered(self) -> bool:
        return (
            self.calibration_clips >= self.requirements.minimum_clips_per_stratum
            and self.reference_visits >= self.requirements.minimum_reference_visits_per_stratum
            and self.reference_legitimate_events
            >= self.requirements.minimum_reference_legitimate_events_per_stratum
        )

    @property
    def stratum_label(self) -> str:
        return f"{self.wind_class}|{self.light_class}"


@dataclass(frozen=True)
class CameraCalibrationCoverageReport:
    """Coverage of every observed camera-condition stratum."""

    strata: tuple[CameraCalibrationStratumCoverage, ...]

    @property
    def uncovered_strata(self) -> tuple[CameraCalibrationStratumCoverage, ...]:
        return tuple(stratum for stratum in self.strata if not stratum.covered)

    @property
    def complete(self) -> bool:
        return not self.uncovered_strata


@dataclass(frozen=True)
class HandlingAgreementReport:
    """Agreement among independently double-scored visit annotations."""

    double_scored_events: int
    exact_agreements: int
    adjudicated_events: int
    unresolved_disagreements: int

    @property
    def exact_agreement_rate(self) -> float | None:
        if self.double_scored_events == 0:
            return None
        return self.exact_agreements / self.double_scored_events


@dataclass(frozen=True)
class PaternityValidationClassSummary:
    """Observed parentage-call behaviour within a known true cross type."""

    true_cross_type: str
    total_validation_seeds: int
    outcross_calls: int
    self_calls: int
    unresolved_calls: int

    @property
    def unresolved_rate(self) -> float | None:
        if self.total_validation_seeds == 0:
            return None
        return self.unresolved_calls / self.total_validation_seeds

    @property
    def resolved_rate(self) -> float | None:
        if self.total_validation_seeds == 0:
            return None
        return 1.0 - self.unresolved_rate


@dataclass(frozen=True)
class PaternityValidationReport:
    """Parentage validation separated by known outcrossed versus selfed seeds."""

    by_true_cross_type: tuple[PaternityValidationClassSummary, ...]

    def summary_for(self, true_cross_type: str) -> PaternityValidationClassSummary:
        for summary in self.by_true_cross_type:
            if summary.true_cross_type == true_cross_type:
                return summary
        raise KeyError(f"no validation summary for {true_cross_type}")

    @property
    def outcross_minus_self_unresolved_rate(self) -> float | None:
        outcross = self.summary_for("outcross").unresolved_rate
        selfed = self.summary_for("self").unresolved_rate
        if outcross is None or selfed is None:
            return None
        return outcross - selfed


CSV_TEMPLATE_HEADERS: Mapping[str, tuple[str, ...]] = {
    "camera_windows.csv": (
        "window_id",
        "site_id",
        "plant_id",
        "flower_id",
        "device_id",
        "started_at",
        "ended_at",
        "exposure_seconds",
        "wind_class",
        "light_class",
        "rain_present",
        "field_notes",
    ),
    "visit_annotations.csv": (
        "event_id",
        "window_id",
        "event_offset_seconds",
        "primary_handling_label",
        "primary_scorer_id",
        "secondary_handling_label",
        "secondary_scorer_id",
        "adjudicated_handling_label",
        "event_notes",
    ),
    "camera_calibration_clips.csv": (
        "clip_id",
        "window_id",
        "clip_start_seconds",
        "clip_duration_seconds",
        "selection_method",
        "primary_visit_count",
        "reference_visit_count",
        "primary_legitimate_count",
        "reference_legitimate_count",
        "primary_scorer_id",
        "reference_scorer_id",
        "audit_notes",
    ),
    "fruits.csv": (
        "fruit_id",
        "site_id",
        "maternal_id",
        "collection_date",
        "mature_seed_count",
        "genotyped_seed_target",
        "genotyped_seed_count",
        "fruit_notes",
    ),
    "paternity_calls.csv": (
        "seed_id",
        "fruit_id",
        "called_outcome",
        "unresolved_reason",
        "call_confidence",
        "genotype_replicate_count",
        "call_notes",
    ),
    "paternity_validation.csv": (
        "validation_seed_id",
        "true_cross_type",
        "called_outcome",
        "unresolved_reason",
        "validation_source",
        "call_confidence",
        "validation_notes",
    ),
}


def _is_nonempty(value: str) -> bool:
    return bool(value and value.strip())


def _parse_iso_datetime(value: str) -> datetime | None:
    if not _is_nonempty(value):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_iso_date(value: str) -> bool:
    if not _is_nonempty(value):
        return False
    try:
        datetime.fromisoformat(value)
    except ValueError:
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            return False
    return True


def _append_issue(
    issues: list[RawRecordValidationIssue],
    severity: str,
    code: str,
    message: str,
    record_id: str = "",
) -> None:
    issues.append(RawRecordValidationIssue(severity, code, message, record_id))


def _check_unique_ids(
    records: Iterable[object],
    attribute: str,
    table_name: str,
    issues: list[RawRecordValidationIssue],
) -> None:
    seen: set[str] = set()
    for record in records:
        identifier = getattr(record, attribute)
        if not _is_nonempty(identifier):
            _append_issue(issues, "error", "missing_id", f"{table_name} has an empty {attribute}")
            continue
        if identifier in seen:
            _append_issue(
                issues,
                "error",
                "duplicate_id",
                f"{table_name} repeats {attribute}={identifier}",
                identifier,
            )
        seen.add(identifier)


def _check_label(
    value: str,
    allowed: frozenset[str],
    field: str,
    record_id: str,
    issues: list[RawRecordValidationIssue],
    allow_empty: bool = False,
) -> None:
    if not _is_nonempty(value):
        if not allow_empty:
            _append_issue(issues, "error", "missing_value", f"{field} is required", record_id)
        return
    if value not in allowed:
        _append_issue(
            issues,
            "error",
            "invalid_category",
            f"{field}={value!r} is not an allowed value",
            record_id,
        )


def validate_izu_raw_record_bundle(bundle: IzuRawRecordBundle) -> RawRecordValidationReport:
    """Validate links, accounting, and key calibration fields across all tables."""

    issues: list[RawRecordValidationIssue] = []
    _check_unique_ids(bundle.camera_windows, "window_id", "camera_windows", issues)
    _check_unique_ids(bundle.visit_annotations, "event_id", "visit_annotations", issues)
    _check_unique_ids(bundle.calibration_clips, "clip_id", "camera_calibration_clips", issues)
    _check_unique_ids(bundle.fruits, "fruit_id", "fruits", issues)
    _check_unique_ids(bundle.paternity_calls, "seed_id", "paternity_calls", issues)
    _check_unique_ids(bundle.paternity_validation, "validation_seed_id", "paternity_validation", issues)

    windows = {record.window_id: record for record in bundle.camera_windows if _is_nonempty(record.window_id)}
    fruits = {record.fruit_id: record for record in bundle.fruits if _is_nonempty(record.fruit_id)}

    for window in bundle.camera_windows:
        record_id = window.window_id
        for field in ("site_id", "plant_id", "flower_id", "device_id"):
            if not _is_nonempty(getattr(window, field)):
                _append_issue(issues, "error", "missing_value", f"camera window requires {field}", record_id)
        started = _parse_iso_datetime(window.started_at)
        ended = _parse_iso_datetime(window.ended_at)
        if started is None or ended is None:
            _append_issue(
                issues,
                "error",
                "invalid_timestamp",
                "started_at and ended_at must be ISO-8601 timestamps",
                record_id,
            )
        elif ended <= started:
            _append_issue(issues, "error", "time_order", "ended_at must follow started_at", record_id)
        if window.exposure_seconds <= 0.0:
            _append_issue(issues, "error", "invalid_exposure", "exposure_seconds must be positive", record_id)
        _check_label(window.wind_class, WIND_CLASSES, "wind_class", record_id, issues)
        _check_label(window.light_class, LIGHT_CLASSES, "light_class", record_id, issues)

    for annotation in bundle.visit_annotations:
        record_id = annotation.event_id
        window = windows.get(annotation.window_id)
        if window is None:
            _append_issue(
                issues,
                "error",
                "unknown_window",
                f"visit annotation references unknown window_id={annotation.window_id}",
                record_id,
            )
        elif not 0.0 <= annotation.event_offset_seconds <= window.exposure_seconds:
            _append_issue(
                issues,
                "error",
                "event_outside_exposure",
                "event_offset_seconds must lie within the usable camera exposure",
                record_id,
            )
        _check_label(annotation.primary_handling_label, HANDLING_LABELS, "primary_handling_label", record_id, issues)
        if not _is_nonempty(annotation.primary_scorer_id):
            _append_issue(issues, "error", "missing_value", "primary_scorer_id is required", record_id)
        has_secondary_label = _is_nonempty(annotation.secondary_handling_label)
        has_secondary_scorer = _is_nonempty(annotation.secondary_scorer_id)
        if has_secondary_label != has_secondary_scorer:
            _append_issue(
                issues,
                "error",
                "incomplete_double_score",
                "secondary handling label and scorer ID must be supplied together",
                record_id,
            )
        if has_secondary_label:
            _check_label(
                annotation.secondary_handling_label,
                HANDLING_LABELS,
                "secondary_handling_label",
                record_id,
                issues,
            )
            if annotation.secondary_scorer_id == annotation.primary_scorer_id:
                _append_issue(
                    issues,
                    "error",
                    "nonindependent_double_score",
                    "primary and secondary scorer IDs must differ",
                    record_id,
                )
        if _is_nonempty(annotation.adjudicated_handling_label):
            _check_label(
                annotation.adjudicated_handling_label,
                HANDLING_LABELS,
                "adjudicated_handling_label",
                record_id,
                issues,
            )
        if annotation.primary_handling_label in {"uncertain", "not_assessable"}:
            _append_issue(
                issues,
                "warning",
                "uncertain_handling",
                "event has no directly usable binary handling label; retain it but do not silently coerce it",
                record_id,
            )

    for clip in bundle.calibration_clips:
        record_id = clip.clip_id
        window = windows.get(clip.window_id)
        if window is None:
            _append_issue(
                issues,
                "error",
                "unknown_window",
                f"calibration clip references unknown window_id={clip.window_id}",
                record_id,
            )
        elif (
            clip.clip_start_seconds < 0.0
            or clip.clip_duration_seconds <= 0.0
            or clip.clip_start_seconds + clip.clip_duration_seconds > window.exposure_seconds
        ):
            _append_issue(
                issues,
                "error",
                "clip_outside_exposure",
                "calibration clip must lie within the usable camera exposure",
                record_id,
            )
        _check_label(clip.selection_method, CALIBRATION_SELECTION_METHODS, "selection_method", record_id, issues)
        for field in (
            "primary_visit_count",
            "reference_visit_count",
            "primary_legitimate_count",
            "reference_legitimate_count",
        ):
            if getattr(clip, field) < 0:
                _append_issue(issues, "error", "negative_count", f"{field} must be non-negative", record_id)
        if clip.primary_legitimate_count > clip.primary_visit_count:
            _append_issue(
                issues,
                "error",
                "invalid_count_partition",
                "primary_legitimate_count cannot exceed primary_visit_count",
                record_id,
            )
        if clip.reference_legitimate_count > clip.reference_visit_count:
            _append_issue(
                issues,
                "error",
                "invalid_count_partition",
                "reference_legitimate_count cannot exceed reference_visit_count",
                record_id,
            )
        if not _is_nonempty(clip.primary_scorer_id) or not _is_nonempty(clip.reference_scorer_id):
            _append_issue(issues, "error", "missing_value", "both calibration scorer IDs are required", record_id)
        elif clip.primary_scorer_id == clip.reference_scorer_id:
            _append_issue(
                issues,
                "error",
                "nonindependent_calibration",
                "primary and reference calibration scorers must differ",
                record_id,
            )

    paternity_by_fruit: Counter[str] = Counter()
    for fruit in bundle.fruits:
        record_id = fruit.fruit_id
        for field in ("site_id", "maternal_id"):
            if not _is_nonempty(getattr(fruit, field)):
                _append_issue(issues, "error", "missing_value", f"fruit requires {field}", record_id)
        if not _parse_iso_date(fruit.collection_date):
            _append_issue(
                issues,
                "error",
                "invalid_date",
                "collection_date must be YYYY-MM-DD or an ISO-8601 timestamp",
                record_id,
            )
        for field in ("mature_seed_count", "genotyped_seed_target", "genotyped_seed_count"):
            if getattr(fruit, field) < 0:
                _append_issue(issues, "error", "negative_count", f"{field} must be non-negative", record_id)
        if fruit.genotyped_seed_count > fruit.mature_seed_count:
            _append_issue(
                issues,
                "error",
                "genotype_exceeds_mature",
                "genotyped_seed_count cannot exceed mature_seed_count",
                record_id,
            )
        if fruit.genotyped_seed_count > fruit.genotyped_seed_target:
            _append_issue(
                issues,
                "warning",
                "genotype_exceeds_target",
                "genotyped_seed_count exceeds the recorded target; verify the field/lab target",
                record_id,
            )

    for call in bundle.paternity_calls:
        record_id = call.seed_id
        if call.fruit_id not in fruits:
            _append_issue(
                issues,
                "error",
                "unknown_fruit",
                f"paternity call references unknown fruit_id={call.fruit_id}",
                record_id,
            )
        else:
            paternity_by_fruit[call.fruit_id] += 1
        _check_label(call.called_outcome, PARENTAGE_OUTCOMES, "called_outcome", record_id, issues)
        _validate_unresolved_reason(
            call.called_outcome,
            call.unresolved_reason,
            record_id,
            issues,
        )
        if not 0.0 <= call.call_confidence <= 1.0:
            _append_issue(
                issues,
                "error",
                "invalid_confidence",
                "call_confidence must lie in [0, 1]",
                record_id,
            )
        if call.genotype_replicate_count < 1:
            _append_issue(
                issues,
                "error",
                "invalid_replicate_count",
                "genotype_replicate_count must be at least one",
                record_id,
            )

    for fruit_id, fruit in fruits.items():
        observed_calls = paternity_by_fruit[fruit_id]
        if observed_calls != fruit.genotyped_seed_count:
            _append_issue(
                issues,
                "error",
                "paternity_count_mismatch",
                f"fruit records genotyped_seed_count={fruit.genotyped_seed_count} but has {observed_calls} paternity rows",
                fruit_id,
            )

    for validation in bundle.paternity_validation:
        record_id = validation.validation_seed_id
        _check_label(validation.true_cross_type, TRUE_CROSS_TYPES, "true_cross_type", record_id, issues)
        _check_label(validation.called_outcome, PARENTAGE_OUTCOMES, "called_outcome", record_id, issues)
        _validate_unresolved_reason(
            validation.called_outcome,
            validation.unresolved_reason,
            record_id,
            issues,
        )
        if not _is_nonempty(validation.validation_source):
            _append_issue(
                issues,
                "error",
                "missing_value",
                "validation_source is required for externally known cross type",
                record_id,
            )
        if not 0.0 <= validation.call_confidence <= 1.0:
            _append_issue(
                issues,
                "error",
                "invalid_confidence",
                "call_confidence must lie in [0, 1]",
                record_id,
            )

    return RawRecordValidationReport(tuple(issues))


def _validate_unresolved_reason(
    called_outcome: str,
    unresolved_reason: str,
    record_id: str,
    issues: list[RawRecordValidationIssue],
) -> None:
    has_reason = _is_nonempty(unresolved_reason)
    if called_outcome == "unresolved":
        _check_label(unresolved_reason, UNRESOLVED_REASONS, "unresolved_reason", record_id, issues)
    elif has_reason:
        _append_issue(
            issues,
            "warning",
            "reason_on_resolved_call",
            "unresolved_reason should be empty when called_outcome is resolved",
            record_id,
        )


def camera_calibration_stratum(window: CameraWindowRecord) -> tuple[str, str]:
    """Return the wind × light stratum used for calibration coverage."""

    return window.wind_class, window.light_class


def assess_camera_calibration_coverage(
    camera_windows: Sequence[CameraWindowRecord],
    calibration_clips: Sequence[CameraCalibrationClipRecord],
    requirements: CameraCalibrationRequirements = CameraCalibrationRequirements(),
) -> CameraCalibrationCoverageReport:
    """Audit calibration coverage for every actually observed condition stratum."""

    windows = {window.window_id: window for window in camera_windows}
    observed_windows: Counter[tuple[str, str]] = Counter(
        camera_calibration_stratum(window) for window in camera_windows
    )
    clip_count: Counter[tuple[str, str]] = Counter()
    reference_visits: Counter[tuple[str, str]] = Counter()
    reference_legitimate: Counter[tuple[str, str]] = Counter()
    for clip in calibration_clips:
        window = windows.get(clip.window_id)
        if window is None:
            continue
        stratum = camera_calibration_stratum(window)
        clip_count[stratum] += 1
        reference_visits[stratum] += clip.reference_visit_count
        reference_legitimate[stratum] += clip.reference_legitimate_count
    return CameraCalibrationCoverageReport(
        tuple(
            CameraCalibrationStratumCoverage(
                wind_class=wind,
                light_class=light,
                observation_windows=count,
                calibration_clips=clip_count[(wind, light)],
                reference_visits=reference_visits[(wind, light)],
                reference_legitimate_events=reference_legitimate[(wind, light)],
                requirements=requirements,
            )
            for (wind, light), count in sorted(observed_windows.items())
        )
    )


def assess_handling_annotation_agreement(
    annotations: Sequence[VisitAnnotationRecord],
) -> HandlingAgreementReport:
    """Summarise independent double scoring of legitimate-handling labels."""

    double_scored = 0
    agreements = 0
    adjudicated = 0
    unresolved_disagreements = 0
    for annotation in annotations:
        if not _is_nonempty(annotation.secondary_handling_label):
            continue
        double_scored += 1
        if annotation.primary_handling_label == annotation.secondary_handling_label:
            agreements += 1
        elif _is_nonempty(annotation.adjudicated_handling_label):
            adjudicated += 1
        else:
            unresolved_disagreements += 1
    return HandlingAgreementReport(
        double_scored_events=double_scored,
        exact_agreements=agreements,
        adjudicated_events=adjudicated,
        unresolved_disagreements=unresolved_disagreements,
    )


def assess_paternity_validation(
    validation_records: Sequence[PaternityValidationRecord],
) -> PaternityValidationReport:
    """Summarise parentage-call outcomes separately for known seed classes."""

    grouped: dict[str, Counter[str]] = {
        "outcross": Counter(),
        "self": Counter(),
    }
    for record in validation_records:
        if record.true_cross_type not in grouped:
            continue
        grouped[record.true_cross_type]["total"] += 1
        grouped[record.true_cross_type][record.called_outcome] += 1
    return PaternityValidationReport(
        tuple(
            PaternityValidationClassSummary(
                true_cross_type=true_cross_type,
                total_validation_seeds=counts["total"],
                outcross_calls=counts["outcross"],
                self_calls=counts["self"],
                unresolved_calls=counts["unresolved"],
            )
            for true_cross_type, counts in grouped.items()
        )
    )


def write_izu_raw_record_templates(output_directory: str | Path) -> tuple[Path, ...]:
    """Write empty CSV templates and a concise protocol README to a directory."""

    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for filename, headers in CSV_TEMPLATE_HEADERS.items():
        path = directory / filename
        with path.open("w", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerow(headers)
        written.append(path)
    readme = directory / "README.md"
    readme.write_text(field_template_readme(), encoding="utf-8")
    written.append(readme)
    return tuple(written)


def field_template_readme() -> str:
    """Return the portable README packaged with blank field templates."""

    return """# Izu raw-record protocol templates

These files preserve the replicate identifiers needed to estimate or calibrate
camera detection, handling labels, seed fate, and parentage resolution later.
They are not six independent ledgers: IDs must link across tables.

## Required links

```text
camera_windows.window_id
  -> visit_annotations.window_id
  -> camera_calibration_clips.window_id

fruits.fruit_id
  -> paternity_calls.fruit_id
```

## Calibration subset

Select camera calibration clips before interpretation, covering every observed
`wind_class × light_class` stratum.  Use an independent reference scorer.  Add a
second scorer to a prespecified subset of visit annotations, especially events
near the legitimate/non-legitimate boundary.

For paternity validation, `paternity_validation.csv` must contain seeds with a
known true cross type from an external source. Record unresolved reasons even
when a call fails; a blank failure reason makes cross-type-dependent resolution
bias impossible to diagnose.

## Canonical categorical values

```text
wind_class: calm | breezy | windy | unknown
light_class: bright | shade | low_light | backlit | night | unknown
handling: legitimate | non_legitimate | uncertain | not_assessable
called_outcome: outcross | self | unresolved
```

Use ISO timestamps with time zone where possible, e.g.
`2026-07-04T09:30:00+09:00`.
"""
