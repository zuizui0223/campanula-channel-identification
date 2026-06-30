# Two-breakpoint public-evidence and counterfactual workflow

## Research question

The focal hypothesis is not simply that smaller flowers evolved with smaller
bees. It distinguishes two transitions:

```text
large Bombus regime
    → Bombus ardens regime
    → no-Bombus / low-effective-outcross regime
```

The proposed signature is temporally staggered:

1. floral-size optimum can shift at the first transition;
2. spotting and predominantly outcrossed reproduction can remain while
   *Bombus ardens* supplies effective outcross service;
3. spotting loss and selection favouring autonomous selfing become plausible
   only after effective Bombus service is lost or no longer substitutable.

This is the `ardens_replacement_loss` scenario. It must be compared with:

| Scenario ID | Competing explanation |
|---|---|
| `environment_only` | Environment, isolation, history, or plasticity explain the traits without a pollinator-regime pathway. |
| `body_size_only` | Floral size follows pollinator size continuously; spotting and mating system need not show a second threshold. |
| `small_bee_substitution` | Non-Bombus small bees substitute effectively, so Bombus loss alone should not predict spotting loss or increased selfing. |
| `ardens_replacement_loss` | *B. ardens* retains effective outcross service and guide benefit after the first transition, but non-Bombus small bees do not fully substitute after the second. |

No scenario is treated as true before evidence comparison.

## Architecture borrowed from Biotic Interaction Trait Architecture

The accompanying theory repository separates robustness, public-data
feasibility, and effect synthesis rather than forcing a single global join. This
workflow follows the same order:

```text
Part I   counterfactual two-breakpoint model and robustness sweep
Part II  public-evidence feasibility and source-locatable claim registry
Part III evidence-specific parameter envelopes and comparative scenario audit
```

The initial repository addition implements Part II and the firewall between Part
II and Parts I/III. It is intentionally useful before any public record has
been entered.

## Evidence layers

### Layer 1 — source facts

A source fact is a claim with a stable source, precise locator, method, time,
place, and denominator/exposure where relevant.

Examples:

- a paper table reporting a multilocus outcrossing estimate for a named island;
- a checklist recording *Bombus ardens* during a stated period;
- a georeferenced occurrence record with event date and identification status;
- a photograph from which spot fraction was measured under a documented image
  protocol.

### Layer 2 — derived evidence

These are reproducible transformations, not source facts:

- historical-to-accepted taxon mapping;
- island-level aggregation of occurrences with explicit filtering;
- species-distribution-model predictions;
- photographic spot measurements;
- comparison of trait distributions across taxonomic or geographic groups.

Derived outputs must point to their input record IDs and code version. They may
constrain a scenario only after the derivation is documented and reviewed.

### Layer 3 — scenario assumptions

These are unknown biological quantities deliberately varied in a simulation:

- relative effective-outcross efficiency of *B. ardens*;
- relative effectiveness of non-Bombus small bees;
- spotting benefit through handling or pollen placement;
- autonomous selfing compensation;
- inbreeding-depression range when no directly matching census is available;
- timing of pollinator replacement/loss.

They remain `sensitivity_only` or `not_identified` unless an audited claim
supports a transparent mapping. A simulation must label them as assumptions in
its outputs.

## LLM-assisted collection protocol

Use an LLM to **find, transcribe, and structure candidates**, not to determine
facts independently.

1. Give the LLM one source at a time.
2. Require one candidate claim per row.
3. Require exact page/table/figure/supplement location and a short verbatim
   basis.
4. Keep the historical taxon name and accepted name in separate fields.
5. Mark every LLM-produced row `candidate` and `not_reviewed`.
6. A human checks the original source and promotes a row to `verified` /
   `reviewed`, or rejects it.
7. Run the Python audit before an evidence row can become a scenario anchor.

The generated template includes the actual extraction prompt:

```bash
python scripts/audit_two_breakpoint_evidence.py \
  --write-templates data/two_breakpoint_evidence
```

The LLM contract explicitly forbids four common errors:

