from channel_id.discrimination import MeasurementOption, rank_measurements
from channel_id.life_history import (
    CompatibilityResult,
    LifeHistoryParameters,
    LifeHistoryResult,
    Metric,
)


def _report(seed_budget: float, recruits: float, seeds: float) -> CompatibilityResult:
    parameters = LifeHistoryParameters(
        seed_budget=seed_budget,
        baseline_outcross_fraction=0.0,
        attraction_pollination_gain=0.0,
        attraction_cost=0.0,
        assurance_cost=0.0,
        selfing_viability=1.0,
        baseline_establishment=0.5,
    )
    result = LifeHistoryResult(
        outcross_viable_seeds=0.0,
        selfed_viable_seeds=seeds,
        local_viable_seed_output=seeds,
        establishment=0.5,
        retained_recruits=recruits,
    )
    return CompatibilityResult(
        parameters=parameters,
        compatible=True,
        failures=(),
        predictions={"island": result},
    )


def test_ranking_prefers_measurement_that_separates_candidates() -> None:
    compatible = (
        _report(1.0, recruits=1.0, seeds=2.0),
        _report(2.0, recruits=1.0, seeds=4.0),
        _report(3.0, recruits=1.0, seeds=6.0),
    )
    options = (
        MeasurementOption("island", Metric.RETAINED_RECRUITS, resolution=0.1),
        MeasurementOption("island", Metric.LOCAL_VIABLE_SEED_OUTPUT, resolution=0.1),
    )

    rankings = rank_measurements(compatible, options)

    assert rankings[0].option.metric is Metric.LOCAL_VIABLE_SEED_OUTPUT
    assert rankings[0].outcome_class_sizes == (1, 1, 1)
    assert rankings[0].expected_eliminated_candidates == 2.0
    assert rankings[1].outcome_class_sizes == (3,)
    assert rankings[1].expected_eliminated_candidates == 0.0


def test_resolution_can_remove_nominal_separation() -> None:
    compatible = (
        _report(1.0, recruits=1.0, seeds=2.0),
        _report(2.0, recruits=1.0, seeds=2.05),
        _report(3.0, recruits=1.0, seeds=2.10),
    )

    ranking = rank_measurements(
        compatible,
        (MeasurementOption("island", Metric.LOCAL_VIABLE_SEED_OUTPUT, resolution=0.2),),
    )[0]

    assert ranking.outcome_class_sizes == (3,)
    assert ranking.expected_remaining_candidates == 3.0


def test_rejects_incompatible_reports() -> None:
    report = _report(1.0, recruits=1.0, seeds=2.0)
    invalid = CompatibilityResult(
        parameters=report.parameters,
        compatible=False,
        failures=("existing failure",),
        predictions=report.predictions,
    )

    try:
        rank_measurements(
            (report, invalid),
            (MeasurementOption("island", Metric.RETAINED_RECRUITS, resolution=0.1),),
        )
    except ValueError as error:
        assert "compatible" in str(error)
    else:
        raise AssertionError("incompatible candidates must be rejected")
