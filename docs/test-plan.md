# Test plan: Actual Budget v26.10.0 (server setup, accounts, transaction register)

## 1. Objective

Find the defects that would cause a self-hosting user to **lose access** to their budget or **record wrong money
data without noticing**, and report them so a developer can reproduce each one in under 5 minutes.

## 2. System under test

[Actual Budget](https://github.com/actualbudget/actual) is an open-source, local-first personal finance app.
Version tested: `@actual-app/sync-server` 26.10.0, with the bundled web client 26.10.0, installed from npm.

## 3. Scope

| In scope | Out of scope (why) |
|---|---|
| First-run password setup and login (API and UI) | Bank sync: needs real bank credentials |
| Server availability: start-up, rate limiting | OpenID / multi-user: needs an identity provider |
| Creating local accounts: name, starting balance | Budget templates, schedules, rules: next cycle |
| Entering transactions in the register: amount and date | Mobile layout: next cycle |
| Display of amounts | Import (QIF/OFX/CSV): next cycle |

## 4. Approach

- **Risk-based.** Money values and dates get the most cases, because a wrong value there goes unnoticed and
  corrupts every report built on it.
- **Test design techniques:**
  - Equivalence partitioning: valid, invalid and wrong-type inputs.
  - Boundary values: password length 0/1, 5 vs 6 failed logins, rounding at half a cent, 12-digit amounts,
    day 30 in February.
  - State-based: bootstrapped vs not; locked vs not.
  - Error guessing: arithmetic, scientific notation, locale formats.
- **Exploratory testing.** Three time-boxed charters (ET-01..03), with notes turned into scripted cases.
- **Automation.** API checks use pytest + requests; UI checks use pytest + Playwright. Every test starts its own
  server with an empty data directory, so tests are independent and repeatable. A test for an open defect asserts
  the *expected* behaviour and is marked `xfail(strict)` with the defect id, so it turns red the day the defect is
  fixed.

## 5. Environment

Linux container (no IPv6) · Node 22.22 · Chromium (Playwright) · Python 3.13, pytest 8.

## 6. Entry and exit criteria

| Entry | Exit |
|---|---|
| SUT installs and starts; test data dir is empty | Every in-scope requirement has ≥ 1 executed case (RTM) |
| | Every failed case has a reproducible defect report with evidence |
| | No open Critical defect; Major defects reported with priority |

## 7. Risks

| Risk | Mitigation |
|---|---|
| Rate limiting blocks the test run itself | One browser session per module; API clients bind distinct source IPs |
| Flaky UI timing produces false failures | Typing with delays; every defect re-run ≥ 3 times before reporting |
| Treating designed behaviour as a defect | Compare with the app's own behaviour elsewhere (e.g. the register evaluates `100+50`) and with its own validation messages |

## 8. Deliverables

`test-cases.csv` · `rtm.csv` · `docs/defect-reports.md` · `docs/test-summary-report.md` · `automation/` · `evidence/`
