# Seed set plus paternity-subsampling design

## Why this layer is needed

A mature-seed count alone cannot distinguish higher outcrossing from
selfing/assurance compensation.  Conversely, a paternity panel usually does
not genotype every mature seed.  A field-facing power calculation must retain
both stages:

```text
maternal individual
  └ fruit
      └ potential ovules
          ├ mature outcrossed seed
          ├ mature selfed seed
          └ other ovule fate
      └ fixed or capped subsample of mature seeds for parentage assignment
          ├ called outcrossed
          ├ called selfed
          └ unresolved
```

`channel_id.seed_set_paternity` creates virtual datasets on this scale and
passes their outcrossed and selfed viable-seed intervals to the restricted
scenario engine.

## Declared design

```python
from channel_id.seed_set_paternity import SeedSetPaternityDesign

plan = SeedSetPaternityDesign(
    maternal_individuals=40,
    fruits_per_maternal=2,
    potential_ovules_per_fruit=10,
    genotyped_mature_seeds_per_fruit=3,
    unresolved_probability=0.10,
    outcross_to_self_error=0.01,
    self_to_outcross_error=0.01,
    familywise_confidence=0.95,
)
```

The scenario output must be expressed per sampled fruit (or an explicitly
rescaled equivalent).  `potential_ovules_per_fruit` is not a convenience
constant: it must be calibrated from the floral unit under study and be large
enough to contain the viable-seed expectation of every candidate scenario.

## Virtual data-generating process

For each fruit, outcrossed viable seed, selfed viable seed, and other ovule
fate are sampled as mutually exclusive outcomes of the shared ovule pool.
Only mature seeds are eligible for the paternity subset.  A selected seed can
then yield an outcrossed call, a selfed call, or an unresolved call.

The current correction assumes that:

1. unresolved calls are independent of true cross type;
2. the two directional call-error rates are externally calibrated;
3. genotype calls are independent conditional on the declared parameters.

Those assumptions are deliberately visible in the design object.  Do not set
both error rates to zero merely because no calibration has been done.

## Recovery benchmark

```python
from channel_id.guide_scenarios import GuideRoutes, GuideScenario
from channel_id.seed_set_paternity import benchmark_seed_set_paternity_recovery

truth = GuideRoutes("visit_assurance", visit_attraction=True, assurance=True)
candidates = (
    GuideScenario.NULL,
    GuideScenario.VISIT_ATTRACTION,
    GuideScenario.ASSURANCE,
    truth,
)
summary = benchmark_seed_set_paternity_recovery(
    truth,
    candidates,
    settings,
    "typical",
    plan,
    replicates=1_000,
    seed=20260629,
)
print(summary)
```

Read the resulting rates together:

- `truth_retained_rate`: how often the virtual true route remains compatible;
- `unique_truth_recovery_rate`: how often it is the only compatible route;
- `empty_compatible_set_rate`: how often all declared candidates are rejected;
- `mean_resolved_paternity_calls`: realised genotype information after seed set
  and unresolved calls, not merely the intended sampling cap.

A high unique-recovery rate with low truth retention is overconfident.  A high
empty-set rate signals a mismatch between the candidate set, interval model,
or observation design.

## What this does not solve

This is not a substitute for a final parentage likelihood.  Future extensions
must address maternal and site random effects, overdispersed seed set,
non-random genotype failure, incomplete paternal candidate coverage, genotype
error estimated from replicates, and seed abortion or viability measured before
maturity.  It is the smallest design layer that stops the analysis from
pretending every seed's cross type is observed without error.
