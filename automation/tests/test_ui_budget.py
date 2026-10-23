"""Cycle 2: the Budget module (envelope budgeting rules).

Rules under test (Actual's documented envelope model):
  R-17 To Budget = money in on-budget accounts not yet assigned to a category
  R-18 Assigning to a category moves money out of To Budget, one for one
  R-19 Spending in a category lowers that category's balance, not To Budget
  R-20 A positive category balance rolls over to the next month
  R-21 Overspending is taken out of NEXT month's To Budget
  R-22 Off-budget accounts never change To Budget
  R-23 Budget amounts are parsed like every other money field
Scenario dates are in the current month (the budget page opens on it); the next month is visible beside it.
"""
import datetime

import pytest
from conftest import PASSWORD, Server
from playwright.sync_api import sync_playwright

pytestmark = pytest.mark.ui
XF = {"strict": True, "raises": AssertionError}

TODAY = datetime.date.today()
THIS = TODAY.strftime("%Y%m")
NEXT = (TODAY.replace(day=1) + datetime.timedelta(days=32)).strftime("%Y%m")
DATE_IN_MONTH = TODAY.replace(day=min(TODAY.day, 15)).strftime("%m/%d/%Y")


def money(s: str) -> float:
    return float(s.replace(",", "").replace("−", "-"))


@pytest.fixture(scope="module")
def app():
    srv = Server()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page(viewport={"width": 1500, "height": 950})
        pg.goto(srv.url() + "/login")
        pg.locator("input[type=password]").fill(PASSWORD)
        pg.keyboard.press("Enter")
        pg.get_by_text("Start budgeting").click(timeout=30_000)
        pg.wait_for_selector("text=To Budget", timeout=120_000)
        add_account(pg, "Checking", "1000")
        yield pg
        browser.close()
    srv.stop()


def add_account(pg, name, balance, off_budget=False):
    pg.get_by_text("Add account").first.click()
    pg.get_by_text("Create a local account").first.click()
    pg.locator("input[name=name]").fill(name)
    if off_budget:
        pg.locator("input[name=offbudget]").check()
    pg.locator("input[name=balance]").fill(balance)
    pg.locator("[role=dialog]").last.get_by_role("button", name="Create").click()
    pg.wait_for_timeout(1500)


def open_budget(pg):
    pg.get_by_text("Budget", exact=True).first.click()
    pg.wait_for_selector(f"[data-testid='budget{THIS}!available-funds']")
    pg.wait_for_timeout(800)


def to_budget(pg, month=THIS) -> float:
    """The 'To Budget' amounts appear in the same order as the visible months."""
    months = pg.evaluate("""() => [...document.querySelectorAll('[data-testid$="!available-funds"]')]
                                    .map(e => e.dataset.testid.slice(6, 12))""")
    values = pg.evaluate("""() => [...document.querySelectorAll('*')]
        .filter(e => e.childElementCount == 0 && /^(To Budget|Overbudgeted):$/.test(e.textContent.trim()))
        .map(e => e.parentElement.innerText.split('\\n').pop())""")
    return money(values[months.index(month)])


def summary(pg, key, month=THIS) -> float:
    return money(pg.get_by_test_id(f"budget{month}!{key}").inner_text())


def row(pg, category):
    return pg.get_by_test_id("row").filter(
        has=pg.get_by_test_id("category-name").get_by_text(category, exact=True)).first


def select_month(pg, month):
    """The category table shows one month; pick it in the month bar (e.g. 'Nov')."""
    label = datetime.date(int(month[:4]), int(month[4:]), 1).strftime("%b")
    pg.get_by_text(label, exact=True).first.click()
    pg.wait_for_timeout(800)


def category_value(pg, category, column, month=THIS) -> float:
    """column: 'budget' | 'spent' | 'balance' for the given month."""
    if month != THIS:
        select_month(pg, month)
    value = money(row(pg, category).get_by_test_id(column).inner_text())
    if month != THIS:
        select_month(pg, THIS)
    return value


def assign(pg, category, amount):
    row(pg, category).get_by_test_id("budget").click()
    pg.wait_for_timeout(300)
    pg.keyboard.press("Control+A")
    pg.keyboard.type(amount, delay=40)
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(800)


