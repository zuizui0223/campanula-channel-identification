# Nectar-guide evolution model: six linked layers

This specification extends the initial guide `visit -> handling -> F -> E -> W`
model only where a new layer changes a concrete evolutionary interpretation.
Each layer has a corresponding observable and a falsification target.

## 1. Maternal and paternal genetic contribution

A guide may change maternal success, paternal success, or both.

```text
W_total = W_female + male_weight * W_male
```

- `W_female`: retained recruits from maternal seed production.
- `W_male`: realised siring contribution from exported pollen.
- `male_weight`: declared conversion to the chosen common genetic currency.

**Data:** pollen removal/export, recipient pollen transfer, paternity or
siring success.

**Falsification:** if guide contrast has no effect on export or siring after
controlling display and plant condition, a paternal-only explanation weakens.

## 2. Functional pollinator guilds

For guild `j`, the model separately stores:

```text
visit rate lambda_j(g)
legitimate handling h_j(g)
pollen deposition d_j(g)
pollen export x_j(g)
```

The outcross and paternal components aggregate guild-specific contributions,
not a pooled visitor count.

**Data:** identify guild, visit frequency, contact position, pollen deposition,
and pollen removal/export per visit.

**Falsification:** a purported guide-responsive guild must show its predicted
intermediate response; a pooled increase in visits is insufficient.

## 3. Late inbreeding depression

Selfed seed is converted to recruits on a separate path:

```text
selfed survival = outcrossed survival * (1 - delta_late)
```

This forces delayed selfing to earn its apparent compensation beyond seed set.

**Data:** cross type, germination, survival, and recruitment over a declared
window. Ideally include controlled self and outcross crosses.

**Falsification:** if selfed and outcrossed lineages retain equal recruitment,
large late inbreeding depression is unsupported.

## 4. Temporal environmental variation

For years or explicitly weighted pollinator states, report both arithmetic and
geometric mean contribution.

```text
W_geo = exp(sum(p_t * log(W_t)))
```

A zero in a positive-probability state yields zero geometric mean rather than
being hidden inside an average.

**Data:** repeated years, annual pollinator-guild composition, annual
reproductive components, and whether year states are sampled representatively.

**Falsification:** a bet-hedging or assurance interpretation weakens if its
supposed poor-pollination years do not occur or do not differentially penalise
guide strategies.

## 5. Genetic versus plastic guide expression

The observed guide phenotype is not automatically the selectable genetic value.
The reaction-norm layer writes:

```text
expressed guide = genetic baseline + plastic slope * environmental deviation
```

bounded to the measurement scale.

**Data:** family/clone structure, common garden or reciprocal environment,
repeated measures, and recorded drivers such as light or nutrient condition.

**Falsification:** if guide contrast tracks environment within the same genetic
family and no family-level variation remains, an evolutionary explanation based
on guide genotype is not yet supported.

## 6. Spatial dispersal and establishment

Viable seed is distributed among patches before recruitment:

```text
recruits_k = min(capacity_k,
                 viable_seeds * dispersal_to_k * establishment_k)
```

This distinguishes local seed production from destination-specific recruitment
and makes saturation explicit.

**Data:** seed dispersal/retention, patch availability, seed addition or cohort
follow-up, germination and survival per patch.

**Falsification:** a local-reproduction explanation weakens if F is unchanged
but dispersal destination or patch establishment predicts W.

## Integration contract

Do not fit all six layers at once simply because they exist. Start with a
predeclared set of competing mechanisms and only activate a layer if its
required intermediate quantity is measured or has a defensible calibrated
proxy.

A strong future conclusion will look like:

> Guide contrast was associated with a specific guild's legitimate handling and
> pollen export, increasing both maternal and paternal contributions. Selfing
> partly compensated in low-service years, but late inbreeding depression and
> recruit-stage limitation prevented complete compensation. The pattern
> persisted after separating family-level guide variation from environmental
> plasticity and after modelling patch-specific establishment.

Anything weaker should be reported as conditional compatibility, not as the
historical cause of nectar-guide evolution.
