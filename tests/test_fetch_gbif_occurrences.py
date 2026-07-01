import importlib.util
from pathlib import Path


def load_script_module():
    path = Path(__file__).parents[1] / "scripts" / "fetch_gbif_occurrences.py"
    spec = importlib.util.spec_from_file_location("fetch_gbif_occurrences", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gbif_urls_keep_the_declared_taxon_and_coordinate_filter():
    module = load_script_module()

    match = module.species_match_url("Bombus ardens")
    search = module.occurrence_search_url(1234, "JP", 300, 600)

    assert "Bombus+ardens" in match
    assert "taxon_key=1234" in search
    assert "has_coordinate=true" in search
    assert "country=JP" in search
    assert "limit=300" in search
    assert "offset=600" in search


def test_normalization_retains_candidate_review_status_and_no_effectiveness_claim():
    module = load_script_module()
    row = module.normalize_record(
        {
            "key": 99,
            "scientificName": "Bombus ardens",
            "eventDate": "1985-06-01",
            "decimalLatitude": 34.7,
            "decimalLongitude": 139.3,
            "basisOfRecord": "PRESERVED_SPECIMEN",
            "datasetKey": "dataset",
        },
        "bombus_ardens",
    )

    assert row["review_status"] == "candidate"
    assert row["target_id"] == "bombus_ardens"
    assert row["source_url"].endswith("/99")
    assert "effectiveness" not in row["notes"].lower()
