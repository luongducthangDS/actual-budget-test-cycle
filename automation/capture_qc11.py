"""Evidence for QC-11: a typo in a budget cell wipes the existing amount.
Writes ../evidence/screenshots/QC-11_before.png, QC-11_after.png and ../evidence/logs/QC-11_steps.txt.
    ACTUAL_DIR=../sut python capture_qc11.py
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent / "tests"))
from conftest import PASSWORD, Server
from test_ui_budget import add_account, assign, category_value, open_budget, row, to_budget

EV = Path(__file__).resolve().parents[1] / "evidence"

srv = Server()
log = []
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1500, "height": 950})
        pg.goto(srv.url() + "/login")
        pg.locator("input[type=password]").fill(PASSWORD)
        pg.keyboard.press("Enter")
        pg.get_by_text("Start budgeting").click(timeout=30_000)
        pg.wait_for_selector("text=To Budget", timeout=120_000)
        add_account(pg, "Checking", "1000")
        open_budget(pg)
        assign(pg, "Savings", "200")
        log.append(f"1. Typed '200' in Savings budget -> budget {category_value(pg, 'Savings', 'budget')}, "
                   f"To Budget {to_budget(pg)}")
        row(pg, "Savings").screenshot(path=EV / "screenshots/QC-11_before.png")
        assign(pg, "Savings", "abc")
        log.append(f"2. Typed 'abc' over it and pressed Enter -> budget {category_value(pg, 'Savings', 'budget')}, "
                   f"To Budget {to_budget(pg)} (no warning shown)")
        row(pg, "Savings").screenshot(path=EV / "screenshots/QC-11_after.png")
        pg.screenshot(path=EV / "screenshots/QC-11_after_full.png")
        b.close()
finally:
    srv.stop()
(EV / "logs/QC-11_steps.txt").write_text("Actual Budget v26.10.0, Chromium (Playwright)\n" + "\n".join(log) + "\n")
print("\n".join(log))
