import importlib.util
from pathlib import Path


def load_module():
    path = Path(__file__).parents[1] / "scripts" / "fetch_study_locality_geocoding_candidates.py"
    spec = importlib.util.spec_from_file_location("fetch_study_locality_geocoding_candidates", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def target() -> dict[str, str]:
    return {
        "target_id": "oshima_senzu",
        "island_id": "Oshima",
        "source_locality": "Senzu, Oshima, Tokyo, Japan",
        "source_id": "inoue1986_psb1_89",
    }


def test_query_preserves_literature_locality_and_candidate_limit():
    module = load_module()
    url = module.query_url(target()["source_locality"], limit=5)

    assert "Senzu%2C+Oshima%2C+Tokyo%2C+Japan" in url
    assert "polygon_geojson=1" in url
    assert "limit=5" in url


def test_candidate_rows_remain_unreviewed_geocoding_candidates():
    module = load_module()
    row = module.normalize_candidate(
        target(),
        {
            "osm_type": "node",
            "osm_id": 12,
            "display_name": "Candidate locality, Tokyo, Japan",
            "class": "place",
            "type": "locality",
            "lat": "34.75",
            "lon": "139.36",
            "boundingbox": ["34.74", "34.76", "139.35", "139.37"],
            "importance": 0.5,
        },
        rank=1,
    )

    assert row["review_status"] == "candidate"
    assert row["target_id"] == "oshima_senzu"
    assert row["source_id"] == "inoue1986_psb1_89"
    assert "do not use" in row["notes"]
