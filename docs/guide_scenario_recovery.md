# Competing guide-scenario recovery

## Purpose

The six-layer guide architecture becomes useful only when expressed as
competing restricted scenarios. `channel_id.guide_scenarios` generates expected
observations from a scenario and retains every scenario compatible with
predeclared observation intervals.

It is a pre-data design and synthetic-recovery tool, not posterior model
selection or proof of historical evolution.

## Named scenarios and composable routes

The named scenarios remain useful shorthand for simple hypotheses:

| Scenario | Active route |
|---|---|
| `null` | no independent guide effect |
| `visit_attraction` | guide → visits → maternal outcross seed |
| `handling` | guide → legitimate contact → maternal outcross seed |
| `cost` | guide expression cost without guide benefit |
| `paternal` | guide → pollen export/siring → paternal contribution |
| `assurance` | autonomous/delayed selfing pathway |
| `spatial` | patch-specific retention after local reproduction |
| `mixed` | all declared routes; activate only with all required intermediates |

A real mechanism need not correspond to one named scenario.  `GuideRoutes`
allows a small, declared combination of routes without automatically turning on
unmeasured paternal or spatial mechanisms.

```python
from channel_id.guide_scenarios import GuideRoutes

visit_assurance = GuideRoutes(
    "visit_assurance",
    visit_attraction=True,
    assurance=True,
)
```

This matters because a guide-related increase in visitation and delayed selfing
can plausibly operate at the same time.  Treating those alternatives as
mutually exclusive can produce an empty compatible set even when the virtual
truth is simple and biologically plausible.

## Synthetic recovery rule

1. Simulate a named or composable virtual truth without passing its label to
   recovery.
2. Give recovery a coarse terminal observation and confirm that multiple
   mechanisms remain compatible where they should.
3. Add the intermediate measurements predicted by the truth model.
4. Use jointly calibrated observation intervals and finite-sample simulations.
5. Check whether the compatible set contracts to the truth, or record the
   irreducible ambiguity and empty-set rate.

The deterministic regression test uses a virtual visit-attraction truth.  The
finite-sample benchmark in `channel_id.operating_characteristics` adds
individual-level count noise and reports truth retention, unique recovery,
empty-set rate, and remaining ambiguity.

## First empirical use

For the first Izu campaign, begin with the following maternal candidates rather
than a broad all-pathways model:

```text
null
visit_attraction
handling
cost
assurance
visit + assurance
handling + assurance
visit + cost
handling + cost
visit + handling
visit + handling + assurance
```

`core_maternal_scenarios()` returns this starting set.  Collect guide contrast,
display/nectar and plant condition, guild-resolved visits, per-visit handling or
stigma pollen deposition, separate outcross and selfed seed output where
possible, and a short declared recruitment window.

Activate paternal, temporal, plasticity, and spatial routes only when their
intermediate quantities are measured.  A surviving scenario says only that it
is compatible with declared route restrictions, parameter bounds, observation
intervals, and the assumed observation model.  It is not a unique causal
answer.
