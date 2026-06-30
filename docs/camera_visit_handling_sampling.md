# Camera visit and handling observation design

## Why camera records need a separate observation model

A recorded visit is not automatically a visit-rate observation, and a labelled
"legitimate" visit is not automatically a legitimate-contact fraction.  For a
camera-based assay, the field-facing hierarchy is:

```text
flower × camera window
  └ true visits
      ├ detected visit / missed visit
      └ for each detected visit
          ├ call: legitimate handling
          └ call: non-legitimate handling
```

`channel_id.camera_visit_handling` maps this hierarchy to two scenario metrics:

- `EXPECTED_VISITS`: camera detection-corrected visit rate;
- `LEGITIMATE_CONTACT_FRACTION`: annotation-error-corrected fraction of visits
  with the declared legitimate handling event.

Keeping them separate is what lets the design distinguish an attraction route
from a handling route.  The scenario engine already treats those as different
quantities rather than collapsing both into visit number.

## Declared calibration inputs

```python
from channel_id.camera_visit_handling import CameraVisitHandlingDesign

plan = CameraVisitHandlingDesign(
    flower_camera_windows=1_000,
    exposure_multiplier_per_window=1.0,
    visit_detection_probability=0.85,
    legitimate_annotation_sensitivity=0.90,
    legitimate_annotation_specificity=0.95,
    familywise_confidence=0.95,
)
```

`flower_camera_windows` is the number of declared independent flower-by-window
units, after deciding how windows are spaced and which recordings are treated
as repeated observations of the same flower or plant.

`exposure_multiplier_per_window` is essential.  The current scenario model
expresses expected visits on a maternal-flower scale, whereas field video has a
duration and field-of-view.  This multiplier maps one camera window to that
scenario scale.  It must come from a predeclared observation protocol or pilot
data; it is **not** automatically the number of camera minutes.

`visit_detection_probability`, annotation sensitivity, and annotation
specificity should be estimated from double scoring, reference clips, or a
calibration subsample.  They should not silently be set to 1.0 in an empirical
design unless that is actually justified.

## Virtual data-generating process

For each virtual survey, the model:

1. draws a Poisson total of true visits over the declared exposure;
2. draws a legitimate/non-legitimate status for each true visit;
3. applies the visit detection probability;
4. applies the legitimate-handling annotation sensitivity/specificity to each
   detected visit;
5. returns an approximate Poisson interval for expected visits and a Wilson
   interval for the error-corrected handling fraction.

The two intervals are Bonferroni-calibrated for their declared familywise
coverage.  They are then submitted together to `recover_compatible_scenarios`.

## Recovery benchmark

```python
from channel_id.guide_scenarios import GuideScenario
from channel_id.camera_visit_handling import benchmark_camera_visit_handling_recovery

summary = benchmark_camera_visit_handling_recovery(
    truth=GuideScenario.HANDLING,
    candidates=(
        GuideScenario.NULL,
        GuideScenario.VISIT_ATTRACTION,
        GuideScenario.HANDLING,
    ),
    settings=settings,
    year_label="typical",
    design=plan,
    replicates=1_000,
    seed=20260630,
)
print(summary)
```

Interpret the outputs as design operating characteristics, not biological
estimates: truth retention, unique recovery, empty compatible sets, mean
compatible scenarios, and mean detected visits.

## Not yet covered

This module does not fit a final video-analysis model.  It currently excludes:

- plant, site, day, and camera random effects;
- autocorrelation among windows;
- pollinator identity or repeated visitor trajectories;
- detection that depends on handling class, flower position, weather, or video
  quality;
- annotation errors that are correlated across scorers or clips.

Those additions belong in a later hierarchical empirical likelihood, once the
Izu protocol has fixed camera duration, camera placement, scoring rules, and
pilot calibration data.
