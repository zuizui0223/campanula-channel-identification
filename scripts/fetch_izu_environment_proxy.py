"""Fetch climate reanalysis at declared island proxies and compute distance proxies.

The input points are *island proxies* selected by an explicit rule from a raw
geocoding artifact. They are not historical Campanula sampling localities. The
output therefore gives `environment_only` a reproducible competing covariate
layer, while preserving the fact that proxy resolution can affect conclusions.

The script saves raw API replies as well as derived summaries. It never uses an
occurrence point, a public photograph, or a pollinator record as a climate point.

Network retries occur per island query. A transient failure for one point never
throws away successful replies for the other declared points, and retries never
substitute or interpolate a missing climate value.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ARCHIVE_API = "https://archive-api.open-meteo.com/v1/archive"
DAILY_VARS = "temperature_2m_mean,precipitation_sum"
SUMMARY_COLUMNS = (
    "island_id",
    "latitude",
    "longitude",
    "climate_period_start",
    "climate_period_end",
    "mean_daily_temperature_c",
    "mean_annual_precipitation_mm",
    "precipitation_seasonality_cv",
    "days_with_temperature",
    "days_with_precipitation",
    "attempts_used",
    "source_url",
    "proxy_boundary",
)
DISTANCE_COLUMNS = (
    "from_island",
    "to_island",
    "great_circle_proxy_km",
    "distance_interpretation",
)


def climate_url(latitude: float, longitude: float, start_date: str, end_date: str) -> str:
    params = {
        "latitude": f"{latitude:.7f}",
        "longitude": f"{longitude:.7f}",
        "start_date": start_date,
        "end_date": end_date,
        "daily": DAILY_VARS,
        "timezone": "GMT",
    }
    return f"{ARCHIVE_API}?{urlencode(params)}"


def fetch_json(url: str) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "campanula-channel-identification/1.0"})
    with urlopen(request, timeout=120) as response:  # nosec B310 - fixed HTTPS endpoint
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Climate response is not an object")
    return payload


def fetch_json_with_retry(url: str, max_attempts: int, retry_delay_seconds: float) -> tuple[dict[str, Any], int]:
    """Fetch one declared query with exponential backoff for transient transport errors."""

    if max_attempts <= 0:
        raise ValueError("max_attempts must be positive")
    if retry_delay_seconds < 0.0:
        raise ValueError("retry_delay_seconds cannot be negative")
    last_error: OSError | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fetch_json(url), attempt
        except HTTPError as error:
            if error.code < 500 and error.code != 429:
                raise
            last_error = error
        except OSError as error:
            last_error = error
        if attempt < max_attempts:
            time.sleep(retry_delay_seconds * (2 ** (attempt - 1)))
    assert last_error is not None
    raise last_error


def _as_float_series(value: object, label: str) -> list[float | None]:
    if not isinstance(value, list):
        raise ValueError(f"Climate response lacks list-valued {label}")
    result: list[float | None] = []
    for item in value:
        if item is None:
            result.append(None)
        elif isinstance(item, (int, float)) and math.isfinite(float(item)):
            result.append(float(item))
        else:
            raise ValueError(f"Climate response contains invalid {label} value")
    return result


def _as_date_series(value: object) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("Climate response lacks string daily.time values")
    return list(value)


def summarize_climate(
    payload: dict[str, Any],
    point: dict[str, Any],
    start_date: str,
    end_date: str,
    source_url: str,
    attempts_used: int,
) -> dict[str, str]:
    daily = payload.get("daily")
    if not isinstance(daily, dict):
        raise ValueError("Climate response lacks daily object")
    dates = _as_date_series(daily.get("time"))
    temperatures = _as_float_series(daily.get("temperature_2m_mean"), "temperature_2m_mean")
    precipitation = _as_float_series(daily.get("precipitation_sum"), "precipitation_sum")
    if not (len(dates) == len(temperatures) == len(precipitation)):
        raise ValueError("Climate daily arrays have different lengths")
    usable_temperature = [value for value in temperatures if value is not None]
    usable_precipitation = [value for value in precipitation if value is not None]
    if not usable_temperature or not usable_precipitation:
        raise ValueError("Climate response has no usable temperature or precipitation values")
    annual_precipitation: dict[int, float] = defaultdict(float)
    monthly_precipitation: dict[int, float] = defaultdict(float)
    for date_text, value in zip(dates, precipitation):
        if value is None:
            continue
        try:
            year, month, _ = (int(part) for part in date_text.split("-"))
        except ValueError as error:
            raise ValueError(f"Unexpected climate date {date_text!r}") from error
        annual_precipitation[year] += value
        monthly_precipitation[month] += value
    if not annual_precipitation or not monthly_precipitation:
        raise ValueError("Climate response has no aggregable precipitation values")
    monthly_values = list(monthly_precipitation.values())
    monthly_mean = mean(monthly_values)
    precip_cv = 0.0 if monthly_mean == 0.0 else pstdev(monthly_values) / monthly_mean
    return {
        "island_id": str(point["island_id"]),
        "latitude": f"{float(point['latitude']):.7f}",
        "longitude": f"{float(point['longitude']):.7f}",
        "climate_period_start": start_date,
        "climate_period_end": end_date,
        "mean_daily_temperature_c": f"{mean(usable_temperature):.6f}",
        "mean_annual_precipitation_mm": f"{mean(annual_precipitation.values()):.6f}",
        "precipitation_seasonality_cv": f"{precip_cv:.6f}",
        "days_with_temperature": str(len(usable_temperature)),
        "days_with_precipitation": str(len(usable_precipitation)),
        "attempts_used": str(attempts_used),
        "source_url": source_url,
        "proxy_boundary": "Island proxy point only; not a study locality or island-wide mean.",
    }


def haversine_km(latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float) -> float:
    radius_km = 6371.0088
    lat_a = math.radians(latitude_a)
    lat_b = math.radians(latitude_b)
    delta_lat = lat_b - lat_a
    delta_lon = math.radians(longitude_b - longitude_a)
    value = math.sin(delta_lat / 2.0) ** 2 + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lon / 2.0) ** 2
    return radius_km * 2.0 * math.asin(math.sqrt(value))


def distance_rows(points: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, left in enumerate(points):
        for right in points[index + 1 :]:
            distance = haversine_km(
                float(left["latitude"]),
                float(left["longitude"]),
                float(right["latitude"]),
                float(right["longitude"]),
            )
            rows.append(
                {
                    "from_island": str(left["island_id"]),
                    "to_island": str(right["island_id"]),
                    "great_circle_proxy_km": f"{distance:.6f}",
                    "distance_interpretation": "Great-circle distance between declared island proxy points; not least-cost dispersal distance or a direct measure of gene flow.",
                }
            )
    return rows


def run(
    config_path: Path,
    output_dir: Path,
    start_date: str,
    end_date: str,
    max_attempts: int,
    retry_delay_seconds: float,
    inter_request_delay_seconds: float,
) -> int:
    if inter_request_delay_seconds < 0.0:
        raise ValueError("inter_request_delay_seconds cannot be negative")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    points = config.get("points")
    if not isinstance(points, list) or not points:
        raise ValueError("config must contain a nonempty points list")
    point_ids = [str(point.get("island_id") or "") for point in points if isinstance(point, dict)]
    if len(point_ids) != len(points) or not all(point_ids) or len(set(point_ids)) != len(point_ids):
        raise ValueError("each proxy point needs a unique island_id")
    output_dir.mkdir(parents=True, exist_ok=True)
    raw: list[dict[str, Any]] = []
    summaries: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []
    for index, point in enumerate(points):
        if not isinstance(point, dict):
            failures.append({"island_id": "unknown", "error": "proxy point is not an object"})
            continue
        island_id = str(point.get("island_id") or "unknown")
        try:
            latitude = float(point["latitude"])
            longitude = float(point["longitude"])
            if not -90.0 <= latitude <= 90.0 or not -180.0 <= longitude <= 180.0:
                raise ValueError("proxy coordinate is outside valid bounds")
            url = climate_url(latitude, longitude, start_date, end_date)
            payload, attempts_used = fetch_json_with_retry(url, max_attempts, retry_delay_seconds)
            raw.append({"point": point, "query_url": url, "attempts_used": attempts_used, "response": payload})
            summaries.append(summarize_climate(payload, point, start_date, end_date, url, attempts_used))
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
            failures.append({"island_id": island_id, "error": str(error), "max_attempts": str(max_attempts)})
        if index < len(points) - 1 and inter_request_delay_seconds:
            time.sleep(inter_request_delay_seconds)
    manifest = {
        "source": "Open-Meteo archive API",
        "fetched_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "proxy_config": config,
        "climate_period_start": start_date,
        "climate_period_end": end_date,
        "max_attempts_per_island": max_attempts,
        "retry_delay_seconds": retry_delay_seconds,
        "inter_request_delay_seconds": inter_request_delay_seconds,
        "boundary": "Climate values come from declared island proxy points. They are suitable only as a reproducible environmental competing explanation and must be checked against alternative point/polygon extractions.",
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "raw_climate_responses.json").write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "failures.json").write_text(json.dumps(failures, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with (output_dir / "environment_proxy_summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        writer.writerows(summaries)
    with (output_dir / "island_proxy_distances.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=DISTANCE_COLUMNS)
        writer.writeheader()
        writer.writerows(distance_rows([point for point in points if isinstance(point, dict)]))
    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--start-date", default="1981-01-01")
    parser.add_argument("--end-date", default="2010-12-31")
    parser.add_argument("--max-attempts", type=int, default=5)
    parser.add_argument("--retry-delay-seconds", type=float, default=5.0)
    parser.add_argument("--inter-request-delay-seconds", type=float, default=1.0)
    args = parser.parse_args()
    try:
        status = run(
            args.config,
            args.output_dir,
            args.start_date,
            args.end_date,
            args.max_attempts,
            args.retry_delay_seconds,
            args.inter_request_delay_seconds,
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error
    if status:
        raise SystemExit("One or more island proxy climate requests failed after per-island retries; inspect the retained artifact.")


if __name__ == "__main__":
    main()
