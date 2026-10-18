"""Plotly figure builders for the dashboard. Pure: DataFrames in, figures out.

Palette (dataviz reference palette): single-series blue, diverging blue (profit) to red (loss)
around a neutral gray, recessive gray grid. Text stays in ink colors, never series colors.
"""

import pandas as pd
import plotly.graph_objects as go

from hogproj.basis import PERIODS, period_label

BLUE = "#2a78d6"
BLUE_DARK = "#184f95"
BLUE_LIGHT = "#b7d3f6"
RED = "#e34948"
NEUTRAL = "#f0efec"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e6e5e0"
SURFACE = "#fcfcfb"


def _usd(v: float, dec: int = 2) -> str:
    v = round(v, dec) + 0.0  # + 0.0 turns -0.0 into 0.0
    return f"-${abs(v):,.{dec}f}" if v < 0 else f"${v:,.{dec}f}"


def _layout(fig: go.Figure, title: str, height: int = 380) -> go.Figure:
    fig.update_layout(
        title={"text": title, "font": {"size": 16, "color": INK}, "x": 0, "xanchor": "left"},
        height=height,
        margin={"l": 8, "r": 24, "t": 48, "b": 8},
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font={"color": INK_2, "size": 13},
        hoverlabel={"bgcolor": "white", "font_color": INK},
        showlegend=False,
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID)
    return fig


def cost_breakdown(costs: pd.DataFrame) -> go.Figure:
    """Horizontal bars: $/head sold per cost line, largest at top."""
    df = costs.loc[costs["total_usd"].abs() > 0.005].sort_values(by="usd_per_head_sold")
    fig = go.Figure(
        go.Bar(
            x=df["usd_per_head_sold"],
            y=df["line"],
            orientation="h",
            marker={"color": BLUE, "cornerradius": 4},
            text=[f"${v:,.2f}" for v in df["usd_per_head_sold"]],
            textposition="outside",
            textfont={"color": INK_2},
            cliponaxis=False,
            customdata=df["pct_of_total"],
            hovertemplate=(
                "%{y}<br>$%{x:,.2f}/head sold<br>%{customdata:.1f}% of cost<extra></extra>"
            ),
        )
    )
    fig.update_xaxes(tickprefix="$", showgrid=True)
    fig.update_yaxes(showgrid=False)
    return _layout(fig, "Cost per head sold", height=max(300, 34 * len(df) + 80))


def net_by_location(df: pd.DataFrame, selected: str) -> go.Figure:
    """Net $/head sold by location; profit blue, loss red; selected location outlined."""
    df = df.sort_values("net_usd_per_head_sold")
    colors = [BLUE if v >= 0 else RED for v in df["net_usd_per_head_sold"]]
    widths = [2.5 if n == selected else 0 for n in df["location"]]
    fig = go.Figure(
        go.Bar(
            x=df["net_usd_per_head_sold"],
            y=df["location"],
            orientation="h",
            marker={"color": colors, "line": {"color": INK, "width": widths}, "cornerradius": 4},
            text=[_usd(v) for v in df["net_usd_per_head_sold"]],
            textposition="outside",
            textfont={"color": INK_2},
            cliponaxis=False,
            hovertemplate="%{y}<br>Net $%{x:,.2f}/head sold<extra></extra>",
        )
    )
    fig.update_xaxes(tickprefix="$", zerolinecolor=INK_2, zerolinewidth=1)
    return _layout(fig, "Net profit per head sold, by location", max(300, 34 * len(df) + 80))


def basis_bars(df: pd.DataFrame, value_col: str, title: str, unit: str, selected: str) -> go.Figure:
    """One basis per location (e.g. corn ¢/bu under futures); selected location darker.
    Values sit inside the bars so negative bars never run into the location names."""
    df = df.sort_values(by=value_col)
    scale = 100 if unit == "¢/bu" else 1
    colors = [BLUE_DARK if n == selected else BLUE for n in df["location"]]
    fig = go.Figure(
        go.Bar(
            x=df[value_col] * scale,
            y=df["location"],
            orientation="h",
            marker={"color": colors, "cornerradius": 4},
            text=[f"{v * scale:+,.0f}" for v in df[value_col]],
            textposition="inside",
            insidetextanchor="middle",
            textfont={"color": "white"},
            hovertemplate="%{y}<br>%{x:+,.1f} " + unit + "<extra></extra>",
        )
    )
    fig.update_xaxes(ticksuffix=f" {unit}", zerolinecolor=INK_2, zerolinewidth=1)
    return _layout(fig, title, max(280, 30 * len(df) + 80))


