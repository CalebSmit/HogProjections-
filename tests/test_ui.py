import pytest

from hogproj.ui import usd


@pytest.mark.parametrize(
    ("x", "decimals", "expected"),
    [
        (11.6, 2, "$11.60"),
        (-11.6, 2, "−$11.60"),
        (-0.004, 2, "$0.00"),
        (-0.4, 0, "$0"),
        (-1234.5, 0, "−$1,234"),
    ],
)
def test_usd(x, decimals, expected):
    assert usd(x, decimals) == expected


def test_usd_short_and_signed():
    from hogproj.ui import signed, usd_short

    assert usd_short(-869_092) == "−$869k"
    assert usd_short(1_234_567) == "$1.23M"
    assert signed(1.5) == "+$1.50"
    assert signed(-1.5) == "−$1.50"
    assert signed(0.0) == "$0.00"
