"""Synthetic checks for Campanula mechanism discrimination.

This example creates three intentionally stylised virtual data-generating
processes and asks whether the constrained simulator reproduces the expected
life-history signatures.  It is a software and design benchmark, not evidence
about real Campanula populations.

Run with:

    python examples/synthetic_mechanism_benchmark.py
"""

from __future__ import annotations

from channel_id.discrimination import MeasurementOption, rank_measurements
from channel_id.life_history import (
    LifeHistoryParameters,
    Metric,
    ObservationInterval,
    ParameterGrid,
    Regime,
    SimulationCase,
    TraitState,
    assess_compatibility,
    retain_compatible_candidates,
    simulate_life_history,
)


BASE = dict(
    seed_budget=10.0,
    baseline_outcross_fraction=0.10,
    attraction_pollination_gain=1.00,
    attraction_cost=0.40,
    assurance_cost=0.20,
    selfing_viability=0.75,
    baseline_establishment=0.20,
)


def print_result(name: str, result) -> None:
    print(
        f"{name:26s} "
        f"outcross={result.outcross_viable_seeds:5.2f}  "
        f"selfed={result.selfed_viable_seeds:5.2f}  "
        f"F={result.local_viable_seed_output:5.2f}  "
        f"E={result.establishment:4.2f}  "
        f"W={result.retained_recruits:5.2f}"
    )


def attraction_signature() -> None:
    """High attraction raises outcross seed under appreciable pollinator service."""

    parameters = LifeHistoryParameters(**BASE)
    regime = Regime(pollinator_service=0.70)
    low = simulate_life_history(TraitState(attraction=0.10, assurance=0.20), regime, parameters)
    high = simulate_life_history(TraitState(attraction=0.80, assurance=0.20), regime, parameters)
    print("\nAttraction signature")
    print_result("high service / low A", low)
    print_result("high service / high A", high)


def assurance_signature() -> None:
    """High assurance raises selfed seed when pollinator service is low."""

    parameters = LifeHistoryParameters(**BASE)
    regime = Regime(pollinator_service=0.10)
    low = simulate_life_history(TraitState(attraction=0.20, assurance=0.10), regime, parameters)
    high = simulate_life_history(TraitState(attraction=0.20, assurance=0.80), regime, parameters)
    print("\nAssurance signature")
    print_result("low service / low R", low)
    print_result("low service / high R", high)


def establishment_signature() -> None:
    """Changing establishment changes W but preserves F by construction."""

    parameters = LifeHistoryParameters(**BASE)
    trait = TraitState(attraction=0.30, assurance=0.70)
    low_e = simulate_life_history(
        trait,
        Regime(pollinator_service=0.30, establishment_multiplier=0.50),
        parameters,
    )
    high_e = simulate_life_history(
        trait,
        Regime(pollinator_service=0.30, establishment_multiplier=1.50),
        parameters,
    )
    print("\nEstablishment signature")
    print_result("low establishment", low_e)
    print_result("high establishment", high_e)


def discrimination_signature() -> None:
    """Show why F resolves an F-versus-E ambiguity left by W alone."""

    true_parameters = LifeHistoryParameters(**BASE)
    trait = TraitState(attraction=0.30, assurance=0.70)
    mainland = Regime(pollinator_service=0.55, establishment_multiplier=1.00)
    island = Regime(pollinator_service=0.25, establishment_multiplier=1.50)
    mainland_truth = simulate_life_history(trait, mainland, true_parameters)
    island_truth = simulate_life_history(trait, island, true_parameters)

    # Deliberately only constrain W initially, allowing F/E compensation.
    cases = (
        SimulationCase(
            name="mainland",
            trait=trait,
            regime=mainland,
            observations=(
                ObservationInterval(
                    Metric.RETAINED_RECRUITS,
                    mainland_truth.retained_recruits - 0.05,
                    mainland_truth.retained_recruits + 0.05,
                ),
            ),
        ),
        SimulationCase(
            name="island",
            trait=trait,
            regime=island,
            observations=(
                ObservationInterval(
                    Metric.RETAINED_RECRUITS,
                    island_truth.retained_recruits - 0.05,
                    island_truth.retained_recruits + 0.05,
                ),
            ),
        ),
    )
    grid = ParameterGrid(
        seed_budget=(8.0, 10.0, 12.0),
        baseline_outcross_fraction=(0.10,),
        attraction_pollination_gain=(0.60, 1.00, 1.40),
        attraction_cost=(0.00, 0.40),
        assurance_cost=(0.00, 0.20),
        selfing_viability=(0.50, 0.75, 1.00),
        baseline_establishment=(0.15, 0.20, 0.25),
    )
    compatible = retain_compatible_candidates(grid, cases)
    rankings = rank_measurements(
        compatible,
        (
            MeasurementOption("island", Metric.LOCAL_VIABLE_SEED_OUTPUT, 0.10),
            MeasurementOption("island", Metric.OUTCROSS_VIABLE_SEEDS, 0.10),
            MeasurementOption("island", Metric.SELFED_VIABLE_SEEDS, 0.10),
            MeasurementOption("island", Metric.ESTABLISHMENT, 0.01),
        ),
    )

    print("\nF-versus-E discrimination from W-only synthetic observations")
    print(f"compatible candidates: {len(compatible)}")
    for ranking in rankings:
        print(
            f"{ranking.option.display_name:32s} "
            f"eliminates {ranking.expected_eliminated_candidates:5.2f} "
            f"of {ranking.candidate_count}; classes={ranking.outcome_class_sizes}"
        )

    # Smoke-check that the true parameterization remains compatible.
    truth_report = assess_compatibility(true_parameters, cases)
    assert truth_report.compatible


if __name__ == "__main__":
    attraction_signature()
    assurance_signature()
    establishment_signature()
    discrimination_signature()
