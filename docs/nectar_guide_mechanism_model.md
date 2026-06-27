# Nectar-guide mechanism model

## Why a separate model is needed

For *Campanula microdonta*, “nectar guides evolved because they attract
pollinators” is too coarse to be informative. A guide can plausibly affect at
least three separable causal steps:

```text
visual guide
  ├─ encounter / visit rate
  ├─ legitimate handling and pollen placement conditional on a visit
  └─ allocation or pigment-maintenance cost

un-outcrossed ovules
  └─ autonomous or delayed-selfing compensation

local viable seed output F
  └─ establishment E
      └─ retained recruits W
```

`channel_id.nectar_guide` makes those pathways explicit and keeps them
switchable. It is a hypothesis comparator, not a claim that any pathway is
already present in the species.

## Competing models

| Model | Parameter restriction | Core prediction |
|---|---|---|
| Visit-attraction | `guide_visit_gain > 0`, `guide_handling_gain = 0` | guide contrast raises visit rate, then outcross seed output |
| Handling / pollen-placement | `guide_visit_gain = 0`, `guide_handling_gain > 0` | visit rate is unchanged, but legitimate contact and outcross seed output rise |
| Pure cost | guide gains = 0, `guide_cost > 0` | guide contrast lowers remaining seed budget and performance |
| Benefit–cost | gains and cost > 0 | guide advantage can reverse across pollinator service or resource conditions |
| Assurance compensation | guide pathway may be weak while `assurance` is high | reduced outcrossing can be partly offset by selfed viable seed production |
| Null guide | guide gains = guide cost = 0 | guide contrast has no independent predicted effect after controlling declared covariates |

The null model matters. A guide–fitness correlation alone is not evidence for a
causal guide effect if guide contrast covaries with flower size, nectar, site,
or genetic background.

## Current equations

For a trait `(g, d, r)` = guide contrast, display, assurance and a regime with
pollinator service `P`:

```text
remaining budget = seed_budget
                   - display_cost * d^2
                   - guide_cost * g^2
                   - assurance_cost * r^2

expected visits = P * (baseline_visit_rate
                       + display_visit_gain * d
                       + guide_visit_gain * g)

legitimate contact fraction = min(1,
                                  baseline_legitimate_fraction
                                  + guide_handling_gain * g)

outcross fraction = 1 - exp(- expected_visits
                             * legitimate_contact_fraction
                             * pollen_to_outcross_fraction)
```

The rest of the life cycle follows the existing factorisation:

```text
outcross viable seeds + selfed viable seeds = F
F * E = W
```

The saturation function is deliberate: it prevents the model from treating
extra visits as indefinitely linearly beneficial and permits a guide effect on
handling even when visit counts have already saturated.

## Data that distinguish the models

| Candidate claim | Minimal discriminating observation | What would weaken it |
|---|---|---|
| Guide increases visitation | standardized guide manipulation or natural contrast variation with visit rate, controlling display and nectar | guide does not predict visits after those controls |
| Guide improves handling | contact position, stigma pollen deposition, pollen removal, or legitimate-visit fraction per visit | visits differ but per-visit pollen transfer does not |
| Guide raises outcrossing | paternity / mating-system estimate, pollen supplementation contrasts, or outcrossed viable seed output | higher guide does not increase outcross component |
| Guide is maintained despite a cost | direct budget/ovule/nectar/seed trade-off with guide contrast, ideally manipulated | no detectable cost and no benefit–cost reversal |
| Guide loss is buffered by assurance | autonomous/delayed selfing and inbreeding-related viability across guide states | low-guide phenotypes lack compensation and lose F/W |
| E explains the pattern instead | seed addition, germination, cohort survival, or recruit follow-up | F already explains the contrast and E is unchanged |

## What is required before saying “evolutionary cause”

The model can produce a **conditional relative-performance contrast** between
low- and high-guide phenotypes. That only becomes evidence about evolutionary
cause when all of the following are separately addressed:

1. guide contrast has standing heritable variation or a defensible genetic
   basis, rather than being only a plastic response;
2. guide contrast is measured or manipulated independently of flower size,
   nectar amount, plant condition, and site;
3. the proposed mechanism predicts a measured intermediate quantity: visits,
   handling, pollen transfer, mating outcome, cost, or establishment;
4. the relative effect is observed over the declared fitness census window;
5. plausible alternatives, including selfing compensation and E-stage
   differences, are compared rather than assumed absent.

Until then, this is a model of *mechanistic compatibility*, not a historical
explanation for the evolution of nectar guides.

## Next model improvements after this layer

The highest-value future additions are not arbitrary complexity:

1. pollen deposition and pollen removal as separate measured quantities;
2. genotype / maternal-family random effects and guide plasticity;
3. inbreeding depression expressed after seed set, not only selfed seed
   viability;
4. multiple pollinator functional groups with guide-specific responses;
5. annual variation in pollinator service and the geometric mean of fitness;
6. spatial dispersal and recruit establishment only after E-stage observations
   exist.
