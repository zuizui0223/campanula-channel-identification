# Public-data collection plan for staged island divergence

## Goal

Add public observation layers to the source-backed Inoue-series synthesis without
turning records into unobserved biological processes.

```text
raw occurrence/photo/environment record
  -> source-versioned reviewed observation
  -> availability / trait / environmental evidence
  -> scenario compatibility comparison
```

The model must never make this shortcut:

```text
GBIF record -> flower visitation -> effective pollen transfer -> historical selection
```

## Target query docket

Every search is saved separately with its taxon string, GBIF match result, query
URL, retrieval time, raw response pages, and candidate CSV.

| Target ID | Initial query | Role in analysis |
|---|---|---|
| `campanula_microdonta` | `Campanula microdonta` | focal plant distribution and photographic lead generation |
| `campanula_punctata` | `Campanula punctata` | mainland comparison and historical-name cross-check |
| `bombus_ardens` | `Bombus ardens` | Oshima bridge candidate; availability evidence only |
| `bombus_diversus` | `Bombus diversus` | mainland Bombus comparison |
| `lasioglossum` | `Lasioglossum` | small-bee guild availability, not species-specific effectiveness |
| `megachile` | `Megachile` | small-bee guild availability, not species-specific effectiveness |
| `ceratina` | `Ceratina` | supplementary small-bee guild availability |

Taxonomy must be checked per retrieval because historical names, synonymy, and
rank resolution can change the returned taxon key. The match JSON is retained
rather than overwritten.

## Occurrence download

```bash
python scripts/fetch_gbif_occurrences.py \
  --scientific-name "Bombus ardens" \
  --target-id bombus_ardens \
  --country JP \
  --max-records 2000 \
  --output-dir data/raw/gbif/bombus_ardens
```

Repeat one taxon at a time. Then review candidates before copying accepted rows
into `data/public_evidence/occurrences.csv`.

Recommended initial filters for review:

- coordinate exists and the record can be assigned to a source-versioned island buffer;
- event date is retained when supplied;
- basis of record and dataset provenance are retained;
- identification is not obviously contradicted by the record metadata;
- records are deduplicated by occurrence key, not merely coordinates.

A missing record in an island buffer remains unknown. It is not an absence datum.

## Environment layer

Use a reproducible point/buffer extraction rather than a hand-copied island
mean. For each variable retain:

```text
source name and version
raster locator or checksum
island geometry source and version
extraction statistic (point, mean buffer, range, etc.)
extraction code/version and date
unit
```

The first comparison set should be deliberately small to avoid a six-island
multiple-comparison exercise:

```text
annual mean temperature
precipitation seasonality
annual precipitation
island area
shortest distance to mainland
shortest distance to the nearest source island
```

Climate is used to give the `environment_only` model a fair competing pathway.
It is not used as a proxy for pollinator effect.

## Photo trait layer

A photograph is eligible only when the flower interior is sufficiently visible.
For every usable image retain the original URL, license, taxon label, capture
date if available, island assignment basis, and image quality score.

Minimum annotations:

```text
spot_present: present / absent / not_assessable
spot_fraction: [0, 1] only when measurable
spot_position_relative: [0, 1] only when measurable
annotator identifier
```

At least two independent annotations on a subset of the same images are needed
before treating island differences as more than exploratory. Curated showcase
photos are not random samples, so the output remains a photographic evidence
channel rather than a population frequency estimate.

## Integration order

1. Audit occurrence, environment, and photo tables separately.
2. Build a coverage matrix: which island × evidence channel is observed.
3. Add public layers one at a time to scenario compatibility checks.
4. Run leave-one-island-out sensitivity and record which conclusion changes.
5. Only then consider a joint latent-availability model.

The first joint model should return compatibility regions and counterfactual
predictions, not a claim that the historical sequence has been proven.
