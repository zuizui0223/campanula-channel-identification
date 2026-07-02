from pathlib import Path

import pytest

from channel_id.island_multichannel import (
    EvidenceChannel,
    GuideOrderConstraint,
    IslandEvidence,
    IslandScenario,
    ObservationScale,
    _reported_proportion_logit,
    _score_draw,
    _standardize_environment,
    compare_scenarios,
    draw_scenario_parameters,
    load_guide_order_constraints,
    load_island_evidence,
)


ROOT = Path(__file__).parents[1]
DATA = ROOT / "data" / "inoue_literature_island_traits.csv"
GUIDE = ROOT / "data" / "guide_direction_constraints.csv"


def test_loads_source_locked_island_table_without_filling_missing_environment() -> None:
    rows = load_island_evidence(DATA)

    assert {row.island_id for row in rows} == {
        "Honshu",
        "Oshima",
        "Toshima",
        "Niijima",
        "Kozushima",
        "Miyake",
        "Hachijo",
    }
    honshu = next(row for row in rows if row.island_id == "Honshu")
    assert honshu.environment == (None, None, None)
    assert honshu.outcrossing_mid == pytest.approx((0.733 + 0.794) / 2.0)


def test_empty_guide_constraint_file_is_a_valid_absent_channel() -> None:
    assert load_guide_order_constraints(GUIDE) == ()


def test_reported_bagging_endpoints_are_finite_and_not_literal_probabilities() -> None:
    assert _reported_proportion_logit(0.0) > -10.0
    assert _reported_proportion_logit(1.0) < 10.0
    assert _reported_proportion_logit(1.0) > _reported_proportion_logit(0.0)


def test_same_seed_gives_same_scenario_ranking() -> None:
    rows = load_island_evidence(DATA)
    first = compare_scenarios(rows, draws=250, seed=44)
    second = compare_scenarios(rows, draws=250, seed=44)

    assert first == second
    assert {row.scenario for row in first} == set(IslandScenario)
    assert all(row.included_channels == tuple(EvidenceChannel) for row in first)


def test_guide_direction_likelihood_prefers_matching_latent_order() -> None:
    left = IslandEvidence(
        "left", 0.0, 1.0, 0.0, 0.0, None, None, None, (0.0,)
    )
    right = IslandEvidence(
        "right", 0.0, 0.0, 1.0, 0.0, None, None, None, (0.0,)
    )
    constraint = GuideOrderConstraint("c1", "left", "right", "gt", "reviewed_source", 0.25)
    rng = __import__("random").Random(5)
    draw = draw_scenario_parameters(IslandScenario.ARDENS_BRIDGE_LOSS, 1, rng)
    standardized = _standardize_environment((left, right))
    matching = _score_draw(
        IslandScenario.ARDENS_BRIDGE_LOSS,
        (left, right),
        (constraint,),
        draw,
        standardized,
        ObservationScale(),
        {EvidenceChannel.GUIDE_ORDER},
    )
    reversed_constraint = GuideOrderConstraint("c2", "left", "right", "lt", "reviewed_source", 0.25)
    reversed_result = _score_draw(
        IslandScenario.ARDENS_BRIDGE_LOSS,
        (left, right),
        (reversed_constraint,),
        draw,
        standardized,
        ObservationScale(),
        {EvidenceChannel.GUIDE_ORDER},
    )

    assert matching.by_channel[EvidenceChannel.GUIDE_ORDER] > reversed_result.by_channel[EvidenceChannel.GUIDE_ORDER]
