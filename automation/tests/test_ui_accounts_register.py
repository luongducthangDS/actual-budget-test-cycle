"""Web UI: account creation and the transaction register (Playwright).

One browser session per module (an app load costs ~200 requests against a 500/min limit, see QC-04).
Expected results come from the test cases in ../test-cases.csv.
"""
import re
import uuid

import pytest
from conftest import PASSWORD, Server
from playwright.sync_api import sync_playwright

pytestmark = pytest.mark.ui
XF = {"strict": True, "raises": AssertionError}


@pytest.fixture(scope="module")
def page():
    srv = Server()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page(viewport={"width": 1400, "height": 900})
        pg.goto(srv.url() + "/login")
        pg.locator("input[type=password]").fill(PASSWORD)
        pg.keyboard.press("Enter")
        pg.get_by_text("Start budgeting").click(timeout=30_000)
        pg.wait_for_selector("text=To Budget", timeout=120_000)
        pg.fresh_budget_text = pg.inner_text("body")
        yield pg
        browser.close()
    srv.stop()


def create_account(pg, name, balance):
    pg.get_by_text("Add account").first.click()
    pg.get_by_text("Create a local account").first.click()
    pg.locator("input[name=name]").fill(name)
    pg.locator("input[name=balance]").fill(balance)
    pg.locator("[role=dialog]").last.get_by_role("button", name="Create").click()
    pg.wait_for_timeout(1200)
    if pg.locator("input[name=name]").count():          # dialog still open = rejected
        error = pg.locator("[role=dialog]").last.inner_text()
        for _ in range(3):
            if pg.locator("[role=dialog]").count():
                pg.keyboard.press("Escape")
                pg.wait_for_timeout(300)
        return None, error
    body = pg.inner_text("body")
    return body.split(f"\n{name}\n", 1)[1].split("\n")[0], ""


def money(text):
    return float(text.replace(",", ""))


def add_deposit(pg, account_name, date, amount):
    """Enter one transaction with keyboard only, the way a power user does. Returns (date, amount) as saved."""
    pg.get_by_text(account_name, exact=True).first.click()
    pg.wait_for_timeout(800)
    payee = f"P-{uuid.uuid4().hex[:6]}"
    pg.get_by_role("button", name="Add New").click()
    k = pg.keyboard
    k.press("Control+A"); k.type(date, delay=50); pg.wait_for_timeout(300)
    k.press("Tab"); pg.wait_for_timeout(300)
    k.type(payee, delay=30); pg.wait_for_timeout(300); k.press("Tab"); pg.wait_for_timeout(300)
    for _ in range(3):
        k.press("Tab"); pg.wait_for_timeout(200)        # notes -> category -> payment -> deposit
    k.type(amount, delay=50); pg.wait_for_timeout(300)
    pg.get_by_role("button", name="Add", exact=True).click()
    pg.wait_for_timeout(1000)
    for _ in range(2):
        k.press("Escape"); pg.wait_for_timeout(200)
    row = pg.inner_text("body").split(payee, 1)
    saved_date = row[0].rstrip().split("\n")[-1]
    saved_amount = re.findall(r"-?[\d,]+\.\d{2}", row[1])[0]
    return saved_date, saved_amount


@pytest.fixture(scope="module")
def register(page):
    create_account(page, "Register", "1000")
    return page


# ---------- account creation ----------------------------------------------------------------------

@pytest.mark.parametrize("balance, shown", [
    ("1000", "1,000.00"), ("1,234.56", "1,234.56"), ("-500", "-500.00"), ("0.005", "0.01"),
    ("  50  ", "50.00"), ("999999999999", "999,999,999,999.00"), ("1.234,56", "1,234.56"),
], ids=["integer", "grouped", "negative", "half-cent-rounds-up", "padded", "12-digits", "european-format"])
def test_TC_ACC_01_starting_balance_accepted(page, balance, shown):
    name = f"Acc {uuid.uuid4().hex[:5]}"
    got, err = create_account(page, name, balance)
    assert got == shown, err