def hog_basis_seasonal(by_year_period: pd.DataFrame, years: list[int]) -> go.Figure:
    """Each chosen year as a thin gray line, the average of those years as the blue line."""
    labels = [period_label(p) for p in PERIODS]
    fig = go.Figure()
    t = by_year_period.loc[by_year_period.index.isin(years)]
    for year, row in t.iterrows():
        fig.add_trace(
            go.Scatter(
                x=labels,
                y=[row.get(p) for p in PERIODS],
                mode="lines",
                line={"color": "#c9c8c1", "width": 1},
                name=str(year),
                hovertemplate=f"{year}" + " · %{x}<br>%{y:+.2f} $/cwt<extra></extra>",
            )
        )
    avg = t.mean(axis=0)
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=[avg.get(p) for p in PERIODS],
            mode="lines+markers",
            line={"color": BLUE, "width": 2.5},
            marker={"size": 8, "line": {"color": SURFACE, "width": 2}},
            name="Average",
            hovertemplate="Average · %{x}<br>%{y:+.2f} $/cwt<extra></extra>",
        )
    )
    fig.update_yaxes(ticksuffix=" $/cwt", zerolinecolor=INK_2, zerolinewidth=1)
    fig.update_xaxes(tickangle=-45)
    fig = _layout(fig, "Hog basis by half-month: CME Index − nearby futures", 420)
    fig.update_layout(hovermode="closest")
    return fig


def sensitivity_heatmap(grid: pd.DataFrame) -> go.Figure:
    """Net $/head sold: rows = corn futures change, cols = hog futures change. 0 is gray."""
    z = grid.to_numpy()
    lim = float(max(abs(z.min()), abs(z.max()), 1.0))
    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=[f"{c} $/cwt" for c in grid.columns],
            y=[f"{r} $/bu" for r in grid.index],
            zmin=-lim,
            zmax=lim,
            colorscale=[[0, RED], [0.5, NEUTRAL], [1, BLUE]],
            text=[[_usd(float(v), 0) for v in row] for row in z],
            texttemplate="%{text}",
            textfont={"color": INK},
            xgap=2,
            ygap=2,
            colorbar={"title": "Net $/hd", "tickprefix": "$"},
            hovertemplate="Corn %{y}, hogs %{x}<br>Net %{text}/head sold<extra></extra>",
        )
    )
    fig.update_xaxes(title="Change in lean hog futures", showgrid=False)
    fig.update_yaxes(title="Change in corn futures", showgrid=False, autorange="reversed")
    return _layout(fig, "What if prices move? Net $/head sold", 420)


def price_history(df: pd.DataFrame, x: str, y: str, title: str, unit: str) -> go.Figure:
    fig = go.Figure(
        go.Scatter(
            x=df[x],
            y=df[y],
            mode="lines",
            line={"color": BLUE, "width": 2},
            hovertemplate="%{x|%b %d, %Y}<br>%{y:,.2f} " + unit + "<extra></extra>",
        )
    )
    fig.update_yaxes(tickprefix="$")
    fig = _layout(fig, title, 340)
    fig.update_layout(hovermode="x unified")
    return fig


ORANGE = "#eb6834"


def cash_flow_chart(cf: pd.DataFrame) -> go.Figure:
    """Cash out vs cash in by month (two series, legend + direct identity by color)."""
    months = pd.to_datetime(cf["month"]).dt.strftime("%b %Y")
    fig = go.Figure(
        [
            go.Bar(
                x=months,
                y=cf["cash_out_usd"],
                name="Cash out",
                marker={"color": ORANGE, "cornerradius": 4},
                hovertemplate="%{x}<br>Cash out $%{y:,.0f}<extra></extra>",
            ),
            go.Bar(
                x=months,
                y=cf["cash_in_usd"],
                name="Cash in (hog sales)",
                marker={"color": BLUE, "cornerradius": 4},
                hovertemplate="%{x}<br>Cash in $%{y:,.0f}<extra></extra>",
            ),
        ]
    )
    fig.update_yaxes(tickprefix="$")
    fig = _layout(fig, "Cash out and cash in by month", 360)
    fig.update_layout(
        showlegend=True,
        barmode="group",
        bargap=0.3,
        bargroupgap=0.08,
        legend={"orientation": "h", "y": 1.08, "x": 1, "xanchor": "right"},
    )
    return fig
