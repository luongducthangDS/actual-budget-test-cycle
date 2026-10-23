"""Server: first-time setup, login, rate limiting, availability.

Tests named after test cases in test-cases.csv. Tests that document an open defect are marked
xfail(strict=True, raises=AssertionError) with the defect id: they assert the EXPECTED behaviour, so they turn red (XPASS)
the day the defect is fixed and the test must be promoted to a normal regression test.
"""
import subprocess
import time
from pathlib import Path

import pytest
import requests

from conftest import PASSWORD, Server, client


def bootstrap(s, body):
    return requests.post(s.url() + "/account/bootstrap", json=body, timeout=10)


def login(s, password, ip="127.0.0.1"):
    return client(ip).post(s.url() + "/account/login", json={"password": password}, timeout=10)


# ---------- first-time password setup ------------------------------------------------------------

def test_TC_AUTH_01_bootstrap_with_valid_password(fresh_server):
    r = bootstrap(fresh_server, {"password": PASSWORD})
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert requests.get(fresh_server.url() + "/account/needs-bootstrap").json()["data"]["bootstrapped"] is True


@pytest.mark.parametrize("body", [{"password": ""}, {}], ids=["empty", "missing"])
def test_TC_AUTH_02_03_bootstrap_rejects_empty_or_missing_password(fresh_server, body):
    r = bootstrap(fresh_server, body)
    assert r.status_code == 400
    assert r.json()["status"] == "error"   # reason: invalid-password / no-auth-method-selected
    assert requests.get(fresh_server.url() + "/account/needs-bootstrap").json()["data"]["bootstrapped"] is False


def test_TC_AUTH_04_cannot_bootstrap_twice(fresh_server):
    bootstrap(fresh_server, {"password": PASSWORD})
    r = bootstrap(fresh_server, {"password": "attacker-takes-over"})
    assert r.json()["reason"] == "already-bootstrapped"
    assert login(fresh_server, "attacker-takes-over").json()["status"] == "error"


@pytest.mark.xfail(reason="QC-02: non-string password crashes /account/bootstrap with HTTP 500", strict=True, raises=AssertionError)
@pytest.mark.parametrize("password", [12345, {"a": 1}, ["x"]], ids=["number", "object", "array"])
def test_TC_AUTH_05_bootstrap_rejects_non_string_password_with_400(fresh_server, password):
    r = bootstrap(fresh_server, {"password": password})
    assert r.status_code == 400


@pytest.mark.xfail(reason="QC-02: 500 page leaks stack trace and absolute server paths", strict=True, raises=AssertionError)
def test_TC_AUTH_06_error_response_does_not_leak_internals(fresh_server):
    r = bootstrap(fresh_server, {"password": 12345})
    assert "node_modules" not in r.text and " at " not in r.text


@pytest.mark.xfail(reason="QC-03: whitespace-only / 1-character passwords are accepted", strict=True, raises=AssertionError)
@pytest.mark.parametrize("weak", [" ", "   ", "a"], ids=["one-space", "three-spaces", "one-char"])
def test_TC_AUTH_07_weak_passwords_rejected(fresh_server, weak):
    r = bootstrap(fresh_server, {"password": weak})
    assert r.status_code == 400


# ---------- login ----------------------------------------------------------------------------------

def test_TC_AUTH_08_login_with_correct_password_returns_valid_token(server):
    r = login(server, PASSWORD, ip="127.0.0.2")
    token = r.json()["data"]["token"]
    v = client("127.0.0.2").get(server.url() + "/account/validate", headers={"x-actual-token": token})
    assert v.json()["status"] == "ok"


@pytest.mark.parametrize("pw", ["wrong", PASSWORD.upper(), PASSWORD + " "], ids=["wrong", "case-changed", "trailing-space"])
def test_TC_AUTH_09_login_with_wrong_password_rejected(server, pw):
    r = login(server, pw, ip="127.0.0.3")
    assert r.status_code == 400
    assert r.json() == {"status": "error", "reason": "invalid-password"}


def test_TC_AUTH_10_invalid_token_rejected(server):
    v = client("127.0.0.4").get(server.url() + "/account/validate", headers={"x-actual-token": "forged"})
    assert v.status_code == 403 or v.json()["status"] == "error"


def test_TC_AUTH_11_sixth_failed_login_in_15_min_is_blocked(server):
    ip = "127.0.0.5"
    codes = [login(server, "wrong", ip).status_code for _ in range(6)]
    assert codes[:5] == [400] * 5
    assert codes[5] == 429
    # the block applies even to the correct password from that client
    assert login(server, PASSWORD, ip).status_code == 429
    # another client is not affected
    assert login(server, PASSWORD, "127.0.0.6").json()["status"] == "ok"


def test_TC_AUTH_12_successful_logins_do_not_count_toward_the_limit(server):
    ip = "127.0.0.7"
    for _ in range(4):
        login(server, "wrong", ip)
    for _ in range(5):
        assert login(server, PASSWORD, ip).json()["status"] == "ok"
    assert login(server, "wrong", ip).status_code == 400   # 5th failure: rejected, but not blocked


# ---------- availability -----------------------------------------------------------------------------

def _ipv6_available() -> bool:
    p = Path("/proc/net/if_inet6")
    return p.exists() and p.read_text().strip() != ""


@pytest.mark.skipif(_ipv6_available(), reason="defect only reproduces on hosts without IPv6")
@pytest.mark.xfail(reason="QC-01: bind failure on '::' is ignored; server prints 'Listening' and exits 0", strict=True, raises=AssertionError)
def test_TC_AVAIL_01_server_does_not_exit_silently_when_default_host_cannot_be_bound():
    s = Server(hostname="::", bootstrap=False)
    try:
        code = s.proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        code = None  # still running: acceptable
    log = s.log.read_text()
    s.stop()
    silent_exit = code == 0 and "Listening on" in log
    assert not silent_exit, f"exit={code}, log tail: {log[-200:]}"


@pytest.mark.xfail(reason="QC-04: global 500 req/min limit also counts static assets; normal app use is blocked", strict=True, raises=AssertionError)
def test_TC_AVAIL_02_static_assets_do_not_exhaust_rate_limit(server):
    ip = "127.0.0.8"
    http = client(ip)
    html = http.get(server.url() + "/").text
    assets = [a.split('"')[0] for a in html.split('src="')[1:]] + [a.split('"')[0] for a in html.split('href="')[1:]]
    assets = [a for a in assets if a.startswith("/")] or ["/"]
    # ~3 app loads' worth of static requests (one browser load issues ~200 requests)
    for i in range(600):
        http.get(server.url() + assets[i % len(assets)], timeout=10)
    assert http.get(server.url() + "/").status_code == 200
