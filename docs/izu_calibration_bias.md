# Virtual calibration-bias stress test

## Why this follows finite detection calibration

The finite-calibration benchmark asks whether independent reference visits can
repair a wrong fixed detection probability. In that virtual setting the answer
can look very strong even with few reference visits, because the reference
stream is assumed to match the primary footage and reveal known visit
opportunities.

That is not the whole field question. A calibration table can still be biased if
its clips were selected because they were bright, stable, or easy to annotate,
if calibration clips are pooled over wind/light conditions that do not match the
primary windows, or if that mismatch covaries with the same island axis used to
interpret floral-guide contrast.

This test therefore holds the raw virtual field data and finite calibration
counts fixed, then perturbs only the **analysis-side calibration estimate**.

## Synthetic bias cases

| Label | Meaning |
|---|---|
| `unbiased` | Beta-smoothed finite calibration estimate is used directly. |
| `easy_clip_bias` | Detection estimate is too high by +0.80 on the logit scale, representing easier-than-typical calibration clips. |
| `south_optimistic_gradient` | Calibration optimism increases north-to-south by 2.00 logit units across the ordinal island axis. |
| `south_pessimistic_gradient` | Calibration pessimism increases north-to-south by 2.00 logit units across the ordinal island axis. |
| `easy_clip_plus_gradient_mismatch` | Global easy-clip bias, north-to-south mismatch, and residual site mismatch apply together. |

These magnitudes are not field estimates. They are deliberate stress settings
that ask whether calibration quality matters for route recovery, including when
calibration error can mimic or erase the guide-contrast gradient.

## Run the report

```bash
python scripts/generate_izu_calibration_bias_report.py \
  --replicates 25 \
  --output artifacts/izu_calibration_bias.md
```

The artifact keeps the reference budget fixed at 50 independent known visits per
virtual site-condition and compares visit and visit-plus-assurance worlds under
wind/light and combined field stress.

## Interpret the columns

- `nominal unique top`: scorer incorrectly retains the design's fixed nominal
  detection probability.
- `unbiased unique top`: finite reference calibration is matched to the primary
  site-condition.
- `biased unique top`: the same calibration estimate is distorted according to
  the listed bias case.
- `Δ biased vs unbiased`: loss caused by calibration mismatch, not by reducing
  the number of reference visits.

A large loss means collecting more calibration clips without preserving their
selection method or wind/light match is not enough. A loss that appears only for
the north-to-south gradient cases is especially important: it means detection
calibration can confound the same geographic pattern used to distinguish the
mechanism.

## Field implication

The target is not one global detection rate. Keep each calibration clip linked
to its source `window_id`, exposure, device, wind, light, and selection method.
Use random or stratified-random clips for ordinary detection estimation, retain
targeted clips separately, and pool sparse strata only through a prespecified
model rather than silently averaging them. In particular, check whether
condition coverage differs systematically between northern and southern sites
before interpreting a cross-island guide effect.