# Virtual Izu-gradient benchmark

## Purpose

This benchmark comes **before** empirical inference.  It asks whether the
current observation pipeline can recover a declared guide mechanism when both
floral traits and environmental conditions vary along a recognisable island
axis.

It is deliberately a synthetic landscape.  The default island labels provide
an ordinal north-to-south scaffold only.  They do **not** represent measured
inter-island distance, climate, habitat, pollinator service, focal-taxon
occurrence, or a recommended sampling frame.

## Why this test matters

A geographic trend can be mistaken for a guide effect when guide contrast and
environmental conditions covary.  The benchmark therefore compares two analysis
modes:

```text
CALIBRATED       candidate model receives the declared pollinator-service and
                 establishment gradients for each virtual island.

FLAT_ENVIRONMENT candidate model keeps the guide trait gradient but replaces
                 environmental values with their archipelago-wide mean.
```

The gap between these results is a warning flag: it measures how much mechanism
recovery depends on knowing the environmental background instead of attributing
all island differences to floral traits.

## Virtual landscape

```python
from channel_id.izu_gradient_benchmark import IzuGradientLandscape

landscape = IzuGradientLandscape(
    guide_contrast_north=0.10,
    guide_contrast_south=0.90,
    pollinator_service_north=0.80,
    pollinator_service_south=0.40,
    establishment_multiplier_north=1.00,
    establishment_multiplier_south=0.70,
)
```

Each endpoint is an explicit sensitivity assumption.  Change the signs,
strengths, or constancy of the slopes rather than treating these values as
estimates for any real island.

The module maps each ordinal position to:

- guide contrast in `NectarGuideTrait`;
- pollinator service in `ScenarioYear`;
- establishment multiplier in `ScenarioYear`.

It then generates both camera observations (`EXPECTED_VISITS`,
`LEGITIMATE_CONTACT_FRACTION`) and fruit/paternity observations
(`OUTCROSS_VIABLE_SEEDS`, `SELFED_VIABLE_SEEDS`) at every virtual site.

## Run a benchmark

```python
from channel_id.camera_visit_handling import CameraVisitHandlingDesign
from channel_id.guide_scenarios import GuideScenario
from channel_id.izu_gradient_benchmark import (
    GradientAnalysisMode,
    benchmark_izu_gradient_recovery,
)
from channel_id.seed_set_paternity import SeedSetPaternityDesign

camera = CameraVisitHandlingDesign(
    flower_camera_windows=1_000,
    exposure_multiplier_per_window=1.0,
    visit_detection_probability=0.85,
    legitimate_annotation_sensitivity=0.90,
    legitimate_annotation_specificity=0.95,
)
seed = SeedSetPaternityDesign(
    maternal_individuals=40,
    fruits_per_maternal=2,
    potential_ovules_per_fruit=10,
    genotyped_mature_seeds_per_fruit=3,
)

summary = benchmark_izu_gradient_recovery(
    truth=GuideScenario.VISIT_ATTRACTION,
    candidates=(
        GuideScenario.NULL,
        GuideScenario.VISIT_ATTRACTION,
        GuideScenario.HANDLING,
        GuideScenario.ASSURANCE,
    ),
    template_settings=settings,
    landscape=landscape,
    camera_design=camera,
    seed_design=seed,
    analysis_mode=GradientAnalysisMode.CALIBRATED,
    replicates=1_000,
    seed=20260630,
)
print(summary)
```

Run the same configuration with `FLAT_ENVIRONMENT`.  Compare truth retention,
unique recovery, empty compatible-set rate, and mean compatible scenarios.

## Recommended sensitivity suite

Before setting field targets, run at least these synthetic worlds:

1. **Null guide + environmental gradient:** guide contrast covaries with the
   archipelago but the true mechanism is null.  This is the false-positive
   stress test.
2. **Visit route + environmental gradient:** check how many camera windows are
   needed to distinguish visit attraction from the null route.
3. **Handling route + environmental gradient:** test whether video scoring
   quality, not raw visit count, becomes the bottleneck.
4. **Assurance route + environmental gradient:** test the added value of seed
   set and paternity subsampling when visitation becomes low.
5. **Compound visit + assurance route:** assess whether combined camera and
   genetic sampling can retain a biologically plausible joint route.

## Transition to real data

Only after this synthetic stage passes should the ordinal scaffold be replaced
with data-backed site covariates and protocol inputs: confirmed occurrence and
phenotype sites, geodesic isolation, elevation/topographic context, climate,
habitat or land-cover measurements, camera calibration, maternal/fruit
sampling, and parentage calibration.  The virtual benchmark tells us which of
those measurements are worth collecting first; it does not supply their values.
