import importlib.util
from pathlib import Path


SCRIPT_PATH = Path("scripts/score_pollinator_hierarchy_counterfactual.py")
spec = importlib.util.spec_from_file_location("score_pollinator_hierarchy_counterfactual", SCRIPT_PATH)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

load_records = module.load_records
score = module.score


def test_loaded_literature_matrix_contains_expected_islands():
    records = load_records(Path("data/inoue_literature_island_traits.csv"))
    assert [r.island_id for r in records] == [
        "Honshu",
        "Oshima",
        "Toshima",
        "Niijima",
        "Kozushima",
        "Miyake",
        "Hachijo",
    ]


def test_pollinator_hierarchy_is_compared_against_environment_and_isolation():
    result = score(load_records(Path("data/inoue_literature_island_traits.csv")))
    models = {row["model"] for row in result["model_scores"]}
    assert models == {"pollinator_hierarchy", "environment_only", "isolation_order"}
    assert len(result["island_rows"]) >= 6


def test_stage_bridge_for_oshima_is_explicit():
    rows = {row["island_id"]: row for row in score(load_records(Path("data/inoue_literature_island_traits.csv")))["island_rows"]}
    assert rows["Honshu"]["pollinator_stage_prediction"] == 0.0
    assert rows["Oshima"]["pollinator_stage_prediction"] == 0.5
    assert rows["Hachijo"]["pollinator_stage_prediction"] == 1.0
