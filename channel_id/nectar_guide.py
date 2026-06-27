"""A mechanism-explicit nectar-guide model for Campanula.

The purpose is not to assume that a nectar guide is an attraction trait with a
single effect.  It separates four candidate pathways:

1. guide contrast can increase encounter/visitation;
2. guide contrast can increase legitimate handling conditional on a visit;
3. guide expression can carry an allocation or pigment-maintenance cost;
4. autonomous or delayed selfing can compensate for un-outcrossed ovules.

The model reports expected life-history components, plus a *conditional
relative-performance contrast* between two guide phenotypes.  That contrast is
not an evolutionary claim unless heritable variation, the relevant census
window, and competing explanations are independently addressed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import exp, isclose


def _unit_interval(value: float, name: str) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must lie in [0, 1]")


def _nonnegative(value: float, name: str) -> None:
    if value < 0.0:
        raise ValueError(f"{name} must be non-negative")


@dataclass(frozen=True)
class NectarGuideTrait:
    """Declared floral phenotype on scaled axes.

    ``guide_contrast`` is a predeclared visual contrast measure, not a colour
    category. ``display`` may represent flower size, display area, nectar, or
    another separately declared display axis. ``assurance`` represents the
    capacity for autonomous or delayed selfing.
    """

    guide_contrast: float
    display: float
    assurance: float

    def __post_init__(self) -> None:
        _unit_interval(self.guide_contrast, "guide_contrast")
        _unit_interval(self.display, "display")
        _unit_interval(self.assurance, "assurance")


@dataclass(frozen=True)
class NectarGuideRegime:
    """Exogenous interaction and establishment conditions."""

    pollinator_service: float
    establishment_multiplier: float = 1.0

    def __post_init__(self) -> None:
        _unit_interval(self.pollinator_service, "pollinator_service")
        _nonnegative(self.establishment_multiplier, "establishment_multiplier")


@dataclass(frozen=True)
class NectarGuideParameters:
    """Mechanism-specific parameters for a declared guide hypothesis.

    Setting a pathway coefficient to zero explicitly removes that pathway. For
    example, a pure handling hypothesis uses ``guide_visit_gain=0`` and a
    positive ``guide_handling_gain``. This makes candidate mechanisms directly
    comparable rather than hiding all guide effects inside one attraction term.
    """

    seed_budget: float
    display_cost: float
    guide_cost: float
    assurance_cost: float
    baseline_visit_rate: float
    display_visit_gain: float
    guide_visit_gain: float
    baseline_legitimate_fraction: float
    guide_handling_gain: float
    pollen_to_outcross_fraction: float
    selfing_viability: float
    baseline_establishment: float

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            _nonnegative(value, name)
        _unit_interval(self.baseline_legitimate_fraction, "baseline_legitimate_fraction")
        _unit_interval(self.selfing_viability, "selfing_viability")
        _unit_interval(self.baseline_establishment, "baseline_establishment")


@dataclass(frozen=True)
class NectarGuideResult:
    """Expected observables and life-history quantities per maternal flower."""

    remaining_seed_budget: float
    expected_visits: float
    legitimate_contact_fraction: float
    outcross_fraction: float
    outcross_viable_seeds: float
    selfed_viable_seeds: float
    local_viable_seed_output: float
    establishment: float
    retained_recruits: float


class GuideSelectionDirection(str, Enum):
    """Conditional relative-performance direction for contrasting phenotypes."""

    FAVOURS_HIGHER_GUIDE = "favours_higher_guide"
    FAVOURS_LOWER_GUIDE = "favours_lower_guide"
    INDETERMINATE_AT_TOLERANCE = "indeterminate_at_tolerance"


@dataclass(frozen=True)
class GuideContrast:
    """Performance comparison of two declared phenotypes in one regime.

    The direction is only a relative-performance result conditional on this
    model. It is not a population-genetic prediction and does not establish
    historical evolution.
    """

    lower_guide: NectarGuideResult
    higher_guide: NectarGuideResult
    retained_recruit_difference: float
    retained_recruit_ratio: float | None
    direction: GuideSelectionDirection


def simulate_nectar_guide_life_history(
    trait: NectarGuideTrait,
    regime: NectarGuideRegime,
    parameters: NectarGuideParameters,
) -> NectarGuideResult:
    """Evaluate the declared guide -> visit -> handling -> F -> E -> W life cycle.

    The outcross fraction follows a saturating process:

    ``1 - exp(- expected_visits * legitimate_contact_fraction * conversion)``.

    Thus visitation and handling are mathematically distinguishable: a guide
    may change encounter rate, legitimate contact conditional on a visit, both,
    neither, or yield a net loss if its cost exceeds its reproductive benefit.
    """

    remaining_budget = max(
        0.0,
        parameters.seed_budget
        - parameters.display_cost * trait.display**2
        - parameters.guide_cost * trait.guide_contrast**2
        - parameters.assurance_cost * trait.assurance**2,
    )
    expected_visits = regime.pollinator_service * (
        parameters.baseline_visit_rate
        + parameters.display_visit_gain * trait.display
        + parameters.guide_visit_gain * trait.guide_contrast
    )
    legitimate_contact_fraction = min(
        1.0,
        parameters.baseline_legitimate_fraction
        + parameters.guide_handling_gain * trait.guide_contrast,
    )
    outcross_fraction = 1.0 - exp(
        -expected_visits
        * legitimate_contact_fraction
        * parameters.pollen_to_outcross_fraction
    )
    outcross_viable_seeds = remaining_budget * outcross_fraction
    selfed_viable_seeds = (
        remaining_budget
        * (1.0 - outcross_fraction)
        * trait.assurance
        * parameters.selfing_viability
    )
    local_viable_seed_output = outcross_viable_seeds + selfed_viable_seeds
    establishment = min(
        1.0,
        parameters.baseline_establishment * regime.establishment_multiplier,
    )
    retained_recruits = local_viable_seed_output * establishment
    return NectarGuideResult(
        remaining_seed_budget=remaining_budget,
        expected_visits=expected_visits,
        legitimate_contact_fraction=legitimate_contact_fraction,
        outcross_fraction=outcross_fraction,
        outcross_viable_seeds=outcross_viable_seeds,
        selfed_viable_seeds=selfed_viable_seeds,
        local_viable_seed_output=local_viable_seed_output,
        establishment=establishment,
        retained_recruits=retained_recruits,
    )


def compare_guide_phenotypes(
    lower_guide_trait: NectarGuideTrait,
    higher_guide_trait: NectarGuideTrait,
    regime: NectarGuideRegime,
    parameters: NectarGuideParameters,
    tolerance: float = 1e-9,
) -> GuideContrast:
    """Compare guide phenotypes while requiring all non-guide traits to match."""

    if lower_guide_trait.guide_contrast > higher_guide_trait.guide_contrast:
        raise ValueError("lower_guide_trait must not exceed higher_guide_trait")
    if not isclose(lower_guide_trait.display, higher_guide_trait.display):
        raise ValueError("display must match when contrasting guide phenotypes")
    if not isclose(lower_guide_trait.assurance, higher_guide_trait.assurance):
        raise ValueError("assurance must match when contrasting guide phenotypes")
    if tolerance < 0.0:
        raise ValueError("tolerance must be non-negative")

    lower = simulate_nectar_guide_life_history(lower_guide_trait, regime, parameters)
    higher = simulate_nectar_guide_life_history(higher_guide_trait, regime, parameters)
    difference = higher.retained_recruits - lower.retained_recruits
    if difference > tolerance:
        direction = GuideSelectionDirection.FAVOURS_HIGHER_GUIDE
    elif difference < -tolerance:
        direction = GuideSelectionDirection.FAVOURS_LOWER_GUIDE
    else:
        direction = GuideSelectionDirection.INDETERMINATE_AT_TOLERANCE

    ratio = None if lower.retained_recruits == 0.0 else higher.retained_recruits / lower.retained_recruits
    return GuideContrast(
        lower_guide=lower,
        higher_guide=higher,
        retained_recruit_difference=difference,
        retained_recruit_ratio=ratio,
        direction=direction,
    )
