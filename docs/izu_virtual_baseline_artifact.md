# Virtual Izu sensitivity baseline artifact

## What this artifact is

The workflow `Virtual Izu Baseline` runs one reproducible, fixed-seed virtual
comparison after a relevant pull request. It writes a Markdown artifact named
`izu-virtual-sensitivity-baseline`.

The artifact compares four deliberately contrasting plans across five synthetic
mechanism worlds and two analysis modes:

```text
plans:  light, camera_heavy, genetic_heavy, balanced_high
worlds: null, visit, handling, assurance, visit + assurance
actions: calibrated environment, flat environment
```

It uses the ordinal Izu scaffold and synthetic endpoint assumptions declared in
`scripts/generate_izu_sensitivity_baseline.py`. It is **not** an empirical result
and must not be read as a field sample-size recommendation.

## Why generate a fixed baseline

The purpose is regression visibility. When a change alters the observation
model, scenario engine, or virtual-gradient logic, the resulting table makes it
possible to notice whether it changes:

- truth retention;
- unique route recovery;
- empty compatible-set rate;
- which plan, if any, lies on the Pareto-minimal passing frontier.

The artifact remains fixed at seed `20260630` and 50 replicates per
plan × world × analysis mode. It is a stable smoke baseline, not a substitute
for high-replicate sensitivity analyses.

## How to read the rows

- `calibrated` provides every candidate scenario with the same declared
  pollinator-service and establishment gradient used to generate the virtual
  data. Only these rows decide whether a plan passes its operating thresholds.
- `flat_environment` intentionally ignores that background gradient. Its
  purpose is to expose mechanism misattribution risk, especially in the null
  world. It never determines whether a plan is accepted.
- `genotype cap` is an upper bound on genotyped mature seeds; actual informative
  paternity calls can be lower because mature seeds may be absent or unresolved.

## Retrieval

On a pull request, open **Actions → Virtual Izu Baseline → Artifacts** and
retrieve `izu-virtual-sensitivity-baseline`. The workflow also prints the
Markdown report in the job log.

To reproduce locally:

```bash
python scripts/generate_izu_sensitivity_baseline.py \
  --replicates 50 \
  --output artifacts/izu_virtual_sensitivity_baseline.md
```

For serious sensitivity work, create a separate configuration or invocation
with expanded assumptions and more replicates rather than changing the fixed
baseline silently.
