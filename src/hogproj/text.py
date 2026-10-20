"""Small wording helpers shared by the models and pages. Pure."""


def ordinal(x: float) -> str:
    """31 -> "31st", 12 -> "12th", 22.6 -> "23rd" (rounded first)."""
    n = int(round(x))
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def day(d: object, fmt: str = "%b %d, %Y") -> str:
    """A date without a zero-padded day on any platform: "Aug 3, 2027", not "Aug 03, 2027"."""
    import pandas as pd

    t = pd.Timestamp(d if hasattr(d, "strftime") else str(d))  # type: ignore[arg-type]
    # A plain-text marker: Linux's strftime stops at a NUL byte, so "\x00" cut the date short.
    return t.strftime(fmt.replace("%d", "@@DAY@@")).replace("@@DAY@@", str(t.day))


def article(phrase: str) -> str:
    """ "a" or "an" before a number or word as it's said aloud: an 8%, an 11%, an 80%, a 7%."""
    s = phrase.lstrip()
    for word in ("under ", "over "):  # "under 1%" -> "under a 1%"
        if s.startswith(word):
            return word + article(s[len(word) :])
    digits = "".join(ch for ch in s if ch.isdigit())
    if digits:
        n = int(digits) if len(digits) <= 2 else int(digits[:3])
        an = digits.startswith("8") or n in (11, 18)
    else:
        an = s[:1].lower() in "aeiou" and not s.lower().startswith(("one", "u"))
    return f"{'an' if an else 'a'} {s}"
