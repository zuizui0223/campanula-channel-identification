# Island multichannel evidence model

## Question

This module asks a deliberately restricted question:

> Given source-locked summaries of flower length, outcrossing, bagged autonomous
> reproduction, visitor-regime evidence, measured environment, and optionally
> reviewed directional guide/spot evidence, which declared island scenario
> remains most compatible with the combined observations?

It does **not** reconstruct the historical evolution of any island population,
estimate a contemporary pollination rate from GBIF/iNaturalist records, or turn
an LLM summary into a biological parameter.

## Why a separate module

The older staged-island synthesis is a useful transparent sensitivity sweep, but
it uses broad scenario ranges over a limited set of summary statistics.  The
multichannel model keeps the evidence channels separate until the likelihood
stage and makes their contribution, omission sensitivity, and prior dependence
explicit.

The current baseline inputs are the source-locked `data/inoue_literature_island_traits.csv` table:

```text
- reported multilocus outcrossing range
- bagged capsule-set percentage
- common-garden flower-length summary where available
- direct historical visitor-regime indicators
- declared climate proxy values
```

Missing values remain missing.  In particular, an island without a flower-length
summary is not assigned a value by regression before model comparison.

## Latent quantities and observation channels

For island `i`, the model represents an effective outcross-service state `Q_i`,
autonomous-assurance state `A_i`, and latent guide strength `G_i`.

```text
visitor-regime availability + scenario-specific effectiveness -> Q_i
Q_i and climate covariates                              -> A_i, t_i, L_i, G_i
A_i                                                     -> bagging outcome
```

The current observation channels are deliberately modest:

| Channel | Observed input | Likelihood scale | What it can constrain |
|---|---|---|---|
| Outcrossing | paper-level `t` range midpoint | normal on logit scale | realised mating-system summary |
| Bagging | bagged capsule-set percentage | normal on logit scale | autonomous reproductive output in that experiment |
| Flower | common-garden flower length | normal, mm scale | morphology under the reported common-garden setting |
| Guide order | reviewed `island A > island B` constraint | ordered-probit style | directional guide/spot information only |

The likelihoods are not treated as exchangeable raw-individual models.  They
are an interim bridge for heterogeneous paper-level summaries, and their error
scales are declared in `ObservationScale`.

## Candidate scenarios

```text
environment_only
body_size_only
small_bee_substitution
ardens_bridge_loss
```

- `environment_only`: climate covariates may explain all trait channels without
  a pollinator-service pathway.
- `body_size_only`: effective service influences flower size but does not impose
  the second threshold on outcrossing, assurance, or guide strength.
- `small_bee_substitution`: non-Bombus small bees are allowed to be at least as
  effective as the *Bombus ardens* bridge for the modelled service quantity.
- `ardens_bridge_loss`: *B. ardens* is constrained to be more effective than the
  small-bee composite; lower service can increase autonomous assurance and
  reduce the guide-maintenance margin.

Each scenario integrates over broad, documented parameter ranges by prior Monte
Carlo.  The reported `log_marginal_compatibility` is **not** a historical Bayes
factor.  It is a reproducible score under the chosen scenario restrictions,
observation scales, and priors.

## Directional guide/spot evidence

`data/guide_direction_constraints.csv` is intentionally empty at first.  Add a
row only after the source itself has been inspected and preserved in the source
registry.

```csv
constraint_id,left_island,right_island,relation,source_id,source_noise,notes
reviewed_001,Oshima,Hachijo,gt,source_locator,1.0,What was compared and why it is comparable
```

Use `gt` for "left has stronger guide/spot expression than right" and `lt` for
the reverse.  `source_noise` must be larger for a single uncalibrated photograph
than for a consistent, independently scored image series.  Do **not** enter a
comparison merely because an image appears visually persuasive at a glance.

## Running

```bash
python scripts/run_island_multichannel_analysis.py \
  --input data/inoue_literature_island_traits.csv \
  --guide-constraints data/guide_direction_constraints.csv \
  --output-json artifacts/island_multichannel_analysis.json \
  --output-md artifacts/island_multichannel_analysis.md
```

The script also creates leave-one-channel-out rankings.  A scenario whose rank
changes after omitting one channel is not robust to that channel's uncertainty.

## Interpretation guardrails

1. Public occurrence records can update availability candidates only.  They do
   not measure flower visitation, pollen deposition, or pollinator effectiveness.
2. Bagged seed/capsule outcomes do not measure realised natural selfing rate and
   do not establish a long-term selfing advantage without later fitness data.
3. A directional guide constraint opens a trait channel but does not establish
   heritability, selection, or historical trait loss.
4. The current climate proxy layer is intentionally limited.  Before treating an
   environment-only result as strong, extend it with reviewed island area,
   elevation/ruggedness, mainland and nearest-island distances, land cover, and
   alternate extraction geometries.
5. The output is a compatibility map.  It identifies which claims survive the
   available evidence and which are still sensitivity-only; it does not convert
   an underidentified history into a proven mechanism.