@pytest.mark.parametrize("name, balance, message", [
    ("", "100", "Name cannot be blank"),
    ("Dup", "100", "already exists"),
    ("Letters", "abc", "Balance must be a number"),
], ids=["blank-name", "duplicate-name", "non-numeric-balance"])
def test_TC_ACC_02_invalid_input_rejected_with_message(page, name, balance, message):
    if name == "Dup":
        create_account(page, "Dup", "1")
    got, err = create_account(page, name, balance)
    assert got is None
    assert message in err


@pytest.mark.xfail(reason="QC-05: '100+50' becomes 10,050.00 in the account dialog (register gives 150.00)", **XF)
def test_TC_ACC_03_arithmetic_balance_evaluated_or_rejected(page):
    got, _err = create_account(page, f"Expr {uuid.uuid4().hex[:5]}", "100+50")
    assert got in (None, "150.00"), f"silently stored as {got}"


@pytest.mark.xfail(reason="QC-06: '1e3' becomes 13.00 in the account dialog", **XF)
def test_TC_ACC_04_scientific_notation_evaluated_or_rejected(page):
    got, _err = create_account(page, f"Sci {uuid.uuid4().hex[:5]}", "1e3")
    assert got in (None, "1,000.00"), f"silently stored as {got}"


# ---------- transaction register -------------------------------------------------------------------

@pytest.mark.parametrize("amount, shown", [
    ("50", "50.00"), ("12.345", "12.35"), ("1,000.50", "1,000.50"), ("100+50", "150.00"),
], ids=["integer", "3-decimals-rounds", "grouped", "arithmetic"])
def test_TC_TX_01_deposit_amount_saved(register, amount, shown):
    _, saved = add_deposit(register, "Register", "10/20/2026", amount)
    assert saved == shown


def test_TC_TX_02_running_balance_matches_sum_of_transactions(register):
    before = money(register.inner_text("body").split("\nRegister\n", 1)[1].split("\n")[0])
    add_deposit(register, "Register", "10/20/2026", "25.75")
    after = money(register.inner_text("body").split("\nRegister\n", 1)[1].split("\n")[0])
    assert round(after - before, 2) == 25.75


@pytest.mark.xfail(reason="QC-06: '1e3' is saved as 1.00 in the register", **XF)
def test_TC_TX_03_scientific_notation_amount(register):
    _, saved = add_deposit(register, "Register", "10/20/2026", "1e3")
    assert saved in ("1,000.00",)


@pytest.mark.xfail(reason="QC-09: non-numeric amount silently saves a 0.00 transaction", **XF)
def test_TC_TX_04_non_numeric_amount_not_saved_as_zero(register):
    _, saved = add_deposit(register, "Register", "10/20/2026", "abc")
    assert saved != "0.00"


@pytest.mark.xfail(reason="QC-07: 02/30/2026 is silently saved as 02/03/2026", **XF)
def test_TC_TX_05_impossible_calendar_date_not_silently_changed(register):
    saved_date, _ = add_deposit(register, "Register", "02/30/2026", "10")
    assert saved_date not in ("02/03/2026",)


@pytest.mark.xfail(reason="QC-08: 13/45/2026 is silently replaced by today's date", **XF)
def test_TC_TX_06_garbage_date_not_replaced_by_today(register):
    import datetime
    today = datetime.date.today().strftime("%m/%d/%Y")
    saved_date, _ = add_deposit(register, "Register", "13/45/2026", "10")
    assert saved_date != today


# ---------- display ---------------------------------------------------------------------------------

@pytest.mark.xfail(reason="QC-10: fresh budget shows '-0.00' (negative zero)", **XF)
def test_TC_UI_01_no_negative_zero_on_fresh_budget(page):
    assert "-0.00" not in page.fresh_budget_text
