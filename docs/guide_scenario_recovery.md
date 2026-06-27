# Competing guide-scenario recovery

## Purpose

The six-layer guide architecture becomes useful only when expressed as
competing restricted scenarios. `channel_id.guide_scenarios` generates expected
observations from a scenario and retains every scenario compatible with
predeclared observation intervals.

It is a pre-data design and synthetic-recovery tool, not posterior model
selection or proof of historical evolution.

## Current restricted scenarios

| Scenario | Active route |
|---|---|
| `null` | no independent guide effect |
| `visit_attraction` | guide → visits → maternal outcross seed |
| `handling` | guide → legitimate contact → maternal outcross seed |
| `paternal` | guide → pollen export/siring → paternal contribution |
| `assurance` | autonomous/delayed selfing pathway |
| `spatial` | patch-specific retention after local reproduction |
| `mixed` | all declared routes; interpret conservatively |

## Synthetic recovery rule

1. Simulate a named virtual truth without passing its label to recovery.
2. Give recovery a coarse terminal observation and confirm that multiple
   mechanisms remain compatible where they should.
3. Add the intermediate measurements predicted by the truth model.
4. Check whether the compatible set contracts to the truth, or record the
   irreducible ambiguity.

The included regression test uses a virtual visit-attraction truth. A wide
interval for total genetic contribution retains multiple scenarios. Adding
expected visits and outcross viable seeds recovers `visit_attraction`.

## First empirical use

For the first Izu campaign, begin with four scenarios only:

```text
null
visit_attraction
handling
assurance
```

Collect guide contrast, display/nectar and plant condition, guild-resolved
visits, per-visit handling or stigma pollen deposition, seed output, and a
short declared recruitment window. Activate paternal, temporal, plasticity,
and spatial scenarios only when their intermediate quantities are measured.

A surviving scenario says only that it is compatible with declared model
restrictions, parameter bounds, and observation intervals. It is not a unique
causal answer.