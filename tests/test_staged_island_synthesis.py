from channel_id.staged_island_synthesis import IslandScenario, default_island_observations, sweep_scenarios


def test_source_transcriptions_include_expected_island_channels():
    outcrossing, flowers = default_island_observations()
    assert len(outcrossing) == 10
    assert len(flowers) == 4
    assert {row.island for row in flowers} == {'Oshima', 'Toshima', 'Niijima', 'Hachijo'}


def test_sweep_is_reproducible_and_comparative():
    first = sweep_scenarios(draws=50, seed=123)
    second = sweep_scenarios(draws=50, seed=123)
    assert first == second
    assert {row.scenario for row in first} == set(IslandScenario)
    assert all(0.0 <= row.compatibility_rate <= 1.0 for row in first)
