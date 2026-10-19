import pytest

from hogproj.ui import MINUS, md, signed, usd, usd_short


@pytest.mark.parametrize(
    ("x", "decimals", "expected"),
    [
        (11.6, 2, "$11.60"),
        (-11.6, 2, f"{MINUS}$11.60"),
        (-0.004, 2, "$0.00"),
        (-0.4, 0, "$0"),
        (-1234.5, 0, f"{MINUS}$1,234"),
    ],
)
def test_usd(x, decimals, expected):
    assert usd(x, decimals) == expected


def test_minus_is_typographic_and_unbreakable():
    assert MINUS == "−⁠"  # true minus + word joiner


def test_usd_short_and_signed():
    assert usd_short(-869_092) == f"{MINUS}$869k"
    assert usd_short(1_234_567) == "$1.23M"
    assert signed(1.5) == "+$1.50"
    assert signed(-1.5) == f"{MINUS}$1.50"
    assert signed(0.0) == "$0.00"


def test_md_escapes_dollars_for_widget_labels():
    assert md("Corn $5.25 · SBM $300") == r"Corn \$5.25 · SBM \$300"
