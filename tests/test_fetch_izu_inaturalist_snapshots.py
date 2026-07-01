import importlib.util
from pathlib import Path


def load_module():
    path = Path(__file__).parents[1] / "scripts" / "fetch_izu_inaturalist_snapshots.py"
    spec = importlib.util.spec_from_file_location("fetch_izu_inaturalist_snapshots", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def target() -> dict[str, str]:
    return {"target_id": "campanula_microdonta", "taxon_name": "Campanula microdonta"}


def region() -> dict[str, float]:
    return {"swlat": 32.80, "swlng": 138.90, "nelat": 35.10, "nelng": 140.00}


def test_query_keeps_declared_taxon_and_spatial_bounds():
    module = load_module()
    url = module.observation_url(target(), region(), page=2, per_page=200)

    assert "taxon_name=Campanula+microdonta" in url
    assert "swlat=32.8" in url
    assert "swlng=138.9" in url
    assert "nelat=35.1" in url
    assert "nelng=140.0" in url
    assert "page=2" in url
    assert "per_page=200" in url


def test_fetch_target_records_total_and_truncation(monkeypatch):
    module = load_module()
    expected_url = module.observation_url(target(), region(), page=1, per_page=1)
    responses = {
        expected_url: {
            "total_results": 2,
            "results": [
                {
                    "id": 5,
                    "taxon": {"name": "Campanula microdonta"},
                    "observed_on": "2024-07-01",
                    "geojson": {"coordinates": [139.3, 34.7]},
                    "photos": [{"id": 1}],
                    "uri": "https://www.inaturalist.org/observations/5",
                }
            ],
        }
    }
    monkeypatch.setattr(module, "fetch_json", lambda url: responses[url])

    result = module.fetch_target(target(), region(), max_records=1)

    assert result["reported_total_results"] == 2
    assert result["retrieved_candidate_records"] == 1
    assert result["truncated_by_max_records"]
    assert result["records"][0]["photo_count"] == "1"
    assert result["records"][0]["latitude"] == "34.7"
