from channel_id.guide_paternal import PaternalGuideParameters, simulate_guide_paternal_fitness
from channel_id.nectar_guide import NectarGuideParameters, NectarGuideRegime, NectarGuideTrait


MATERNAL = NectarGuideParameters(
    seed_budget=10.0,
    display_cost=0.0,
    guide_cost=0.0,
    assurance_cost=0.0,
    baseline_visit_rate=0.4,
    display_visit_gain=0.0,
    guide_visit_gain=0.0,
    baseline_legitimate_fraction=0.2,
    guide_handling_gain=0.0,
    pollen_to_outcross_fraction=1.0,
    selfing_viability=0.6,
    baseline_establishment=0.2,
)


def test_paternal_path_can_favour_guides_without_maternal_effect() -> None:
    paternal = PaternalGuideParameters(
        baseline_pollen_export=1.0,
        display_export_gain=0.0,
        guide_export_gain=2.0,
        baseline_siring_success=0.5,
        male_weight=1.0,
    )
    regime = NectarGuideRegime(pollinator_service=0.8)
    low = simulate_guide_paternal_fitness(
        NectarGuideTrait(guide_contrast=0.0, display=0.5, assurance=0.2), regime, MATERNAL, paternal
    )
    high = simulate_guide_paternal_fitness(
        NectarGuideTrait(guide_contrast=1.0, display=0.5, assurance=0.2), regime, MATERNAL, paternal
    )

    assert high.maternal_retained_recruits == low.maternal_retained_recruits
    assert high.expected_pollen_export > low.expected_pollen_export
    assert high.paternal_retained_recruits > low.paternal_retained_recruits
    assert high.total_genetic_contribution > low.total_genetic_contribution
