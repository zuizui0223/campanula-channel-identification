from channel_id.discrimination import MeasurementOption, rank_measurements
from channel_id.life_history import (
    LifeHistoryParameters,
    Metric,
    ObservationInterval,
    ParameterGrid,
    Regime,
    SimulationCase,
    TraitState,
    retain_compatible_candidates,
    simulate_life_history,
)


PARAMETERS = LifeHistoryParameters(
    seed_budget=10.0,
    baseline_outcross_fraction=0.10,
    attraction_pollination_gain=1.00,
    attraction_cost=0.40,
    assurance_cost=0.20,
    selfing_viability=0.75,
    baseline_establishment=0.20,
)


def test_attraction_signature_increases_outcross_component() -> None:
    regime = Regime(pollinator_service=0.70)
    low = simulate_life_history(TraitState(attraction=0.10, assurance=0.20), regime, PARAMETERS)
    high = simulate_life_history(TraitState(attraction=0.80, assurance=0.20), regime, PARAMETERS)

    assert high.outcross_viable_seeds > low.outcross_viable_seeds
    assert high.establishment == low.establishment


def test_assurance_signature_increases_selfed_component_under_low_service() -> None:
    regime = Regime(pollinator_service=0.10)
    low = simulate_life_history(TraitState(attraction=0.20, assurance=0.10), regime, PARAMETERS)
    high = simulate_life_history(TraitState(attraction=0.20, assurance=0.80), regime, PARAMETERS)

    assert high.selfed_viable_seeds > low.selfed_viable_seeds
    # The small decline in the outcross component is expected here because the
    # declared assurance investment carries a seed-budget cost.
    assert high.outcross_viable_seeds < low.outcross_viable_seeds
    assert high.local_viable_seed_output > low.local_viable_seed_output


def test_establishment_signature_changes_w_without_changing_f() -> None:
    trait = TraitState(attraction=0.30, assurance=0.70)
    low = simulate_life_history(
        trait,
        Regime(pollinator_service=0.30, establishment_multiplier=0.50),
        PARAMETERS,
    )
    high = simulate_life_history(
        trait,
        Regime(pollinator_service=0.30, establishment_multiplier=1.50),
        PARAMETERS,
    )

    assert high.local_viable_seed_output == low.local_viable_seed_output
    assert high.retained_recruits > low.retained_recruits


def test_w_only_leaves_f_vs_e_ambiguity_and_ranking_splits_it() -> None:
    trait = TraitState(attraction=0.30, assurance=0.70)
    mainland_regime = Regime(pollinator_service=0.55, establishment_multiplier=1.00)
    island_regime = Regime(pollinator_service=0.25, establishment_multiplier=1.50)
    mainland_truth = simulate_life_history(trait, mainland_regime, PARAMETERS)
    island_truth = simulate_life_history(trait, island_regime, PARAMETERS)

    cases = (
        SimulationCase(
            name="mainland",
            trait=trait,
            regime=mainland_regime,
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
            regime=island_regime,
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

    assert len(compatible) > 1
    rankings = rank_measurements(
        compatible,
        (
            MeasurementOption("island", Metric.LOCAL_VIABLE_SEED_OUTPUT, 0.10),
            MeasurementOption("island", Metric.OUTCROSS_VIABLE_SEEDS, 0.10),
            MeasurementOption("island", Metric.SELFED_VIABLE_SEEDS, 0.10),
            MeasurementOption("island", Metric.ESTABLISHMENT, 0.01),
        ),
    )

    assert rankings[0].option.metric is Metric.SELFED_VIABLE_SEEDS
    assert rankings[0].expected_eliminated_candidates > 0.0