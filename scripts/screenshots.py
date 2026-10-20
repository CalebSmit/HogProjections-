"""Screenshot every page at desktop and phone width for the visual review in each phase gate.

    uv run --with playwright python -I scripts/screenshots.py [page ...]

Starts its own Streamlit server on a spare port, drives the installed Edge (or Chrome) with
Playwright, writes PNGs to outputs/shots/ and stops the server. Streamlit scrolls inside the
page, so the viewport is made tall instead of relying on full-page capture.
"""

import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "shots"
PAGES = {
    "overview": "",
    "guide": "Guide",
    "herd": "Herd_flow",
    "costs": "Costs_and_returns",
    "w2f": "Wean_to_finish",
    "history": "Crush_history",
    "hedging": "Hedging",
    "scenarios": "Scenarios",
    "risk": "Risk",
    "market": "Market_prices",
    "supply": "Hog_supply",
}
WIDTHS = {"desktop": (1440, 2800), "phone": (390, 5200)}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main(only: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    port = free_port()
    server = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py", "--server.port", str(port),
         "--server.headless", "true"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )  # fmt: skip
    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(channel="msedge", headless=True)
            except Exception:
                browser = p.chromium.launch(channel="chrome", headless=True)
            for label, (w, h) in WIDTHS.items():
                page = browser.new_page(viewport={"width": w, "height": h})
                for name, path in PAGES.items():
                    if only and name not in only:
                        continue
                    for _ in range(60):
                        try:
                            page.goto(f"http://localhost:{port}/{path}")
                            break
                        except Exception:
                            time.sleep(1)
                    page.wait_for_selector("h1", timeout=120_000)
                    # Wait for the script to finish (no running indicator) and charts to draw.
                    for _ in range(90):
                        if page.locator('[data-testid="stStatusWidget"]').count() == 0:
                            break
                        time.sleep(1)
                    time.sleep(5)
                    errors = page.locator('[data-testid="stException"]').count()
                    page.screenshot(path=OUT / f"{label}_{name}.png", full_page=True)
                    print(f"{label:7} {name:10} {'EXCEPTION' if errors else 'ok'}")
                page.close()
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=30)


if __name__ == "__main__":
    main(sys.argv[1:])
