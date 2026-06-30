# Izu virtual sensitivity report

## Purpose

This report is the next step after the virtual Izu-gradient benchmark.  It does
not collect or infer any empirical result.  Instead, it asks which combinations
of camera observation, fruit sampling, and paternity genotyping could recover a
declared mechanism **across all five synthetic worlds** before the field design
is frozen.

The five required worlds are:

1. `null_environment_gradient` — guide contrast covaries with the island axis,
   but the true guide route is null;
2. `visit_environment_gradient` — guide contrast changes visitation;
3. `handling_environment_gradient` — guide contrast changes legitimate handling
   conditional on a visit;
4. `assurance_environment_gradient` — autonomous/delayed selfing compensation
   is the active route;
5. `visit_assurance_environment_gradient` — attraction and assurance operate
   together.

The first world is the false-positive stress test.  A plan that looks powerful
only when the true guide effect is nonzero is not enough.

## Observation-plan axes

Every `IzuObservationPlan` declares, per island site:

```text
flower_camera_windows
maternal_individuals
fruits_per_maternal
potential_ovules_per_fruit
genotyped_mature_seeds_per_fruit
camera detection / annotation calibration
paternity unresolved / directional error calibration
```

The report exposes three direct operational quantities rather than inventing a
single exchange rate among them:

```text
camera windows/site
collected fruits/site = maternal individuals × fruits per maternal
genotype-cap seeds/site = collected fruits × genotype cap per fruit
```

`genotype-cap` is an upper bound.  Low seed set or unresolved calls can make
the realised number of informative parentage calls lower.

## Pass criteria

A plan passes a calibrated world only if all three predeclared criteria hold:

```text
truth retention rate          ≥ 0.90
unique true-route recovery    ≥ 0.80
empty compatible-set rate     ≤ 0.10
```

A plan enters `passing_plans()` only if it passes **every calibrated one of the
five worlds**.  The exact thresholds are inputs, not universal standards.

`FLAT_ENVIRONMENT` rows are retained in the table but do not decide whether a
plan passes.  They deliberately represent an analysis that ignores the
pollinator-service and establishment gradients.  A large gap from the
`CALIBRATED` rows flags a likely confounding problem: the eventual field design
must measure the relevant environmental background instead of treating island
identity as a floral-trait effect.

## Pareto rather than a fake total cost

Camera windows, fruit collection, and genotyping do not share an honest common
currency before actual logistics and prices are known.  Therefore
`pareto_minimal_passing_plans()` removes only a plan for which another passing
plan needs:

- no more camera windows,
- no more collected fruits, and
- no larger genotype seed cap,

with a strict reduction in at least one of those three quantities.

The surviving plans are the choices worth comparing against access, flowering
density, ship schedule, battery/camera availability, and laboratory budget.

## Run the supplied five-world report

```bash
python examples/izu_sensitivity_report.py
```

The example compares four illustrative plans: light, camera-heavy,
genetic-heavy, and balanced-high.  Its values are sensitivity assumptions and
not recommendations for the current summer field trip.  Increase `replicates`
only after deciding the candidate worlds and calibration assumptions; use a
fixed seed when comparing alternative plan grids.

## What to do with the table

Interpret failures by world and by resource pattern.

- **Visit world fails; camera-heavy passes:** camera exposure or detection
  calibration is limiting.
- **Handling world fails despite many visits:** annotation sensitivity/
  specificity or the definition of legitimate contact is limiting.
- **Assurance world fails; genetic-heavy passes:** fruit-level seed sampling or
  parentage information is limiting.
- **Compound world fails but individual worlds pass:** the design cannot yet
  distinguish a realistic combined route; do not force a single-route
  conclusion.
- **Null world fails under `FLAT_ENVIRONMENT`:** the background gradient must
  be measured and entered explicitly before interpreting a trait effect.

## Boundary before real data

This remains a synthetic stress test.  The island scaffold, guide contrast
slope, pollinator-service slope, establishment slope, detection probability,
annotation error, paternity error, and candidate universe are declared inputs.
Only after their failure modes are understood should the scaffold be replaced
with verified occurrence/phenotype sites and measured geographic, climatic,
habitat, camera, seed-set, and parentage calibration data.
