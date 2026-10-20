import numpy as np
import pytest

from hogproj.herd import HerdInputs, lags_weeks, simulate


def test_steady_state_matches_hand_calculation():
    # 1000 sows x 2.35 litters/yr / 52 = 45.19 farrowings/wk
    # x 14.3 born alive x (1 - 0.154) = 546.7 weaned/wk (≈ 28.43/sow/yr)
    # x (1 - 0.065) = 511.2 marketed/wk
    df = simulate(HerdInputs(weeks=52))
    farrowings = 1000 * 2.35 / 52
    weaned = farrowings * 14.3 * (1 - 0.154)
    assert df["farrowings"].to_numpy() == pytest.approx(farrowings)
    assert df["weaned_head"].to_numpy() == pytest.approx(weaned)
    assert df["marketed_head"].to_numpy() == pytest.approx(weaned * 0.935)
    assert df["sold_lb_carcass"].iloc[0] == pytest.approx(weaned * 0.935 * 283 * 0.75)
    assert weaned * 52 / 1000 == pytest.approx(28.43, abs=0.01)


def test_herd_change_arrives_after_biological_lags():
    inp = HerdInputs(sows_start=1000, sows_target=1500, change_week=5, weeks=80)
    df = simulate(inp).set_index("week")
    lag = lags_weeks(inp)
    assert lag == {"gestation": 16, "lactation": 3, "wean_to_market": 22}

    first_farrow = 5 + lag["gestation"]
    first_wean = first_farrow + lag["lactation"]
    first_market = first_wean + lag["wean_to_market"]
    for col, wk in [
        ("farrowings", first_farrow),
        ("weaned_head", first_wean),
        ("marketed_head", first_market),
    ]:
        assert df.loc[wk, col] == pytest.approx(1.5 * df.loc[wk - 1, col]), col
        assert df.loc[: wk - 1, col].nunique() == 1, col


@pytest.mark.parametrize("target", [600, 1000, 1800])
def test_head_counts_conserved(target):
    df = simulate(HerdInputs(sows_target=target, change_week=3, weeks=120))
    # Suckling phase: change in inventory = born alive - (weaned + died before weaning)
    d_suck = df["suckling_inventory_head"].diff().iloc[1:]
    flow_suck = (df["born_alive_head"] - df["weaned_head"] - df["prewean_deaths_head"]).iloc[1:]
    np.testing.assert_allclose(d_suck, flow_suck, atol=1e-6)
    # Growing phase: change in inventory = weaned - (marketed + died)
    d_grow = df["growing_inventory_head"].diff().iloc[1:]
    flow_grow = (df["weaned_head"] - df["marketed_head"] - df["wean_to_market_deaths_head"]).iloc[
        1:
    ]
    np.testing.assert_allclose(d_grow, flow_grow, atol=1e-6)


def test_zero_mortality_conserves_pigs_end_to_end():
    inp = HerdInputs(prewean_mortality=0, wean_to_market_mortality=0, weeks=60)
    df = simulate(inp)
    assert df["marketed_head"].to_numpy() == pytest.approx(df["born_alive_head"].to_numpy())


def test_output_shape():
    df = simulate(HerdInputs(weeks=52))
    assert len(df) == 52
    assert df["week"].tolist() == list(range(52))
    assert (df.drop(columns="week") >= 0).all().all()
