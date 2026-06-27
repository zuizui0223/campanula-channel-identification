# Campanula F-versus-E channel-identification protocol

## Declared question

For a predeclared floral trait \(z\), does a between-regime difference arise through

\[
W(z)=F(z)E(z),
\]

where

- \(W(z)\): retained recruits per maternal individual over a declared census window;
- \(F(z)\): viable seed output per maternal individual conditional on adult survival;
- \(E(z)\): retained recruitment conditional on viable seed output?

This is a model-defined channel question. It is narrower than asking whether flower size, selfing, or a particular pollinator “caused” island divergence.

## Minimum observation set

1. **Common trait domain.** Compare the same individual-level trait values or predeclared bins in every regime. Island means alone are insufficient.
2. **Trait-specific total performance.** Measure \(W(z)\) on one declared census scale, including a predeclared treatment of zeros and stage transitions.
3. **One factor or a calibrated proxy.** Measure direct \(F(z)\) or \(E(z)\), or justify a proxy \(X_i(z)=q_i(z)F_i(z)\) whose conversion \(q_i(z)\) is stable across regimes or independently calibrated.
4. **Boundary handling.** The positive-interior algebra uses division. Structural zeroes, extinction, and zero-inflation require a separately declared analysis rather than silent division by zero.

With positive factors, observing \(W\) and either factor reconstructs the other:

\[
E=W/F,\qquad F=W/E.
\]

## What visit counts can and cannot do

A visit count is not a direct \(F\) measurement by default. It may act as a relative proxy only after the conversion from visits to viable reproductive output is shown stable across compared regimes or calibrated independently.

Therefore:

```text
F versus E identified
!=
pollinator-mediated reproduction versus autonomous selfing identified.
```

To make the latter attribution, predeclare a component model and relevant contrasts, for example open flowers, visitor exclusion, and supplemental pollination. These treatments are not automatically additive and can alter microclimate or autonomous selfing; their estimand must be explicit.

## Current status of the Izu case

The existing published record can motivate competing explanations using flower size, selfing, and pollinator-composition patterns. It does not by itself supply trait-specific \(W\), direct \(F\), direct \(E\), or a calibrated stable proxy.

The correct status for that record is therefore:

```text
not ready for F-versus-E identification
```

That is an actionable design result, not a negative scientific result. It specifies the measurements needed to turn the question into an identifiable one.
