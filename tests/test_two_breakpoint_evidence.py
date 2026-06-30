from pathlib import Path

from channel_id.two_breakpoint_evidence import (
    audit_two_breakpoint_registries,
    write_two_breakpoint_registry_templates,
)


def source(source_id: str = "inoue_1988") -> dict[str, str]:
    return {
        "source_id": source_id,
        "citation_or_title": "Example source",
        "stable_locator": "https://example.org/source",
        "source_type": "primary_article",
        "source_status": "verified",
        "retrieval_date": "2026-06-30",
        "llm_extraction_status": "verified",
        "human_review_status": "reviewed",
        "notes": "Checked against original table.",
    }


def claim(
    claim_id: str = "outcross_oshima",
    claim_type: str = "outcrossing_rate",
    **overrides: str,
) -> dict[str, str]:
    row = {
        "claim_id": claim_id,
        "source_id": "inoue_1988",
        "claim_type": claim_type,
        "target_taxon": "Campanula microdonta",
        "raw_taxon_name": "Campanula microdonta",
        "accepted_taxon": "Campanula microdonta",
        "geographic_unit": "island",
        "site_or_island": "oshima",
        "observation_start": "1987-05-01",
        "observation_end": "1987-06-01",
        "observation_method": "multilocus outcrossing estimate",
        "value": "0.85",
        "value_unit": "proportion",
        "numerator": "not_available",
        "denominator_or_effort": "20 maternal families",
        "uncertainty_lower": "0.70",
        "uncertainty_upper": "0.95",
        "source_locator": "Table 2",
        "verbatim_basis": "Outcrossing estimate reported in Table 2.",
        "directness": "direct_measurement",
        "causal_status": "observational",
        "extraction_status": "verified",
        "human_review_status": "reviewed",
        "notes": "Do not treat as an autonomous-selfing estimate.",
    }
    row.update(overrides)
    return row


def constraint(**overrides: str) -> dict[str, str]:
    row = {
        "constraint_id": "outcross_anchor",
        "scenario_id": "ardens_replacement_loss",
        "parameter_name": "outcrossing_reference",
        "lower": "0.70",
        "upper": "0.95",
        "unit": "proportion",
        "assumption_class": "observed_anchor",
        "supporting_claim_ids": "outcross_oshima",
        "rationale": "Reviewed direct outcrossing estimate.",
        "status": "declared",
        "notes": "Reference only; not an effectiveness parameter.",
    }
    row.update(overrides)
    return row


def summary_by_id(report, record_id: str):
    for collection in (
        report.source_summaries,
        report.claim_summaries,
        report.constraint_summaries,
    ):
        for summary in collection:
            if summary.record_id == record_id:
                return summary
    raise AssertionError(record_id)


def test_verified_direct_outcrossing_claim_can_anchor_a_matching_constraint() -> None:
    report = audit_two_breakpoint_registries(
        [source()], [claim()], [constraint()]
    )

    assert summary_by_id(report, "outcross_oshima").analysis_ready
    assert summary_by_id(report, "outcross_oshima").observed_anchor_eligible
    assert summary_by_id(report, "outcross_anchor").analysis_ready
    assert report.anchor_eligible_claims == 1


def test_llm_candidate_cannot_become_observed_anchor() -> None:
    report = audit_two_breakpoint_registries(
        [source()],
        [claim(extraction_status="candidate", human_review_status="not_reviewed")],
        [constraint()],
    )

    claim_summary = summary_by_id(report, "outcross_oshima")
    constraint_summary = summary_by_id(report, "outcross_anchor")
    assert not claim_summary.observed_anchor_eligible
    assert not constraint_summary.analysis_ready
    assert "supporting claim is not eligible" in " ".join(constraint_summary.warnings)


def test_pollinator_occurrence_cannot_calibrate_effectiveness() -> None:
    occurrence = claim(
        claim_id="ardens_occurrence",
        claim_type="occurrence_record",
        observation_method="georeferenced occurrence record",
        value="1",
        value_unit="record",
        denominator_or_effort="not_available",
        directness="contextual_availability",
    )
    effect_constraint = constraint(
        constraint_id="ardens_effect",
        parameter_name="ardens_effective_outcross_efficiency",
        supporting_claim_ids="ardens_occurrence",
    )

    report = audit_two_breakpoint_registries([source()], [occurrence], [effect_constraint])

    assert not summary_by_id(report, "ardens_occurrence").observed_anchor_eligible
    assert not summary_by_id(report, "ardens_effect").analysis_ready


def test_non_detection_requires_effort_and_is_not_absence() -> None:
    non_detection = claim(
        claim_id="ardens_not_detected",
        claim_type="pollinator_non_detection",
        observation_method="island checklist",
        value="not_available",
        value_unit="not_available",
        denominator_or_effort="",
        directness="contextual_availability",
    )
    report = audit_two_breakpoint_registries([source()], [non_detection], [])

    warnings = " ".join(summary_by_id(report, "ardens_not_detected").warnings)
    assert "non-detection requires denominator_or_effort" in warnings


def test_sensitivity_constraint_must_not_disguise_claims_as_calibration() -> None:
    report = audit_two_breakpoint_registries(
        [source()],
        [claim()],
        [
            constraint(
                constraint_id="small_bee_efficiency",
                parameter_name="small_bee_effective_outcross_efficiency",
                lower="0.0",
                upper="1.0",
                assumption_class="sensitivity_only",
                supporting_claim_ids="outcross_oshima",
            )
        ],
    )

    warnings = " ".join(summary_by_id(report, "small_bee_efficiency").warnings)
    assert "must not present claim IDs as calibration" in warnings


def test_templates_include_source_claim_constraint_and_llm_contract(tmp_path: Path) -> None:
    paths = write_two_breakpoint_registry_templates(tmp_path)

    assert {path.name for path in paths} == {
        "sources.csv",
        "claims.csv",
        "scenario_constraints.csv",
        "README.md",
        "llm_extraction_prompt.md",
    }
    prompt = (tmp_path / "llm_extraction_prompt.md").read_text(encoding="utf-8")
    assert "not_reported" in prompt
    assert "not a visitation" in prompt
