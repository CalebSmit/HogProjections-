"""Small wording helpers shared by the models and pages. Pure."""


def ordinal(x: float) -> str:
    """31 -> "31st", 12 -> "12th", 22.6 -> "23rd" (rounded first)."""
    n = int(round(x))
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"
