from hogproj.charts import _usd, sensitivity_heatmap


def test_usd_format():
    assert _usd(-15.2, 0) == "\u2212$15"
    assert _usd(-0.2, 0) == "$0"
    assert _usd(1234.5) == "$1,234.50"


def test_heatmap_builds():
    import pandas as pd

    grid = pd.DataFrame({"-5": [-3.0, 1.0], "+5": [2.0, 9.0]}, index=["-0.25", "+0.25"])
    fig = sensitivity_heatmap(grid)
    assert fig.data[0].text[0][0] == "\u2212$3"  # type: ignore[index]
