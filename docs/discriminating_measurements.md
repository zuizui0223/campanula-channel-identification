# Ranking discriminating measurements

## Purpose

After current data have left several life-history parameter settings compatible,
the next task is not to add every conceivable measurement. It is to ask:

> Which feasible new observation would most strongly distinguish the surviving
> candidate mechanisms at the precision the field study can realistically
> achieve?

`channel_id.discrimination` ranks declared options from their model predictions.
For each candidate measurement, the tool groups surviving parameter settings
whose predictions are closer than the predeclared assay resolution.

## Interpretation

If `N` compatible candidates split into outcome groups of sizes
`n_1, ..., n_k`, and candidates are temporarily given equal weight, then:

```text
expected remaining candidates = sum(n_i^2) / N
expected eliminated candidates = N - sum(n_i^2) / N
```

A high-ranked measurement is one that creates many predicted outcomes and
avoids leaving nearly every candidate in a single unresolved group.

This is a **conditional design heuristic**, not a posterior inference:

- it is conditional on the current candidate grid and life cycle;
- equal candidate weights are a convenience, not a biological prior;
- resolution must be set from assay precision before inspecting the ranking;
- a mathematically discriminating measurement can still be infeasible,
  destructive, too costly, or biologically uninformative;
- repeated observations and sampling design still determine whether the stated
  resolution is realistic.

## Typical Campanula options

For the same island and mainland cases, consider ranking:

1. total viable seed output `F`;
2. outcross viable seeds, from a paternity or pollination-treatment design;
3. selfed viable seeds or a validated mating-system component;
4. establishment probability `E`, from seed addition or cohort follow-up;
5. retained recruits `W`.

A likely useful result is not necessarily “measure flowers more precisely.” For
example, if total seed output is already compatible with both attraction loss
and delayed-selfing compensation, but their predicted outcrossed seed outputs
separate, the ranking should prioritise a treatment or paternity measurement
that isolates the outcross component.

## Example

```python
from channel_id.discrimination import MeasurementOption, rank_measurements
from channel_id.life_history import Metric

options = (
    MeasurementOption(
        case_name="island_white",
        metric=Metric.LOCAL_VIABLE_SEED_OUTPUT,
        resolution=0.25,
        label="viable seeds per maternal plant",
    ),
    MeasurementOption(
        case_name="island_white",
        metric=Metric.OUTCROSS_VIABLE_SEEDS,
        resolution=0.25,
        label="outcross viable seeds per maternal plant",
    ),
)

rankings = rank_measurements(compatible_candidates, options)
for ranking in rankings:
    print(
        ranking.option.display_name,
        ranking.expected_eliminated_candidates,
        ranking.outcome_class_sizes,
    )
```

`compatible_candidates` must be the result of the existing constrained sweep,
not an unconstrained parameter grid. The ranking then says which next
measurement best resolves what the data already leave uncertain.

## Field-facing reporting standard

For every ranked option, report:

1. the exact biological quantity and its maternal-individual census scale;
2. the regime and trait comparison it applies to;
3. the assumed achievable resolution and how it was chosen;
4. feasibility constraints: sample size, season, destructive sampling,
   paternity/genotyping effort, and repeated-year requirements;
5. the candidate mechanisms that the measurement is expected to separate.

Only promote a top-ranked option into a field protocol after this practical
check.