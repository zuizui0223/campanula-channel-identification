# Separating visit attraction from legitimate handling

## The field-design problem

A nectar guide can increase the number of visits, the probability that a visit
makes a legitimate contact, or both.  Flower-level seed output alone generally
cannot identify those routes.  A visit count alone can also leave a compound
`visit + handling` route indistinguishable from a `visit`-only route, because
both predict the same expected number of encounters.

The scenario layer now exposes three intermediate observables for each year and
maternal-flower scale:

- `expected_visits`: encounters per maternal flower;
- `legitimate_contact_fraction`: the fraction of visits expected to make a
  legitimate contact; and
- `expected_legitimate_contacts`: visits multiplied by that fraction.

It also exposes `stigma_pollen_deposition`, an **effective deposition pressure**
used in the declared saturation rule:

```text
expected legitimate contacts
    = expected visits × legitimate-contact fraction

stigma-pollen deposition
    = expected legitimate contacts × pollen-to-outcross conversion

outcross fraction
    = 1 - exp(-stigma-pollen deposition)
```

`stigma_pollen_deposition` is deliberately not labelled a raw pollen-grain
count.  A field study must predeclare how stigma counts, pollen fluorescence,
or another assay are calibrated onto the model's effective deposition scale.

## Virtual validation included in the test suite

`tests/test_handling_deposition_design_power.py` defines a virtual truth with
both routes active:

```text
visit + handling
```

and compares it with `null`, `visit`, and `handling` candidates.

Under exact virtual observations, visits alone leave two candidates compatible:

```text
visit
visit + handling
```

Adding either the legitimate-contact fraction or effective deposition makes the
compound truth uniquely compatible.  Under a finite-noise normal planning
approximation (`n = 40` effective units), the test requires the intermediate
plans to have a unique-truth recovery rate above 0.85 while visits alone remains
at zero unique recovery by construction.

This is a **synthetic demonstration of the declared model**, not an empirical
claim about Campanula.  The result will change with the candidate routes,
parameter ranges, sampling unit, observation model, and independent effective
sample size.

## Recommended Izu pilot measurements

For every scored flower or observation bout, retain the raw information needed
to rebuild each intermediate quantity:

1. flower identity, site, plant identity, guide treatment or contrast, display,
   nectar, flower age, and observation window;
2. visitor taxon or functional guild;
3. number of visits and total flower-minutes;
4. number of visits that touch the stigma/anthers in a predeclared legitimate
   manner, including video or observer-coding uncertainty;
5. stigma pollen deposition assay result, assay batch, and blank/control data;
6. outcross versus selfed seed or progeny result when feasible; and
7. weather, time block, and site/matched-population identifiers.

A natural guide contrast is still only observational.  To make the exposure
causal, manipulate guide contrast with a credible sham treatment while holding
display, nectar, flower age, and handling disturbance as constant as possible.

## Run the virtual comparison

```bash
python examples/handling_deposition_design_power.py
```

Replace the virtual standard deviations with pilot estimates.  Do not substitute
the normal planning approximation for a binomial contact model, a count model
for pollen deposition, or a hierarchical model when repeated flowers, plants,
sessions, sites, and years are present.
