import json
from pathlib import Path
import subprocess
import sys


def test_two_breakpoint_evidence_cli_writes_templates_and_audits(tmp_path: Path) -> None:
    directory = tmp_path / "evidence"
    subprocess.run(
        [
            sys.executable,
            "scripts/audit_two_breakpoint_evidence.py",
            "--write-templates",
            str(directory),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    (directory / "sources.csv").write_text(
        "source_id,citation_or_title,stable_locator,source_type,source_status,retrieval_date,llm_extraction_status,human_review_status,notes\n"
        "source1,Example,https://example.org,primary_article,verified,2026-06-30,verified,reviewed,Checked\n",
        encoding="utf-8",
    )
    (directory / "claims.csv").write_text(
        "claim_id,source_id,claim_type,target_taxon,raw_taxon_name,accepted_taxon,geographic_unit,site_or_island,observation_start,observation_end,observation_method,value,value_unit,numerator,denominator_or_effort,uncertainty_lower,uncertainty_upper,source_locator,verbatim_basis,directness,causal_status,extraction_status,human_review_status,notes\n"
        "outcross,source1,outcrossing_rate,Campanula microdonta,Campanula microdonta,Campanula microdonta,island,oshima,1987-05-01,1987-06-01,multilocus estimate,0.85,proportion,not_available,20 families,0.70,0.95,Table 2,Reported estimate,direct_measurement,observational,verified,reviewed,Checked\n",
        encoding="utf-8",
    )
    (directory / "scenario_constraints.csv").write_text(
        "constraint_id,scenario_id,parameter_name,lower,upper,unit,assumption_class,supporting_claim_ids,rationale,status,notes\n"
        "outcross_anchor,ardens_replacement_loss,outcrossing_reference,0.70,0.95,proportion,observed_anchor,outcross,Reviewed range,declared,Reference only\n",
        encoding="utf-8",
    )
    output = tmp_path / "audit.json"

    subprocess.run(
        [
            sys.executable,
            "scripts/audit_two_breakpoint_evidence.py",
            "--input-dir",
            str(directory),
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    rendered = json.loads(output.read_text(encoding="utf-8"))
    assert rendered["anchor_eligible_claims"] == 1
    assert rendered["constraint_summaries"][0]["analysis_ready"]
