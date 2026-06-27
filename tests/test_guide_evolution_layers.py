from channel_id.guide_inbreeding import PostSeedSurvival, apply_post_seed_survival
from channel_id.guide_multiguild import PollinatorGuild, simulate_multiguild_guide_response
from channel_id.guide_phenotype import GuideReactionNorm
from channel_id.guide_spatial import Patch, distribute_seeds_to_patches
from channel_id.guide_temporal import YearPerformance, summarise_temporal_fitness
from channel_id.nectar_guide import NectarGuideTrait


def test_guilds_can_have_opposite_guide_responses() -> None:
    trait_low = NectarGuideTrait(guide_contrast=0.0, display=0.5, assurance=0.2)
    trait_high = NectarGuideTrait(guide_contrast=1.0, display=0.5, assurance=0.2)
    guilds = (
        PollinatorGuild(
            name="large_bee", service=1.0, baseline_visit_rate=0.5, guide_visit_gain=1.0,
            baseline_legitimate_fraction=0.5, guide_handling_gain=0.3,
            pollen_deposition_per_contact=1.0, pollen_export_per_visit=1.0,
            guide_export_gain=0.2, siring_conversion=0.5,
        ),
        PollinatorGuild(
            name="small_fly", service=1.0, baseline_visit_rate=1.0, guide_visit_gain=0.0,
            baseline_legitimate_fraction=0.1, guide_handling_gain=0.0,
            pollen_deposition_per_contact=0.1, pollen_export_per_visit=0.1,
            siring_conversion=0.1,
        ),
    )
    low = simulate_multiguild_guide_response(trait_low, guilds)
    high = simulate_multiguild_guide_response(trait_high, guilds)
    assert high.expected_visits > low.expected_visits
    assert high.deposition_pressure > low.deposition_pressure
    assert high.pollen_export > low.pollen_export


def test_late_inbreeding_depression_can_remove_seed_set_compensation() -> None:
    weak = apply_post_seed_survival(2.0, 8.0, PostSeedSurvival(0.5, 0.0))
    strong = apply_post_seed_survival(2.0, 8.0, PostSeedSurvival(0.5, 0.9))
    assert strong.selfed_recruits < weak.selfed_recruits
    assert strong.total_recruits < weak.total_recruits


def test_geometric_mean_penalizes_variance_and_zero_years() -> None:
    stable = summarise_temporal_fitness((YearPerformance("a", 2.0), YearPerformance("b", 2.0)))
    variable = summarise_temporal_fitness((YearPerformance("a", 1.0), YearPerformance("b", 3.0)))
    zero = summarise_temporal_fitness((YearPerformance("a", 0.0), YearPerformance("b", 4.0)))
    assert stable.arithmetic_mean == variable.arithmetic_mean
    assert stable.geometric_mean > variable.geometric_mean
    assert zero.geometric_mean == 0.0
    assert zero.zero_contribution_states == ("a",)


def test_reaction_norm_separates_genetic_and_environmental_inputs() -> None:
    same_genetic_low_env = GuideReactionNorm(genetic_baseline=0.5, plastic_slope=0.4, environment=0.0)
    same_genetic_high_env = GuideReactionNorm(genetic_baseline=0.5, plastic_slope=0.4, environment=1.0)
    assert same_genetic_low_env.expressed_guide_contrast < same_genetic_high_env.expressed_guide_contrast


def test_spatial_layer_can_change_recruitment_without_changing_seed_output() -> None:
    patches = (Patch("poor", establishment_probability=0.1, capacity=100), Patch("good", establishment_probability=0.8, capacity=100))
    poor_destination = distribute_seeds_to_patches(10.0, patches, (1.0, 0.0))
    good_destination = distribute_seeds_to_patches(10.0, patches, (0.0, 1.0))
    assert good_destination.total_retained_recruits > poor_destination.total_retained_recruits


def test_spatial_capacity_prevents_unbounded_recruitment() -> None:
    result = distribute_seeds_to_patches(1000.0, (Patch("small", 1.0, 5.0),), (1.0,))
    assert result.total_retained_recruits == 5.0
