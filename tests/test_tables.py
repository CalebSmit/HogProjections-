import math

import pandas as pd
import pytest

from hogproj.inputs import Location
from hogproj.tables import fill_curve, parse_basis, parse_cuts, parse_locations, parse_phases

NAN = float("nan")


def test_phase_with_one_blank_cell_is_reported_not_dropped():
    df = pd.DataFrame(
        [
            {
                "name": "A",
                "feed_lb_per_pig": 100,
                "corn_pct": 60,
                "sbm_pct": 20,
                "ddgs_pct": 15,
                "other_usd_ton": 900,
            },
            {
                "name": "B",
                "feed_lb_per_pig": NAN,
                "corn_pct": 60,
                "sbm_pct": 20,
                "ddgs_pct": 15,
                "other_usd_ton": 900,
            },
            {
                "name": None,
                "feed_lb_per_pig": NAN,
                "corn_pct": NAN,
                "sbm_pct": NAN,
                "ddgs_pct": NAN,
                "other_usd_ton": NAN,
            },
        ]
    )
    phases, problems = parse_phases(df)
    assert [p.name for p in phases] == ["A"]
    assert problems == ["Feed phase 'B' is missing: feed_lb_per_pig"]


def test_cuts_must_total_100_and_report_blanks():
    df = pd.DataFrame(
        [
            {"days_after_placement": 150.0, "pct_of_marketed": 50, "live_weight_lb": 280},
            {"days_after_placement": 170.0, "pct_of_marketed": NAN, "live_weight_lb": 290},
        ]
    )
    cuts, problems = parse_cuts(df)
    assert len(cuts) == 1
    assert "Marketing row 2 is missing: pct_of_marketed" in problems
    assert any("add up to 100" in p for p in problems)


def test_locations_reject_nan_duplicates_and_empty():
    good = Location(
        name="X",
        corn_basis_usd_bu=-0.4,
        sbm_basis_usd_ton=30,
        ddgs_usd_ton=180,
        barn_rent_usd_space_yr=40,
        labor_wage_usd_hr=18,
    ).model_dump()
    bad = {**good, "name": "Y", "ddgs_usd_ton": NAN}
    locs, problems = parse_locations(pd.DataFrame([good, bad, good]))
    assert [lo.name for lo in locs] == ["X", "X"]
    assert "Location 'Y' is missing: ddgs_usd_ton" in problems
    assert any("unique" in p for p in problems)
    assert parse_locations(pd.DataFrame(columns=list(good)))[1] == ["Keep at least one location."]


def test_location_model_rejects_nan_directly():
    with pytest.raises(ValueError):
        Location(
            name="Z",
            corn_basis_usd_bu=NAN,
            sbm_basis_usd_ton=0,
            ddgs_usd_ton=0,
            barn_rent_usd_space_yr=0,
            labor_wage_usd_hr=0,
        )


def test_blank_basis_is_zero():
    df = pd.DataFrame({"period": [1, 2], "basis_cwt": [NAN, -1.5]})
    assert parse_basis(df) == {1: 0.0, 2: -1.5}


def test_fill_curve_copies_nearest_contract():
    curve, filled = fill_curve(
        {"2027-04": 74.0, "2026-12": 66.0}, ["2027-04", "2027-05", "2027-06"]
    )
    assert curve == {"2027-04": 74.0, "2027-05": 74.0, "2027-06": 74.0}
    assert filled == {"2027-05": "2027-04", "2027-06": "2027-04"}
    curve, filled = fill_curve({"2027-02": 69.0}, ["2027-02"])
    assert filled == {} and curve["2027-02"] == 69.0
    assert fill_curve({}, ["2027-04"]) == ({}, {})
    assert not math.isnan(curve["2027-02"])
