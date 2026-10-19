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


def test_pl_statement_totals_and_signs():
    out = ui.pl_statement(
        1000.0, [ui.Line("Feed", 700.0), ui.Line("G&A", 0.0), ui.Line("Barn", 400.0)], 10, 20, 50.0
    )
    assert "$1,100" in out  # total cost
    assert "net neg" in out and "−$100" in out  # net margin is a loss
    assert "−$150" in out  # after debt service
    assert '<td class="dash">' in out  # a zero line shows dashes
    assert "110.0%" in out  # total cost as % of revenue


def test_rank_table_orders_and_marks_selected():
    rows = [
        {"location": "A <x>", "net": -2.0, "cost": 160, "corn": 4.3, "sbm": 380},
        {"location": "B", "net": 1.5, "cost": 158, "corn": 4.1, "sbm": 390},
    ]
    out = ui.rank_table(rows, "A <x>")
    assert out.index(">B<") < out.index("A &lt;x&gt;")  # best first, names escaped
    assert "+$3.50" in out  # B vs the selected A
    assert 'class="sel"' in out


def test_guide_and_footer_render():
    assert "Breakeven" in ui.guide() and "<script" not in ui.guide()
    assert "v1.2.3" in ui.footer("1.2.3", "Offline")
