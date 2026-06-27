# Campanula Channel Identification

A field-design, causal-identification, and constrained-simulation repository for asking a deliberately narrow question about island floral-trait variation:

\[
W(z)=F(z)E(z).
\]

For a predeclared trait \(z\), can a difference between island regimes be assigned to

- **local reproduction** \(F(z)\), or
- **establishment / reachability conditional on viable seed output** \(E(z)\),

rather than merely described as a difference in flower size, selfing, or visitor identity?

## What this repository does

- records the minimum theorem-compatible measurement design for the factorisation above;
- distinguishes direct measurements from proxies whose calibration must be stable or independently checked;
- keeps published patterns, prospective field measurements, and pollinator-specific claims separate;
- provides a lightweight readiness checker for a proposed sampling design;
- provides a constrained life-history simulation layer for comparing explicitly declared mechanisms against predeclared observation intervals.

The simulation layer does not estimate an unobserved cost from a trait alone. It retains the **set of parameter values compatible with all declared observations**, then makes the remaining uncertainty and the next discriminating measurement explicit. See [the simulation specification](docs/constrained_life_history_simulation.md).

## What it does not claim

A visit count is not automatically a measurement of local reproduction. Likewise, flower-size means, selfing rates, and pollinator turnover alone do not identify \(F\) versus \(E\).

A successful simulated reconstruction is not proof that its mechanism generated the field pattern. It is only a compatibility result conditional on a declared life cycle, parameter ranges, and measurement intervals.

The factorisation is a declared model choice. It does not claim that all natural processes are multiplicative or independent.

## Repository boundary

This is the active empirical design home for the Campanula/Izu channel-identification program extracted from `microdonta`.

The constrained life-history layer is currently limited to attraction and reproductive-assurance hypotheses inside local reproduction \(F\). Direct trait effects on establishment, richer spatial dynamics, and the legacy attraction/mating-system ABM remain in `incubator/` until each has an explicit hypothesis, declared life cycle, measurable observation set, and falsification or discrimination target.