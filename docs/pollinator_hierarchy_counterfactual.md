# Pollinator-hierarchy counterfactual check

This check advances the PR33 environment layer into a literature-grounded pattern comparison. It uses already published Inoue-series channels plus the PR33 island-proxy climate values to ask whether the observed island pattern is more compatible with:

1. `pollinator_hierarchy`: mainland large Bombus -> Oshima B. ardens bridge -> non-Bombus bee regime;
2. `environment_only`: temperature and precipitation proxy gradient;
3. `isolation_order`: ordered island-chain isolation proxy.

## Locked input channels

The first locked table is `data/inoue_literature_island_traits.csv`.

It includes:

- Bombus diversus presence/absence;
- Bombus ardens presence/absence;
- halictid and megachilid pollinator records;
- bagged capsule/seed-set summaries as a self-compatibility/selfing proxy;
- outcrossing-rate intervals from the mating-system literature;
- flower-length values where the 1995 experimental table provides a locked population mean;
- PR33 island-proxy climate summaries.

## Boundary

This is not a causal proof and not a demographic parameter fit. It is a reproducible counterfactual pattern check. A model ranking here means only that the model's declared island-stage prediction has lower pattern error against the currently locked observed channels.

Nectar-guide loss and inbreeding-depression costs remain blocked until island-resolved guide/spot measurements and late survival or fitness data are imported.
