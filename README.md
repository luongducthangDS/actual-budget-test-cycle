# QC test cycle: Actual Budget (open-source personal finance app)

A complete test cycle on real software: plan → test design → execution → defect reports → summary.
The system under test is [Actual Budget](https://github.com/actualbudget/actual) v26.10.0, a widely used
self-hosted budgeting app. Scope: server setup and login, availability, account creation, and money and date entry
in the transaction register.

## Results

| | |
|---|---|
| Test cases | **42 scripted** (26 pass, 16 fail) + 3 exploratory charters |
| Requirements traced | **16 / 16** ([RTM](rtm.csv)) |
| Defects found | **10**: 7 Major, 2 Minor, 1 Trivial ([defect reports](docs/defect-reports.md)) |
| Root cause identified | 3 of 10 (QC-01, QC-02, QC-04), each with a suggested fix |
| Automation | 42 / 42 cases in pytest + Playwright, ~2 min, fresh server per test |
| False positives reported | **0**: one apparent critical finding was disproved by re-testing and withdrawn |

### Most important findings

| ID | Finding |
|---|---|
| QC-05 | Typing `100+50` as an account's starting balance stores **10,050.00**, while the register computes 150.00 for the same input |
| QC-06 | `1e3` becomes **13.00** in one dialog and **1.00** in another |
| QC-07 | Date `02/30/2026` is silently saved as **02/03/2026**, so the transaction lands in the wrong month |
| QC-04 | Reloading the web app 3 times within a minute locks the browser out ("Too many requests"). Cause: the rate limiter also counts static files |
| QC-01 | On a host without IPv6 the server prints "Listening on :::5006" and **exits with code 0**. Cause traced to an ignored error in Express 5's `listen` callback |
| QC-02 | Sending a number as the password crashes setup with **HTTP 500** and leaks the server's stack trace and file paths |

## Deliverables

| File | What it is |
|---|---|
| [docs/test-plan.md](docs/test-plan.md) | Objective, scope, risk-based approach, techniques, entry/exit criteria |
| [test-cases.csv](test-cases.csv) | 45 cases: technique, test data, expected vs actual, status, defect link |
| [rtm.csv](rtm.csv) | Requirement → test cases → result → defects |
| [docs/defect-reports.md](docs/defect-reports.md) | 10 reports: steps, expected/actual, severity/priority, evidence, root cause, fix |
| [docs/test-summary-report.md](docs/test-summary-report.md) | Metrics, risks, product strengths, lessons, next cycle |
| [evidence/](evidence/) | Screenshots and logs for every defect |
| [automation/](automation/) | pytest + Playwright suite. Open defects are `xfail(strict)` tests that turn red when fixed |

## Run the automation

```bash
mkdir sut && cd sut && npm i @actual-app/sync-server@26.10.0 && cd ..
pip install pytest requests playwright && playwright install chromium
cd automation
ACTUAL_DIR=../sut pytest                 # 26 passed, 16 xfailed
ACTUAL_DIR=../sut pytest --runxfail      # shows the 16 failures behind the open defects
```

Known automation issue: on a busy 2-vCPU machine, the UI module's setup (creating the budget) timed out once in 4
full runs. The next 3 runs were green. The next improvement is to wait on the budget-loaded network call instead of
on page text.

## How I worked (and what I'd say in an interview)

- **Risk first.** In a money app the worst defect is a *wrong number nobody notices*, so amount and date entry got
  the most cases: partitions, boundaries, and error guessing (arithmetic, scientific notation, locale formats).
- **Consistency as an oracle.** The strongest defect reports compare the app with itself: the same input
  `100+50` gives 150.00 in one place and 10,050.00 in another. A developer cannot dismiss that as "by design".
- **Reproduce before reporting.** Every defect was re-run at least 3 times. An apparent "lost amount" did not
  reproduce with slower typing and was dropped as an automation artefact.
- **Disprove yourself.** "5 failed logins lock out every user" would have been a critical DoS. Before reporting it, I
  checked how the test sent its traffic. The requests all came from 127.0.0.1, so the "different users" were really
  one. With real source addresses the lockout is per user, as designed.
- **Go one level deeper when you can.** For QC-01 the cause was reproduced in 3 lines of Express code, which turns a
  vague "server won't start" into a one-line fix.

## Before filing upstream

These defects have not yet been checked against Actual's GitHub issue tracker for duplicates. That is the next step
before opening issues.
