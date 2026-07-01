"""Fetch and snapshot public GBIF occurrence records for one declared taxon.

This script records the exact GBIF Species/Occurrence API query, response pages,
and a normalized CSV. Its output is *availability evidence only*: records do not
establish flower visitation, pollen transfer, effectiveness, absence, or history.

Example:
    python scripts/fetch_gbif_occurrences.py \
      --scientific-name "Bombus ardens" \
      --target-id bombus_ardens \
      --country JP \
      --max-records 1000 \
      --output-dir data/raw/gbif/bombus_ardens
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_ROOT = "https://api.gbif.org/v1"
NORMALIZED_COLUMNS = (
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


def fetch_json(url: str) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "campanula-channel-identification/1.0"})
    with urlopen(request, timeout=60) as response:  # nosec B310 - fixed HTTPS API root
        return json.loads(response.read().decode("utf-8"))


def species_match_url(scientific_name: str) -> str:
    return f"{API_ROOT}/species/match?{urlencode({'name': scientific_name})}"


def occurrence_search_url(taxon_key: int, country: str | None, limit: int, offset: int) -> str:
    query: dict[str, str | int] = {
        "taxon_key": taxon_key,
        "has_coordinate": "true",
        "limit": limit,
        "offset": offset,
    }
    if country:
        query["country"] = country
    return f"{API_ROOT}/occurrence/search?{urlencode(query)}"


def normalize_record(record: dict[str, Any], target_id: str) -> dict[str, str]:
    """Convert selected Darwin Core fields without inventing a review decision."""

    key = str(record.get("key", "")).strip()
    return {
        "record_id": key,
        "target_id": target_id,
        "scientific_name": str(record.get("scientificName") or record.get("species") or "").strip(),
        "event_date": str(record.get("eventDate") or record.get("year") or "").strip(),
        "decimal_latitude": str(record.get("decimalLatitude") or "").strip(),
        "decimal_longitude": str(record.get("decimalLongitude") or "").strip(),
        "coordinate_uncertainty_m": str(record.get("coordinateUncertaintyInMeters") or "").strip(),
        "basis_of_record": str(record.get("basisOfRecord") or "").strip(),
        "dataset_key": str(record.get("datasetKey") or "").strip(),
        "source_url": f"https://www.gbif.org/occurrence/{key}" if key else "",
        "identification_status": str(record.get("taxonomicStatus") or "not_reviewed").strip(),
        "review_status": "candidate",
        "notes": "Raw GBIF occurrence; review required before analysis.",
    }


def fetch_occurrences(
    scientific_name: str,
    target_id: str,
    country: str | None,
    max_records: int,
    page_size: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, str]], list[str]]:
    """Resolve a taxon then retrieve bounded, paginated occurrence results."""

    if max_records <= 0 or page_size <= 0:
        raise ValueError("max_records and page_size must be positive")
    match_url = species_match_url(scientific_name)
    match = fetch_json(match_url)
    taxon_key = match.get("usageKey")
    if not isinstance(taxon_key, int):
        raise ValueError(f"GBIF did not return a usageKey for {scientific_name!r}: {match}")
    pages: list[dict[str, Any]] = []
    records: list[dict[str, str]] = []
    urls = [match_url]
    offset = 0
    while len(records) < max_records:
        limit = min(page_size, max_records - len(records))
        query_url = occurrence_search_url(taxon_key, country, limit, offset)
        urls.append(query_url)
        page = fetch_json(query_url)
        pages.append(page)
        results = page.get("results", [])
        if not isinstance(results, list):
            raise ValueError("GBIF occurrence response lacks a result list")
        records.extend(normalize_record(item, target_id) for item in results)
        if page.get("endOfRecords", True) or not results:
            break
        offset += len(results)
    return match, pages, records, urls


def write_snapshot(
    output_dir: Path,
    scientific_name: str,
    target_id: str,
    country: str | None,
    max_records: int,
    page_size: int,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    match, pages, records, urls = fetch_occurrences(
        scientific_name, target_id, country, max_records, page_size
    )
    fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    manifest = {
        "source": "GBIF API",
        "fetched_at_utc": fetched_at,
        "scientific_name_requested": scientific_name,
        "target_id": target_id,
        "country": country,
        "max_records": max_records,
        "page_size": page_size,
        "matched_taxon": match,
        "query_urls": urls,
        "boundary": "Occurrence records are availability evidence only; they do not establish visitation, effectiveness, absence, or historical persistence.",
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (output_dir / "species_match.json").write_text(json.dumps(match, indent=2) + "\n", encoding="utf-8")
    (output_dir / "occurrence_pages.json").write_text(json.dumps(pages, indent=2) + "\n", encoding="utf-8")
    with (output_dir / "occurrences_candidate.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=NORMALIZED_COLUMNS)
        writer.writeheader()
        writer.writerows(records)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scientific-name", required=True)
    parser.add_argument("--target-id", required=True)
    parser.add_argument("--country", default="JP")
    parser.add_argument("--max-records", type=int, default=1000)
    parser.add_argument("--page-size", type=int, default=300)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        write_snapshot(
            output_dir=args.output_dir,
            scientific_name=args.scientific_name,
            target_id=args.target_id,
            country=args.country or None,
            max_records=args.max_records,
            page_size=args.page_size,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
