"""Fetch and snapshot public GBIF occurrence records for one declared taxon.

This script records exact GBIF Species/Occurrence API queries, raw response
pages, and a normalized CSV. Its output is *availability evidence only*: records
do not establish flower visitation, pollen transfer, effectiveness, absence, or
history.

A species-match response can be intentionally non-unique for a genus name. The
normal route uses GBIF's species-match response, then an exact accepted-genus
fallback. When a genus remains non-unique across checklists, callers may provide
a reviewed GBIF taxon key with a rationale. The script validates and saves the
selected GBIF taxon record while preserving the original ambiguous response. It
never silently chooses one of equal matches.

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


def species_search_url(scientific_name: str, rank: str, limit: int = 100) -> str:
    return f"{API_ROOT}/species/search?{urlencode({'q': scientific_name, 'rank': rank, 'limit': limit})}"


def species_key_url(taxon_key: int) -> str:
    return f"{API_ROOT}/species/{taxon_key}"


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


def _normalized_name(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def _exact_accepted_genus_candidates(
    search_response: dict[str, Any], scientific_name: str
) -> list[dict[str, Any]]:
    """Return only unambiguous exact accepted genus candidates.

    This deliberately does not infer synonymy, choose an equal-scoring candidate,
    or accept a different rank. Such decisions must remain visible in the raw
    GBIF response and be reviewed separately.
    """

    target = _normalized_name(scientific_name)
    results = search_response.get("results", [])
    if not isinstance(results, list):
        raise ValueError("GBIF species search response lacks a result list")
    return [
        row
        for row in results
        if isinstance(row, dict)
        and row.get("rank") == "GENUS"
        and _normalized_name(row.get("canonicalName")) == target
        and str(row.get("taxonomicStatus", "")).upper() == "ACCEPTED"
        and isinstance(row.get("key"), int)
    ]


def _validate_declared_taxon(
    selected: dict[str, Any], scientific_name: str, taxon_key: int
) -> None:
    """Validate an explicit key without converting it into an implicit match."""

    if selected.get("key") != taxon_key:
        raise ValueError("GBIF returned a taxon record with a different key than the declared taxon key")
    if str(selected.get("taxonomicStatus", "")).upper() != "ACCEPTED":
        raise ValueError("Declared GBIF taxon key is not accepted")
    canonical = _normalized_name(selected.get("canonicalName"))
    requested = _normalized_name(scientific_name)
    if not canonical or not (requested == canonical or requested.startswith(f"{canonical} ")):
        raise ValueError(
            "Declared GBIF taxon key does not have a canonical name compatible with "
            f"the requested taxon {scientific_name!r}"
        )


def resolve_taxon(
    scientific_name: str,
    declared_taxon_key: int | None = None,
    declared_taxon_key_rationale: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], int, list[str]]:
    """Resolve a GBIF taxon key with auditable non-silent fallbacks.

    When `declared_taxon_key` is supplied, the selected record and the original
    ambiguous match are both retained. A rationale is mandatory because this is
    an explicit reviewed input, not automatic taxonomic resolution.
    """

    if declared_taxon_key is not None:
        if declared_taxon_key <= 0:
            raise ValueError("declared_taxon_key must be positive")
        if not declared_taxon_key_rationale or not declared_taxon_key_rationale.strip():
            raise ValueError("declared_taxon_key_rationale is required with declared_taxon_key")
        match_url = species_match_url(scientific_name)
        selected_url = species_key_url(declared_taxon_key)
        raw_match = fetch_json(match_url)
        selected = fetch_json(selected_url)
        _validate_declared_taxon(selected, scientific_name, declared_taxon_key)
        resolved = {
            **selected,
            "usageKey": declared_taxon_key,
            "matchType": "DECLARED_REVIEWED_TAXON_KEY",
        }
        resolution = {
            "method": "declared_reviewed_taxon_key",
            "rationale": declared_taxon_key_rationale.strip(),
            "original_species_match": raw_match,
            "selected_taxon": selected,
        }
        return resolved, resolution, declared_taxon_key, [match_url, selected_url]

    match_url = species_match_url(scientific_name)
    raw_match = fetch_json(match_url)
    taxon_key = raw_match.get("usageKey")
    if isinstance(taxon_key, int):
        return (
            raw_match,
            {
                "method": "species_match",
                "original_species_match": raw_match,
            },
            taxon_key,
            [match_url],
        )

    search_url = species_search_url(scientific_name, rank="GENUS")
    search_response = fetch_json(search_url)
    candidates = _exact_accepted_genus_candidates(search_response, scientific_name)
    if len(candidates) != 1:
        candidate_summary = [
            {
                "key": row.get("key"),
                "canonicalName": row.get("canonicalName"),
                "scientificName": row.get("scientificName"),
                "rank": row.get("rank"),
                "taxonomicStatus": row.get("taxonomicStatus"),
            }
            for row in candidates
        ]
        raise ValueError(
            "GBIF taxon resolution remains ambiguous for "
            f"{scientific_name!r}; exact accepted GENUS candidates: {candidate_summary}"
        )
    candidate = candidates[0]
    resolved = {
        **raw_match,
        "usageKey": candidate["key"],
        "canonicalName": candidate.get("canonicalName"),
        "scientificName": candidate.get("scientificName"),
        "rank": candidate.get("rank"),
        "taxonomicStatus": candidate.get("taxonomicStatus"),
        "matchType": "SPECIES_SEARCH_EXACT_ACCEPTED_GENUS",
    }
    return (
        resolved,
        {
            "method": "species_search_exact_accepted_genus",
            "original_species_match": raw_match,
            "species_search": search_response,
            "selected_candidate": candidate,
        },
        candidate["key"],
        [match_url, search_url],
    )


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
    declared_taxon_key: int | None = None,
    declared_taxon_key_rationale: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, str]], list[str]]:
    """Resolve a taxon then retrieve bounded, paginated occurrence results."""

    if max_records <= 0 or page_size <= 0:
        raise ValueError("max_records and page_size must be positive")
    resolved, resolution, taxon_key, urls = resolve_taxon(
        scientific_name,
        declared_taxon_key=declared_taxon_key,
        declared_taxon_key_rationale=declared_taxon_key_rationale,
    )
    pages: list[dict[str, Any]] = []
    records: list[dict[str, str]] = []
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
    return resolved, resolution, pages, records, urls


def write_snapshot(
    output_dir: Path,
    scientific_name: str,
    target_id: str,
    country: str | None,
    max_records: int,
    page_size: int,
    declared_taxon_key: int | None = None,
    declared_taxon_key_rationale: str | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    match, resolution, pages, records, urls = fetch_occurrences(
        scientific_name,
        target_id,
        country,
        max_records,
        page_size,
        declared_taxon_key=declared_taxon_key,
        declared_taxon_key_rationale=declared_taxon_key_rationale,
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
        "taxon_resolution_method": resolution["method"],
        "query_urls": urls,
        "boundary": "Occurrence records are availability evidence only; they do not establish visitation, effectiveness, absence, or historical persistence.",
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (output_dir / "species_match.json").write_text(
        json.dumps(resolution["original_species_match"], indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "taxon_resolution.json").write_text(json.dumps(resolution, indent=2) + "\n", encoding="utf-8")
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
    parser.add_argument("--taxon-key", type=int)
    parser.add_argument("--taxon-key-rationale")
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
            declared_taxon_key=args.taxon_key,
            declared_taxon_key_rationale=args.taxon_key_rationale,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
