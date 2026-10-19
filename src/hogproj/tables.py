"""Turn edited dashboard tables into model inputs, with plain-English problems. Pure.

Rules:
- Wholly blank rows are ignored (a half-typed new row).
- A row with *some* blank cells is reported, never silently dropped.
- Blank basis means 0. A missing futures contract is filled from the nearest known contract
  and flagged.
"""

import math

import pandas as pd
from pydantic import ValidationError

from hogproj.inputs import FeedPhase, Location, MarketingCut

TEXT_FIELDS = {"name", "state", "source"}


def _blank(v: object) -> bool:
    return (
        v is None
        or (isinstance(v, float) and math.isnan(v))
        or (isinstance(v, str) and not v.strip())
    )


def _rows(df: pd.DataFrame) -> list[dict]:
    """Records with all-blank rows removed."""
    return [r for r in df.to_dict("records") if not all(_blank(v) for v in r.values())]


def _err_text(e: ValidationError) -> str:
    return "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors())


def parse_phases(df: pd.DataFrame) -> tuple[list[FeedPhase], list[str]]:
    phases, problems = [], []
    for i, r in enumerate(_rows(df), start=1):
        label = r.get("name") if not _blank(r.get("name")) else f"Row {i}"
        missing = [k for k, v in r.items() if _blank(v)]
        if missing:
            problems.append(f"Feed phase '{label}' is missing: {', '.join(missing)}")
            continue
        try:
            phases.append(FeedPhase(**r))
        except ValidationError as e:
            problems.append(f"Feed phase '{label}': {_err_text(e)}")
    return phases, problems


def parse_cuts(df: pd.DataFrame) -> tuple[list[MarketingCut], list[str]]:
    cuts, problems = [], []
    for i, r in enumerate(_rows(df), start=1):
        missing = [k for k, v in r.items() if _blank(v)]
        if missing:
            problems.append(f"Marketing row {i} is missing: {', '.join(missing)}")
            continue
        try:
            r = {**r, "days_after_placement": int(r["days_after_placement"])}
            cuts.append(MarketingCut(**r))
        except (ValidationError, ValueError, TypeError) as e:
            msg = _err_text(e) if isinstance(e, ValidationError) else str(e)
            problems.append(f"Marketing row {i}: {msg}")
    if cuts:
        total = sum(c.pct_of_marketed for c in cuts)
        if abs(total - 100) > 0.01:
            problems.append(f"Marketing '% of pigs' must add up to 100 (now {total:g}).")
    return cuts, problems


def parse_locations(df: pd.DataFrame) -> tuple[list[Location], list[str]]:
    locs, problems = [], []
    for i, r in enumerate(_rows(df), start=1):
        label = r.get("name") if not _blank(r.get("name")) else f"Row {i}"
        missing = [k for k, v in r.items() if _blank(v) and k not in TEXT_FIELDS - {"name"}]
        if missing:
            problems.append(f"Location '{label}' is missing: {', '.join(missing)}")
            continue
        clean = {k: ("" if _blank(v) else v) for k, v in r.items()}
        try:
            locs.append(Location.model_validate(clean))
        except ValidationError as e:
            problems.append(f"Location '{label}': {_err_text(e)}")
    # Excel matches names exactly, but people read "Farm A" and "farm a" as the same place.
    names = [lo.name.strip().casefold() for lo in locs]
    dupes = sorted({lo.name for lo in locs if names.count(lo.name.strip().casefold()) > 1})
    if dupes:
        problems.append(f"Location names must be unique: {', '.join(dupes)}")
    if not locs and not problems:
        problems.append("Keep at least one location.")
    return locs, problems


def parse_basis(df: pd.DataFrame) -> dict[int, float]:
    """period -> basis $/cwt; blank cells count as 0."""
    out = {}
    for r in df.to_dict("records"):
        v = r.get("basis_cwt")
        out[int(r["period"])] = 0.0 if _blank(v) else float(v)  # type: ignore[arg-type]
    return out


def _months(code: str) -> int:
    y, m = (int(x) for x in code.split("-"))
    return y * 12 + m


def fill_curve(
    known: dict[str, float], needed: list[str]
) -> tuple[dict[str, float], dict[str, str]]:
    """Return a curve covering `needed`; missing contracts copy the nearest known contract.
    Second value maps each filled contract to the contract it was copied from."""
    curve = {c: known[c] for c in needed if c in known and not _blank(known[c])}
    filled: dict[str, str] = {}
    usable = {k: v for k, v in known.items() if not _blank(v)}
    if not usable:
        return curve, filled
    for c in needed:
        if c in curve:
            continue
        src = min(usable, key=lambda k: (abs(_months(k) - _months(c)), -_months(k)))
        curve[c] = usable[src]
        filled[c] = src
    return curve, filled


RATION_COLUMNS = ["corn_lb", "sbm_lb", "ddgs_lb", "other_lb", "other_usd_lb"]


def parse_ration_lbs(df: pd.DataFrame) -> tuple[list[FeedPhase], list[str]]:
    """One whole-group ration row (lb per pig marketed; other priced per lb) -> one FeedPhase."""
    rows = _rows(df)
    if len(rows) != 1:
        return [], ["The whole-group ration needs exactly one row."]
    r = rows[0]
    missing = [k for k in RATION_COLUMNS if _blank(r.get(k))]
    if missing:
        return [], [f"Whole-group ration is missing: {', '.join(missing)}"]
    lbs = {k: float(r[k]) for k in RATION_COLUMNS}
    total = lbs["corn_lb"] + lbs["sbm_lb"] + lbs["ddgs_lb"] + lbs["other_lb"]
    if total <= 0 or min(lbs.values()) < 0:
        return [], ["Whole-group ration pounds must be positive."]
    phase = FeedPhase(
        name="Whole-group ration",
        feed_lb_per_pig=total,
        corn_pct=lbs["corn_lb"] / total * 100,
        sbm_pct=lbs["sbm_lb"] / total * 100,
        ddgs_pct=lbs["ddgs_lb"] / total * 100,
        other_usd_ton=lbs["other_usd_lb"] * 2000,
    )
    return [phase], []


def ration_lbs_from_phases(phases: list[FeedPhase]) -> pd.DataFrame:
    """Collapse phases into the whole-group form (other $/lb = weighted average)."""
    corn = sum(p.feed_lb_per_pig * p.corn_pct / 100 for p in phases)
    sbm = sum(p.feed_lb_per_pig * p.sbm_pct / 100 for p in phases)
    ddgs = sum(p.feed_lb_per_pig * p.ddgs_pct / 100 for p in phases)
    other = sum(p.feed_lb_per_pig * p.other_pct / 100 for p in phases)
    other_usd = sum(p.feed_lb_per_pig * p.other_pct / 100 * p.other_usd_ton / 2000 for p in phases)
    return pd.DataFrame(
        [
            {
                "corn_lb": round(corn, 1),
                "sbm_lb": round(sbm, 1),
                "ddgs_lb": round(ddgs, 1),
                "other_lb": round(other, 1),
                "other_usd_lb": round(other_usd / other, 4) if other else 0.0,
            }
        ]
    )
