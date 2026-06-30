import pytest

from channel_id.public_evidence import (
    IslandBuffer,
    OccurrenceRecord,
    PhotoSpotAnnotation,
    haversine_km,
    summarize_occurrences,
    summarize_photo_annotations,
)


def buffer() -> IslandBuffer:
    return IslandBuffer(
        island_id="oshima",
        latitude=34.7500,
        longitude=139.3600,
        buffer_km=10.0,
        geometry_source="example_versioned_geometry",
        geometry_version="v1",
        notes="Test fixture only.",
    )


def record(review_status: str = "reviewed") -> OccurrenceRecord:
    return OccurrenceRecord(
        record_id="gbif:1",
        target_id="bombus_ardens",
        scientific_name="Bombus ardens",
        event_date="1985-06-01",
        decimal_latitude=34.751,
        decimal_longitude=139.361,
        coordinate_uncertainty_m=100.0,
        basis_of_record="PRESERVED_SPECIMEN",
        dataset_key="dataset-1",
        source_url="https://www.gbif.org/occurrence/1",
        identification_status="accepted",
        review_status=review_status,
        notes="Test fixture only.",
    )


def annotation(image_id: str, annotator: str, spot_present: bool | None, fraction: float | None) -> PhotoSpotAnnotation:
    return PhotoSpotAnnotation(
        annotation_id=f"{image_id}-{annotator}",
        image_id=image_id,
        island_id="oshima",
        reported_taxon="Campanula microdonta",
        image_source_url="https://example.org/image",
        image_license="CC-BY",
        capture_date="2025-06-01",
        spot_present=spot_present,
        spot_fraction=fraction,
        spot_position_relative=0.5 if fraction is not None else None,
        image_quality=0.8,
        annotator_id=annotator,
        review_status="reviewed",
        notes="Test fixture only.",
    )


def test_documented_occurrence_never_creates_an_absence_inference() -> None:
    summary = summarize_occurrences([record()], [buffer()])

    assert len(summary) == 1
    assert summary[0].documented_presence
    assert not summary[0].absence_inference_permitted


def test_no_reviewed_record_is_not_rewritten_as_absence() -> None:
    summary = summarize_occurrences([record(review_status="candidate")], [buffer()])

    assert summary == ()


def test_photo_summary_requires_independent_annotation_for_agreement() -> None:
    single = summarize_photo_annotations([annotation("image-1", "a", True, 0.3)])
    paired = summarize_photo_annotations(
        [annotation("image-1", "a", True, 0.3), annotation("image-1", "b", True, 0.5)]
    )

    assert not single[0].agreement_ready
    assert paired[0].agreement_ready
    assert paired[0].image_weighted_spot_fraction == pytest.approx(0.4)


def test_unassessable_spots_stay_missing() -> None:
    summary = summarize_photo_annotations([annotation("image-2", "a", None, None)])

    assert summary[0].spot_present_annotations == 0
    assert summary[0].spot_absent_annotations == 0
    assert summary[0].image_weighted_spot_fraction is None


def test_haversine_distance_is_zero_for_same_coordinate() -> None:
    assert haversine_km(34.75, 139.36, 34.75, 139.36) == 0.0
