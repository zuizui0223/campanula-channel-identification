import pytest

from channel_id.two_breakpoint_counterfactual import (
    PollinatorRegime,
    TwoBreakpointParameters,
    TwoBreakpointScenario,
    ardens_removal_contrast,
    compare_two_breakpoint_scenarios,
    simulate_two_breakpoint_counterfactual,
)


def replacement_loss_parameters() -> TwoBreakpointParameters:
    return TwoBreakpointParameters(
        large_bombus_effectiveness=0.9,
        ardens_effectiveness=0.8,
        small_bee_effectiveness=0.1,
        large_bombus_spot_benefit=0.8,
        ardens_spot_benefit=0.7,
        small_bee_spot_benefit=0.1,
        spot_cost=0.3,
        autonomous_selfing_pressure=0.2,
        background_small_bee_availability=0.1,
        large_bombus_flower_size_optimum=1.0,
        ardens_flower_size_optimum=0.6,
        small_bee_flower_size_optimum=0.4,
    )


def test_ardens_replacement_loss_has_two_breakpoint_signature_under_declared_values() -> None:
    parameters = replacement_loss_parameters()
    large = simulate_two_breakpoint_counterfactual(
        TwoBreakpointScenario.ARDENS_REPLACEMENT_LOSS,
        PollinatorRegime.LARGE_BOMBUS,
        parameters,
    )
    ardens, no_bombus = ardens_removal_contrast(
        TwoBreakpointScenario.ARDENS_REPLACEMENT_LOSS,
        parameters,
    )

    assert ardens.floral_size_optimum < large.floral_size_optimum
    assert ardens.spots_predicted_retained
    assert ardens.expected_outcross_fraction > 0.7
    assert not no_bombus.spots_predicted_retained
    assert no_bombus.expected_outcross_fraction < ardens.expected_outcross_fraction
    assert no_bombus.selfing_selection_margin is not None
    assert no_bombus.selfing_selection_margin > 0.0


def test_small_bee_substitution_removes_the_second_breakpoint_by_construction() -> None:
    parameters = replacement_loss_parameters()
    _, no_bombus = ardens_removal_contrast(
        TwoBreakpointScenario.SMALL_BEE_SUBSTITUTION,
        parameters,
    )

    assert no_bombus.spots_predicted_retained
    assert no_bombus.expected_outcross_fraction > 0.7
    assert no_bombus.selfing_selection_margin is not None
    assert no_bombus.selfing_selection_margin < 0.0


def test_environment_only_does_not_turn_pollinator_regimes_into_measured_service() -> None:
    parameters = replacement_loss_parameters()
    ardens = simulate_two_breakpoint_counterfactual(
        TwoBreakpointScenario.ENVIRONMENT_ONLY,
        PollinatorRegime.ARDENS,
        parameters,
    )
    no_bombus = simulate_two_breakpoint_counterfactual(
        TwoBreakpointScenario.ENVIRONMENT_ONLY,
        PollinatorRegime.NO_BOMBUS,
        parameters,
    )

    assert ardens.effective_outcross_service is None
    assert no_bombus.effective_outcross_service is None
    assert ardens.expected_outcross_fraction == pytest.approx(no_bombus.expected_outcross_fraction)
    assert ardens.floral_size_optimum == pytest.approx(no_bombus.floral_size_optimum)


def test_comparison_requires_a_parameter_set_for_every_requested_scenario() -> None:
    with pytest.raises(ValueError, match="missing parameter sets"):
        compare_two_breakpoint_scenarios(
            {TwoBreakpointScenario.ARDENS_REPLACEMENT_LOSS: replacement_loss_parameters()},
            scenarios=(
                TwoBreakpointScenario.ARDENS_REPLACEMENT_LOSS,
                TwoBreakpointScenario.SMALL_BEE_SUBSTITUTION,
            ),
        )


def test_effectiveness_and_benefit_inputs_are_declared_bounded_assumptions() -> None:
    with pytest.raises(ValueError, match="small_bee_effectiveness"):
        TwoBreakpointParameters(
            **{
                **replacement_loss_parameters().__dict__,
                "small_bee_effectiveness": 1.2,
            }
        )
