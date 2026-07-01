from pathlib import Path

from channel_id.empirical_evidence_lock import build_island_matrix, coverage_audit, render_empirical_evidence_markdown


DATA_DIR = Path(__file__).parents[1] / "data" / "two_breakpoint_evidence"


def test_matrix_keeps_oshima_mixed_mating_and_bagging_as_distinct_channels():
    rows = {row["island"]: row for row in build_island_matrix(DATA_DIR)}

    assert rows["Oshima"]["outcrossing_t_mean"] == 0.691
    assert rows["Oshima"]["bagged_capsule_set_percent"] == 11.3
    assert rows["Oshima"]["direct_pollinator_groups"] == "Bombus ardens;Ceratina spp.;Lasioglossum spp."
    assert rows["Oshima"]["main_pollinator_groups"] == "Bombus_ardens;Lasioglossum"


def test_kozu_and_kozusima_aliases_join_without_rewriting_source_rows():
    rows = {row["island"]: row for row in build_island_matrix(DATA_DIR)}

    assert "Kozushima" in rows
    assert rows["Kozushima"]["outcrossing_t_mean"] == 0.366
    assert rows["Kozushima"]["bagged_capsule_set_percent"] == 97.8


def test_coverage_keeps_missing_channels_explicit():
    coverage = {row.island: row for row in coverage_audit(DATA_DIR)}

    assert coverage["Miyake"].has_outcrossing
    assert coverage["Miyake"].has_bagging
    assert not coverage["Miyake"].has_common_garden_flower_size
    assert "No common-garden flower-length summary" in " ".join(coverage["Miyake"].warnings)


def test_report_states_noncausal_data_lock_boundary():
    text = render_empirical_evidence_markdown(DATA_DIR)

    assert "not a fitted causal model" in text
    assert "empty cell remains missing" in text
