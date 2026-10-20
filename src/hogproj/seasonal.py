"""Every number against its own history: this year, last year and the range of earlier years at
the same time of year, with a plain verdict ("below its 2021–25 range for mid-October").
Pure: a dated series in, tables and words out.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

SKIP_YEARS = (2020,)  # COVID plant closures distort hog prices, slaughter and weights


def by_week(s: pd.Series, how: str = "mean") -> pd.DataFrame:
    """Dated values -> one row per week (ending Friday): week_ending, year, wk (ISO week), value.
    Week 53 folds into 52 so every year lines up."""
    s = pd.Series(s.to_numpy(dtype=float), index=pd.to_datetime(s.index)).dropna().sort_index()
    r = s.resample("W-FRI")
    w = (r.sum(min_count=1) if how == "sum" else r.mean()).dropna()
    through = pd.Series(s.index, index=s.index).resample("W-FRI").max().reindex(w.index)
    iso = w.index.isocalendar()
    return pd.DataFrame({"week_ending": w.index, "through": through.to_numpy(),
                         "year": iso["year"].to_numpy(),
                         "wk": np.minimum(iso["week"].to_numpy(), 52),
                         "value": w.to_numpy()}).reset_index(drop=True)  # fmt: skip


def band(weeks: pd.DataFrame, this_year: int, years: int = 5) -> pd.DataFrame:
    """Min, max and average by week of year over the `years` years before `this_year` (2020
    left out), and which years they cover."""
    prior = [y for y in range(this_year - years, this_year) if y not in SKIP_YEARS]
    x = weeks[weeks["year"].isin(prior)]
    g = x.groupby("wk")["value"]
    out = pd.DataFrame({"lo": g.min(), "hi": g.max(), "avg": g.mean(), "n": g.count()})
    out.attrs["years"] = sorted(int(y) for y in x["year"].unique())
    return out


@dataclass
class Verdict:
    value: float
    week_ending: pd.Timestamp  # last day with data in the latest week
    where: str  # "above", "below" or "inside"
    lo: float
    hi: float
    avg: float
    years: list[int]
    percentile: float  # 0-100: where this week ranks among the same week in every year shown
    extreme: str  # "", "highest" or "lowest" for the week across all years in the data
    n_years: int  # years compared, this one included (2020 left out)

    @property
    def span(self) -> str:
        return f"{self.years[0]}–{str(self.years[-1])[2:]}" if self.years else ""

    def sentence(self, its: str = "its") -> str:
        """'below its 2021–25 range for mid-October, the lowest for the week in 6 years'."""
        text = f"{self.where} {its} {self.span} range for {_when(self.week_ending)}"
        if self.extreme:
            text += f", the {self.extreme} for the week in {self.n_years} years"
        return text


def _when(day: pd.Timestamp) -> str:
    part = "early" if day.day <= 10 else "mid" if day.day <= 20 else "late"
    return f"{part}-{day:%B}"


def verdict(weeks: pd.DataFrame, years: int = 5) -> Verdict | None:
    """Where the latest week sits against the same week in earlier years."""
    if weeks.empty:
        return None
    last = weeks.iloc[-1]
    this_year, wk = int(last["year"]), int(last["wk"])
    b = band(weeks, this_year, years)
    if wk not in b.index or b.loc[wk, "n"] < 2:
        return None
    lo, hi, avg = (float(b.loc[wk, c]) for c in ("lo", "hi", "avg"))
    v = float(last["value"])
    where = "above" if v > hi else "below" if v < lo else "inside"
    same = weeks[(weeks["wk"] == wk) & ~weeks["year"].isin(SKIP_YEARS)]
    others = same[same["year"] != this_year]["value"].to_numpy(dtype=float)
    pct = float((others < v).mean() * 100) if len(others) else 50.0
    extreme = ("highest" if len(others) and v > others.max()
               else "lowest" if len(others) and v < others.min() else "")  # fmt: skip
    return Verdict(v, pd.Timestamp(last["through"]), where, lo, hi, avg, b.attrs["years"],
                   pct, extreme, int(same["year"].nunique()))  # fmt: skip
