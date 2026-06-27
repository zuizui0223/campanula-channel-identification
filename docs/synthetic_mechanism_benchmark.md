# Synthetic mechanism-discrimination benchmark

## Purpose

Before inserting Campanula field data, the model needs to pass a more useful
test than arithmetic consistency: it should express different declared
mechanisms as different observable life-history signatures, and it should show
what data would distinguish mechanisms that remain compatible with a coarse
observation.

`examples/synthetic_mechanism_benchmark.py` and
`tests/test_synthetic_mechanisms.py` provide that check.

These are deliberately simulated data. They do **not** validate any hypothesis
about real island or mainland Campanula.

## Three virtual mechanisms

| Virtual mechanism | Manipulated model quantity | Expected observable signature |
|---|---|---|
| Attraction pathway | attraction `A` under high pollinator service | higher outcross viable seed output; `E` unchanged |
| Assurance pathway | assurance `R` under low pollinator service | higher selfed viable seed output; an investment cost can slightly reduce the outcross component |
| Establishment pathway | establishment multiplier | unchanged local viable seed output `F`; changed retained recruits `W` |

The benchmark is intentionally limited to effects already present in the
current declared life cycle. It does not test direct flower-colour effects on
seedling survival, spatial dispersal, genetic load, or temporal pollinator
variation; those need a later model extension and their own synthetic tests.

## F-versus-E ambiguity test

The benchmark creates a virtual mainland/island comparison and supplies only
an interval for retained recruits `W`. The candidate grid intentionally leaves
multiple parameter combinations compatible with that information.

This is the desired result: recruit output alone does not generally identify
whether the contrast came from seed production `F`, establishment `E`, or
compensation between the two.

The benchmark then ranks four possible island measurements:

- total local viable seed output `F`;
- outcross viable seeds;
- selfed viable seeds;
- establishment `E`.

For the declared virtual grid and measurement resolutions, selfed viable seeds
are the most discriminating option. That is not a universal field prediction.
It only demonstrates that the ranking tool recovers a component measurement
when W-only data leave attraction/assurance alternatives unresolved.

## Running

```bash
python examples/synthetic_mechanism_benchmark.py
python -m pytest -q
```

The first command prints the artificial signatures and the measurement-ranking
result. The second checks that those signatures persist when code changes.

## Acceptance standard

A future model extension should add a comparable synthetic benchmark before it
is used with field data. At minimum it must show:

1. a known virtual parameterization remains compatible with its generated
   observations;
2. the intended mechanism produces an observable signature distinct from the
   alternatives it claims to address;
3. an intentionally coarse observation leaves ambiguity when it should;
4. at least one additional observation can reduce that ambiguity at a stated
   measurement resolution.
