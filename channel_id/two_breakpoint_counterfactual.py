"""Counterfactual toy model for staged pollinator replacement and loss.

This model is intentionally a *sensitivity engine*, not a reconstruction of
Izu history.  It asks whether a declared parameter setting has the qualitative
signature expected when floral-size adaptation occurs after replacement by
*Bombus ardens*, while spotting and outcrossing remain favoured until Bombus
service is no longer effectively substituted.

All efficiencies, guide benefits, and optima are assumptions until separately
constrained by audited evidence.  The output therefore labels model predictions,
not observed island states.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Mapping, Sequence


class PollinatorRegime(str, Enum):
    LARGE_BOMBUS = "large_bombus"
    ARDENS = "ardens"
    NO_BOMBUS = "no_bombus"


class TwoBreakpointScenario(str, Enum):
    ENVIRONMENT_ONLY = "environment_only"
    BODY_SIZE_ONLY = "body_size_only"
    SMALL_BEE_SUBSTITUTION = "small_bee_substitution"
    ARDENS_REPLACEMENT_LOSS = "ardens_replacement_loss"


def _unit_interval(value: float, name: str) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must lie in [0, 1]")


def _finite(value: float, name: str) -> None:
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")


@dataclass(frozen=True)
class TwoBreakpointParameters:
    """Declared sensitivity parameters for one counterfactual sweep.

    ``*_effectiveness`` is effective outcross service per unit availability,
    not a visit rate or a measured pollination probability. ``*_spot_benefit``
    is the model-scale benefit of retaining spots in the corresponding regime.
    The three floral-size optima share an arbitrary common trait scale.
    """

    large_bombus_effectiveness: float
    ardens_effectiveness: float
    small_bee_effectiveness: float
    large_bombus_spot_benefit: float
    ardens_spot_benefit: float
    small_bee_spot_benefit: float
    spot_cost: float
    autonomous_selfing_pressure: float
    background_small_bee_availability: float
    large_bombus_flower_size_optimum: float
    ardens_flower_size_optimum: float
    small_bee_flower_size_optimum: float
    environment_outcross_fraction: float = 0.5
    environment_spot_margin: float = 0.0
    environment_flower_size_optimum: float = 0.0

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            _finite(value, name)
        for name in (
            "large_bombus_effectiveness",
            "ardens_effectiveness",
            "small_bee_effectiveness",
            "large_bombus_spot_benefit",
            "ardens_spot_benefit",
            "small_bee_spot_benefit",
            "spot_cost",
            "autonomous_selfing_pressure",
            "background_small_bee_availability",
            "environment_outcross_fraction",
        ):
            _unit_interval(getattr(self, name), name)


@dataclass(frozen=True)
class CounterfactualPrediction:
    """Predicted state under a scenario and a declared pollinator regime."""

    scenario: TwoBreakpointScenario
    regime: PollinatorRegime
    floral_size_optimum: float
    effective_outcross_service: float | None
    expected_outcross_fraction: float
    spot_selection_margin: float
    spots_predicted_retained: bool
    selfing_selection_margin: float | None


def regime_availability(
    regime: PollinatorRegime,
    parameters: TwoBreakpointParameters,
) -> tuple[float, float, float]:
    """Return declared large-Bombus, *B. ardens*, and small-bee availability."""

    small_background = parameters.background_small_bee_availability
    if regime is PollinatorRegime.LARGE_BOMBUS:
        return 1.0, 0.0, small_background
    if regime is PollinatorRegime.ARDENS:
        return 0.0, 1.0, small_background
    if regime is PollinatorRegime.NO_BOMBUS:
        return 0.0, 0.0, 1.0
    raise ValueError(f"unknown regime {regime!r}")


def _outcross_fraction(service: float, autonomous_selfing_pressure: float) -> float:
    """Map model-scale service to an expected outcross fraction.

    The formula is a bounded convenience mapping. It is not a mating-system
    estimator and should not be fitted to a field outcrossing value without a
    separate observation model.
    """

    denominator = service + autonomous_selfing_pressure
    return 0.0 if denominator == 0.0 else service / denominator


def _pollinator_prediction(
    scenario: TwoBreakpointScenario,
    regime: PollinatorRegime,
    parameters: TwoBreakpointParameters,
) -> CounterfactualPrediction:
    large, ardens, small = regime_availability(regime, parameters)
    size = (
        large * parameters.large_bombus_flower_size_optimum
        + ardens * parameters.ardens_flower_size_optimum
        + small * parameters.small_bee_flower_size_optimum
    ) / (large + ardens + small)

    if scenario is TwoBreakpointScenario.BODY_SIZE_ONLY:
        # The flower-size optimum responds to the available body-size class, but
        # spot retention and mating outcomes are intentionally not tied to the
        # second, Bombus-loss threshold in this competing scenario.
        baseline_service = max(
            parameters.large_bombus_effectiveness,
            parameters.ardens_effectiveness,
            parameters.small_bee_effectiveness,
        )
        return CounterfactualPrediction(
            scenario,
            regime,
            size,
            baseline_service,
            _outcross_fraction(baseline_service, parameters.autonomous_selfing_pressure),
            parameters.large_bombus_spot_benefit - parameters.spot_cost,
            parameters.large_bombus_spot_benefit >= parameters.spot_cost,
            None,
        )

    if scenario is TwoBreakpointScenario.SMALL_BEE_SUBSTITUTION:
        # Under this scenario non-Bombus small bees are declared to substitute
        # fully for the *B. ardens* route in both outcross service and guide
        # benefit. Their supplied effectiveness/benefit is deliberately ignored.
        effective_small = max(parameters.small_bee_effectiveness, parameters.ardens_effectiveness)
        effective_small_spot = max(parameters.small_bee_spot_benefit, parameters.ardens_spot_benefit)
    else:
        effective_small = parameters.small_bee_effectiveness
        effective_small_spot = parameters.small_bee_spot_benefit

    service = (
        large * parameters.large_bombus_effectiveness
        + ardens * parameters.ardens_effectiveness
        + small * effective_small
    )
    spot_benefit = (
        large * parameters.large_bombus_spot_benefit
        + ardens * parameters.ardens_spot_benefit
        + small * effective_small_spot
    ) / (large + ardens + small)
    margin = spot_benefit - parameters.spot_cost
    return CounterfactualPrediction(
        scenario,
        regime,
        size,
        service,
        _outcross_fraction(service, parameters.autonomous_selfing_pressure),
        margin,
        margin >= 0.0,
        parameters.autonomous_selfing_pressure - service,
    )


def simulate_two_breakpoint_counterfactual(
    scenario: TwoBreakpointScenario,
    regime: PollinatorRegime,
    parameters: TwoBreakpointParameters,
) -> CounterfactualPrediction:
    """Return one scenario prediction without assigning it to a real island."""

    if scenario is TwoBreakpointScenario.ENVIRONMENT_ONLY:
        margin = parameters.environment_spot_margin
        return CounterfactualPrediction(
            scenario=scenario,
            regime=regime,
            floral_size_optimum=parameters.environment_flower_size_optimum,
            effective_outcross_service=None,
            expected_outcross_fraction=parameters.environment_outcross_fraction,
            spot_selection_margin=margin,
            spots_predicted_retained=margin >= 0.0,
            selfing_selection_margin=None,
        )
    return _pollinator_prediction(scenario, regime, parameters)


def compare_two_breakpoint_scenarios(
    parameters_by_scenario: Mapping[TwoBreakpointScenario, TwoBreakpointParameters],
    scenarios: Sequence[TwoBreakpointScenario] = tuple(TwoBreakpointScenario),
    regimes: Sequence[PollinatorRegime] = tuple(PollinatorRegime),
) -> tuple[CounterfactualPrediction, ...]:
    """Cross scenarios and regimes for an explicitly declared sensitivity setting."""

    selected_scenarios = tuple(scenarios)
    selected_regimes = tuple(regimes)
    if not selected_scenarios or not selected_regimes:
        raise ValueError("at least one scenario and one regime are required")
    missing = [scenario.value for scenario in selected_scenarios if scenario not in parameters_by_scenario]
    if missing:
        raise ValueError("missing parameter sets for scenarios: " + ", ".join(missing))
    return tuple(
        simulate_two_breakpoint_counterfactual(scenario, regime, parameters_by_scenario[scenario])
        for scenario in selected_scenarios
        for regime in selected_regimes
    )


def ardens_removal_contrast(
    scenario: TwoBreakpointScenario,
    parameters: TwoBreakpointParameters,
) -> tuple[CounterfactualPrediction, CounterfactualPrediction]:
    """Hold all declared parameters fixed and compare retained versus removed *B. ardens*."""

    return (
        simulate_two_breakpoint_counterfactual(scenario, PollinatorRegime.ARDENS, parameters),
        simulate_two_breakpoint_counterfactual(scenario, PollinatorRegime.NO_BOMBUS, parameters),
    )
