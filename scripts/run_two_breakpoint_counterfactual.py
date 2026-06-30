"""Run declared two-breakpoint counterfactual scenarios from a JSON configuration.

The configuration supplies sensitivity parameters, not empirical estimates. The
report labels predictions under four competing scenarios and three pollinator
regimes; it does not identify a real historical transition.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from channel_id.two_breakpoint_counterfactual import (
    PollinatorRegime,
    TwoBreakpointParameters,
    TwoBreakpointScenario,
    compare_two_breakpoint_scenarios,
)


def example_configuration() -> dict[str, object]:
    """Return a clearly synthetic, runnable example configuration."""

    base = {
        "large_bombus_effectiveness": 0.9,
        "ardens_effectiveness": 0.8,
        "small_bee_effectiveness": 0.1,
        "large_bombus_spot_benefit": 0.8,
        "ardens_spot_benefit": 0.7,
        "small_bee_spot_benefit": 0.1,
        "spot_cost": 0.3,
        "autonomous_selfing_pressure": 0.2,
        "background_small_bee_availability": 0.1,
        "large_bombus_flower_size_optimum": 1.0,
        "ardens_flower_size_optimum": 0.6,
        "small_bee_flower_size_optimum": 0.4,
        "environment_outcross_fraction": 0.5,
        "environment_spot_margin": 0.0,
        "environment_flower_size_optimum": 0.0,
    }
    return {
        "interpretation": "Synthetic sensitivity example only; no field value is encoded.",
        "parameters_by_scenario": {
            scenario.value: base for scenario in TwoBreakpointScenario
        },
    }


def render_markdown(predictions, interpretation: str) -> str:
    lines = [
        "# Two-breakpoint counterfactual sensitivity comparison",
        "",
        f"> {interpretation}",
        "",
        "| scenario | regime | flower-size optimum (arbitrary scale) | effective outcross service | expected outcross fraction | spot selection margin | spots predicted retained | selfing selection margin |",
        "|---|---|---:|---:|---:|---:|---|---:|",
    ]
    for row in predictions:
        service = "not modeled" if row.effective_outcross_service is None else f"{row.effective_outcross_service:.3f}"
        selfing = "not modeled" if row.selfing_selection_margin is None else f"{row.selfing_selection_margin:.3f}"
        lines.append(
            "| "
            + " | ".join(
                (
                    row.scenario.value,
                    row.regime.value,
                    f"{row.floral_size_optimum:.3f}",
                    service,
                    f"{row.expected_outcross_fraction:.3f}",
                    f"{row.spot_selection_margin:.3f}",
                    "yes" if row.spots_predicted_retained else "no",
                    selfing,
                )
            )
            + " |"
        )
    lines.extend(
        (
            "",
            "## Interpretation boundary",
            "",
            "Every row is a prediction under declared sensitivity parameters. `effective outcross service` is not a visit rate or empirical pollination estimate, and the table does not establish the historical presence, visitation, or causal effect of *Bombus ardens*.",
        )
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="JSON sensitivity configuration.")
    parser.add_argument(
        "--write-example-config",
        type=Path,
        default=None,
        help="Write a synthetic, explicitly non-empirical JSON example and exit.",
    )
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.write_example_config is not None:
        if args.config is not None:
            raise SystemExit("--write-example-config cannot be combined with --config")
        args.write_example_config.parent.mkdir(parents=True, exist_ok=True)
        args.write_example_config.write_text(
            json.dumps(example_configuration(), indent=2) + "\n", encoding="utf-8"
        )
        return
    if args.config is None:
        raise SystemExit("--config is required unless --write-example-config is used")
    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        parameter_rows = config["parameters_by_scenario"]
        parameters_by_scenario = {
            TwoBreakpointScenario(label): TwoBreakpointParameters(**values)
            for label, values in parameter_rows.items()
        }
        predictions = compare_two_breakpoint_scenarios(parameters_by_scenario)
        rendered = render_markdown(
            predictions,
            str(config.get("interpretation", "Declared sensitivity analysis.")),
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