```text
unmentioned pollinator → absence
occurrence record → flower visitation
self-compatibility result → selfing rate
LLM summary → numerical simulation parameter
```

## Registry contents

### `sources.csv`

One retrieved source per row. It records citation, stable locator, source type,
retrieval date, LLM extraction stage, and human-review stage.

### `claims.csv`

One **source × claim** per row. It can contain competing and negative evidence.
Do not merge values from different studies into a synthetic island estimate.

For `selfing_rate` and `outcrossing_rate`, record a denominator/exposure, method,
and the distinction from autonomous selfing, self-compatibility, fruit set, and
seed set. A claimed pollinator absence needs an explicit sampling interval and
effort; otherwise use `pollinator_non_detection`.

### `scenario_constraints.csv`

One simulation parameter range per row. It has an explicit `assumption_class`:

| Class | Permitted use |
|---|---|
| `observed_anchor` | Reviewed direct measurement with a transparent mapping. |
| `derived_anchor` | Reviewed, reproducibly derived quantity with retained source claims and code. |
| `sensitivity_only` | Explicitly varied assumption; supporting claim IDs must remain empty. |
| `not_identified` | Parameter is unknown and not calibrated. |

## Public-data search docket

The first docket should collect records independently for each evidence channel.
Do not join sources during collection.

### A. Taxonomy and island identity

```text
Campanula microdonta / historical synonyms
island or population name as reported
accepted taxon source and taxonomic decision
```

### B. Mating system and reproductive assurance

```text
natural selfing / multilocus outcrossing / paternity estimate
hand self-pollination and hand outcrossing
bagged autonomous selfing
self-compatibility result
fitness census stage
sample size and year
```

### C. Pollinator regime

```text
Bombus ardens occurrence
other Bombus occurrence
non-Bombus small-bee occurrence
actual flower interaction record
non-detection with stated effort
source year and collection method
```

### D. Flower and spot phenotype

```text
spot presence or fraction
spot location relative to corolla
flower length/opening ratio
flower size category
photograph/measurement protocol
```

### E. Alternative explanatory axes

```text
climate
island area and isolation
elevation
land cover
spatial distance
neutral genomic structure when available
```

## Part I: counterfactual model to implement after the docket has records

The theoretical model will generate the expected pattern under all four
scenarios while varying unknowns over declared ranges:

\[
Q_i = A_{i,L}E_L + A_{i,A}E_A + A_{i,S}E_S,
\]

where \(Q_i\) is effective outcross service; \(A_{i,L}, A_{i,A}, A_{i,S}\) are
availability terms for large Bombus, *B. ardens*, and non-Bombus small bees; and
\(E_L,E_A,E_S\) are not observed facts unless independently calibrated.

The two-breakpoint scenario predicts that the first transition changes a
floral-size optimum, while the second changes the sign or magnitude of guide
benefit and the selective value of autonomous selfing. The counterfactuals must
include at least:

```text
B. ardens retained versus removed under the same island background
non-Bombus small-bee effectiveness low versus high
spot benefit zero versus positive
environment-only matched trait background
spatially/taxonomically matched availability controls when occurrence data exist
```

The output is an identifiability/compatibility map, not a reconstructed
historical truth.

## Audit command

```bash
python scripts/audit_two_breakpoint_evidence.py \
  --input-dir data/two_breakpoint_evidence \
  --output artifacts/two_breakpoint_evidence_audit.json
```

A passing audit means only that rows preserve their declared provenance and may
be used at their assigned evidence layer. It does not validate an ecological
claim or select a scenario.

## Manuscript-safe language

Appropriate:

> We assembled source-locatable public evidence on mating system, floral
> phenotype, and pollinator-regime availability, and used it to constrain or
> contextualise a counterfactual two-breakpoint sensitivity analysis. Unknown
> effectiveness and historical-transition parameters were retained as declared
> sensitivity ranges.

Not appropriate:

> Public occurrences demonstrated that *Bombus ardens* pollinated the focal
> flowers and caused the evolution of spotting.