def spend(pg, account, category, amount, deposit=False):
    pg.get_by_text(account, exact=True).first.click()
    pg.get_by_role("button", name="Add New").click()
    k = pg.keyboard
    k.press("Control+A"); k.type(DATE_IN_MONTH, delay=40); k.press("Tab"); pg.wait_for_timeout(300)
    k.type("Shop", delay=40); k.press("Tab"); pg.wait_for_timeout(300)
    k.press("Tab"); pg.wait_for_timeout(300)                    # notes -> category
    k.type(category, delay=50); pg.wait_for_timeout(500); k.press("Enter"); pg.wait_for_timeout(300)
    k.press("Tab"); pg.wait_for_timeout(300)                    # category -> payment
    if deposit:
        k.press("Tab"); pg.wait_for_timeout(300)                # payment -> deposit
    k.type(amount, delay=40); pg.wait_for_timeout(300)
    pg.get_by_role("button", name="Add", exact=True).click()
    pg.wait_for_timeout(1000)
    for _ in range(2):
        k.press("Escape")
    open_budget(pg)


# ---------- R-17 / R-18 assigning money ------------------------------------------------------------

def test_TC_BUD_01_to_budget_equals_unassigned_on_budget_money(app):
    open_budget(app)
    assert to_budget(app) == 1000.0


def test_TC_BUD_02_assigning_moves_money_out_of_to_budget(app):
    assign(app, "Food", "300")
    assert category_value(app, "Food", "budget") == 300.0
    assert category_value(app, "Food", "balance") == 300.0
    assert to_budget(app) == 700.0


def test_TC_BUD_03_arithmetic_in_budget_cell_is_evaluated(app):
    assign(app, "General", "100+50")
    assert category_value(app, "General", "budget") == 150.0
    assert to_budget(app) == 550.0


@pytest.mark.xfail(reason="QC-06 (also in Budget): '1e3' is stored as 13.00", **XF)
def test_TC_BUD_04_scientific_notation_in_budget_cell(app):
    assign(app, "Bills", "1e3")
    got = category_value(app, "Bills", "budget")
    assign(app, "Bills", "0")                     # clean up so later steps start from known state
    assert got in (0.0, 1000.0), f"silently stored as {got}"


@pytest.mark.xfail(reason="QC-11: a typo in a budget cell wipes the existing amount to 0.00 without warning", **XF)
def test_TC_BUD_05_typo_does_not_wipe_existing_budget(app):
    assign(app, "Savings", "200")
    assign(app, "Savings", "abc")
    got = category_value(app, "Savings", "budget")
    assign(app, "Savings", "0")
    assert got == 200.0, f"budget changed to {got} after typing 'abc'"


# ---------- R-19 spending --------------------------------------------------------------------------

def test_TC_BUD_06_spending_lowers_category_balance_not_to_budget(app):
    before = to_budget(app)
    spend(app, "Checking", "Food", "120")
    assert category_value(app, "Food", "spent") == -120.0
    assert category_value(app, "Food", "balance") == 180.0
    assert to_budget(app) == before


def test_TC_BUD_07_overspent_category_goes_negative(app):
    spend(app, "Checking", "General", "400")            # budget 150 -> balance -250
    assert category_value(app, "General", "balance") == -250.0


# ---------- R-20 / R-21 month rollover -------------------------------------------------------------

def test_TC_BUD_08_positive_balance_rolls_over(app):
    assert category_value(app, "Food", "balance", NEXT) == 180.0


def test_TC_BUD_09_overspending_reduces_next_months_to_budget(app):
    assert summary(app, "last-month-overspent", NEXT) == -250.0
    assert to_budget(app, NEXT) == to_budget(app) - 250.0
    assert category_value(app, "General", "balance", NEXT) == 0.0   # the category itself starts clean


# ---------- R-22 off-budget, income ------------------------------------------------------------------

def test_TC_BUD_10_off_budget_account_does_not_change_to_budget(app):
    before = to_budget(app)
    add_account(app, "Brokerage", "5000", off_budget=True)
    open_budget(app)
    assert to_budget(app) == before


def test_TC_BUD_11_income_increases_to_budget(app):
    before = to_budget(app)
    spend(app, "Checking", "Income", "500", deposit=True)
    assert to_budget(app) == before + 500.0


def test_TC_BUD_12_money_is_conserved(app):
    """Sum of category balances + To Budget = money in on-budget accounts."""
    balances = sum(category_value(app, c, "balance") for c in
                   ("Food", "General", "Bills", "Bills (Flexible)", "Savings"))
    on_budget = money(app.get_by_test_id("sidebar-on-budget-balance").inner_text().split("\n")[-1])
    assert round(balances + to_budget(app), 2) == on_budget
