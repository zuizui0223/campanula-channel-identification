from pathlib import Path

from channel_id.izu_raw_record_protocol import (
    CameraCalibrationClipRecord,
    CameraCalibrationRequirements,
    CameraWindowRecord,
    FruitRecord,
    IzuRawRecordBundle,
    PaternityCallRecord,
    PaternityValidationRecord,
    VisitAnnotationRecord,
    assess_camera_calibration_coverage,
    assess_handling_annotation_agreement,
    assess_paternity_validation,
    validate_izu_raw_record_bundle,
    write_izu_raw_record_templates,
)


def camera_window(
    window_id: str = "window-1",
    wind_class: str = "calm",
    light_class: str = "bright",
) -> CameraWindowRecord:
    return CameraWindowRecord(
        window_id=window_id,
        site_id="site-a",
        plant_id="plant-1",
        flower_id="flower-1",
        device_id="cam-1",
        started_at="2026-07-04T09:00:00+09:00",
        ended_at="2026-07-04T09:10:00+09:00",
        exposure_seconds=600.0,
        wind_class=wind_class,
        light_class=light_class,
        rain_present=False,
    )


def valid_bundle() -> IzuRawRecordBundle:
    return IzuRawRecordBundle(
        camera_windows=(camera_window(),),
        visit_annotations=(
            VisitAnnotationRecord(
                event_id="event-1",
                window_id="window-1",
                event_offset_seconds=120.0,
                primary_handling_label="legitimate",
                primary_scorer_id="scorer-a",
                secondary_handling_label="legitimate",
                secondary_scorer_id="scorer-b",
            ),
        ),
        calibration_clips=(
            CameraCalibrationClipRecord(
                clip_id="clip-1",
                window_id="window-1",
                clip_start_seconds=0.0,
                clip_duration_seconds=120.0,
                selection_method="random",
                primary_visit_count=3,
                reference_visit_count=4,
                primary_legitimate_count=2,
                reference_legitimate_count=3,
                primary_scorer_id="scorer-a",
                reference_scorer_id="scorer-b",
            ),
        ),
        fruits=(
            FruitRecord(
                fruit_id="fruit-1",
                site_id="site-a",
                maternal_id="plant-1",
                collection_date="2026-08-01",
                mature_seed_count=4,
                genotyped_seed_target=2,
                genotyped_seed_count=2,
            ),
        ),
        paternity_calls=(
            PaternityCallRecord("seed-1", "fruit-1", "outcross", "", 0.98, 2),
            PaternityCallRecord("seed-2", "fruit-1", "self", "", 0.97, 2),
        ),
        paternity_validation=(
            PaternityValidationRecord(
                "validation-1", "outcross", "outcross", "", "controlled_cross", 0.99
            ),
            PaternityValidationRecord(
                "validation-2", "self", "self", "", "controlled_cross", 0.99
            ),
        ),
    )


def test_valid_bundle_passes_link_and_count_validation() -> None:
    report = validate_izu_raw_record_bundle(valid_bundle())

    assert report.valid
    assert report.errors == ()


def test_validator_catches_unknown_links_unresolved_reason_and_count_mismatch() -> None:
    bundle = IzuRawRecordBundle(
        camera_windows=(camera_window(),),
        visit_annotations=(
            VisitAnnotationRecord(
                event_id="event-1",
                window_id="missing-window",
                event_offset_seconds=1.0,
                primary_handling_label="legitimate",
                primary_scorer_id="scorer-a",
            ),
        ),
        calibration_clips=(),
        fruits=(
            FruitRecord("fruit-1", "site-a", "plant-1", "2026-08-01", 3, 2, 2),
        ),
        paternity_calls=(
            PaternityCallRecord("seed-1", "fruit-1", "unresolved", "", 0.5, 1),
        ),
        paternity_validation=(),
    )

    report = validate_izu_raw_record_bundle(bundle)
    codes = {issue.code for issue in report.errors}

    assert not report.valid
    assert "unknown_window" in codes
    assert "missing_value" in codes
    assert "paternity_count_mismatch" in codes


def test_camera_calibration_coverage_flags_uncovered_observed_strata() -> None:
    windows = (
        camera_window("calm-bright", "calm", "bright"),
        camera_window("windy-low", "windy", "low_light"),
    )
    clips = (
        CameraCalibrationClipRecord(
            "clip-1",
            "calm-bright",
            0.0,
            60.0,
            "random",
            4,
            4,
            2,
            2,
            "scorer-a",
            "scorer-b",
        ),
    )

    report = assess_camera_calibration_coverage(
        windows,
        clips,
        CameraCalibrationRequirements(
            minimum_clips_per_stratum=1,
            minimum_reference_visits_per_stratum=4,
            minimum_reference_legitimate_events_per_stratum=2,
        ),
    )

    assert not report.complete
    assert [item.stratum_label for item in report.uncovered_strata] == ["windy|low_light"]


def test_handling_agreement_distinguishes_adjudicated_and_unresolved_disagreement() -> None:
    annotations = (
        VisitAnnotationRecord("e1", "w", 1.0, "legitimate", "a", "legitimate", "b"),
        VisitAnnotationRecord("e2", "w", 2.0, "legitimate", "a", "non_legitimate", "b", "legitimate"),
        VisitAnnotationRecord("e3", "w", 3.0, "legitimate", "a", "non_legitimate", "b"),
        VisitAnnotationRecord("e4", "w", 4.0, "legitimate", "a"),
    )

    report = assess_handling_annotation_agreement(annotations)

    assert report.double_scored_events == 3
    assert report.exact_agreements == 1
    assert report.adjudicated_events == 1
    assert report.unresolved_disagreements == 1
    assert report.exact_agreement_rate == 1 / 3


def test_paternity_validation_keeps_true_cross_types_separate() -> None:
    report = assess_paternity_validation(
        (
            PaternityValidationRecord("o1", "outcross", "unresolved", "low_coverage", "controlled", 0.1),
            PaternityValidationRecord("o2", "outcross", "outcross", "", "controlled", 0.9),
            PaternityValidationRecord("s1", "self", "self", "", "controlled", 0.9),
            PaternityValidationRecord("s2", "self", "self", "", "controlled", 0.9),
        )
    )

    assert report.summary_for("outcross").unresolved_rate == 0.5
    assert report.summary_for("self").unresolved_rate == 0.0
    assert report.outcross_minus_self_unresolved_rate == 0.5


def test_template_writer_outputs_all_csv_headers_and_protocol_readme(tmp_path: Path) -> None:
    written = write_izu_raw_record_templates(tmp_path)

    filenames = {path.name for path in written}
    assert {
        "camera_windows.csv",
        "visit_annotations.csv",
        "camera_calibration_clips.csv",
        "fruits.csv",
        "paternity_calls.csv",
        "paternity_validation.csv",
        "README.md",
    } == filenames
    assert (tmp_path / "camera_windows.csv").read_text(encoding="utf-8").startswith(
        "window_id,site_id,plant_id,flower_id"
    )
    assert "wind_class" in (tmp_path / "README.md").read_text(encoding="utf-8")
