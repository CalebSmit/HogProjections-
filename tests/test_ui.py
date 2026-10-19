"""HTML builders: escaping, number formats, the hero gauge, the crush table."""

import re
from datetime import date

from hogproj import ui
from hogproj.crush import ROWS, Week, crush_table
from tests.test_crush_parity import (
    CORN_FUT,
    DDG,
    LH_BASIS,
    LH_FUT,
    SBM_FUT,
    USDA_WP,
    app_projection,
)


def test_user_text_is_escaped():
    out = ui.header("T", "e", [("Location", "<script>x</script> & Co")], ("offline", "n"))
    assert "<script>" not in out and "&lt;script&gt;" in out and "&amp; Co" in out
    assert "<b>" not in ui.stat_list([("<b>", "1")])


def test_usd_uses_a_real_minus():
    assert ui.usd(-2.274) == "−$2.27"
    assert ui.usd(-0.001) == "$0.00"
    assert ui.usd(1234.5, 0) == "$1,234"  # banker's rounding: 1234.5 -> 1234


def test_hero_gauge_is_clamped_and_says_which_side():
    out = ui.hero_card(-2.27, 50.0, 77.24)  # far below the gauge's 80% floor
    lefts = [float(x) for x in re.findall(r"left:([\d.]+)%", out)]
    assert all(0 <= x <= 100 for x in lefts)
    assert "below breakeven" in out and "Projected loss" in out and "loss" in out
    assert "above breakeven" in ui.hero_card(5.0, 80.0, 77.0)


def test_crush_table_groups_and_flags_losses():
    weeks = [Week(date(2026, 9, 13), USDA_WP, CORN_FUT, SBM_FUT, DDG, LH_FUT, LH_BASIS)]
    table = crush_table(app_projection(), weeks, 1, 160, 290.0)
    money = {label for label, _, _ in ROWS} | {"USDA weaned pig $/hd"}
    out = ui.crush_table(table, money)
    for group in ("Timing", "Prices", "Per pig", "Costs per pig"):
        assert f">{group}</td>" in out
    assert "Sep 13" in out and "Average" in out
    margin = float(table.loc["Margin $/pig", "2026-09-13"])  # type: ignore[arg-type]
    assert ("pos" if margin > 0 else "neg") in out.split("Margin $/pig")[1].split("</tr>")[0]
