# Defect reports: Actual Budget v26.10.0

**Environment:** `@actual-app/sync-server` 26.10.0 (app and web 26.10.0) · Node 22.22 · Linux container, no IPv6 ·
Chromium (Playwright) · fresh data directory per test.

**Severity:** Critical = data loss or security breach · Major = wrong data or a feature unusable, workaround hard ·
Minor = workaround easy or low impact · Trivial = cosmetic.
**Priority:** P1 = fix this release · P2 = next release · P3 = backlog.

| ID | Title | Severity | Priority | Area |
|---|---|---|---|---|
| QC-05 | Starting balance `100+50` is saved as 10,050.00 | Major | P1 | Accounts |
| QC-06 | `1e3` is saved as 13.00 (account dialog, budget cell) and 1.00 (register) | Major | P1 | Accounts, Register, Budget |
| QC-07 | Date `02/30/2026` is saved as `02/03/2026` without warning | Major | P1 | Register |
| QC-08 | Invalid date `13/45/2026` is replaced by today's date without warning | Major | P2 | Register |
| QC-04 | Reloading the app 3 times within a minute locks the browser out | Major | P2 | Server / availability |
| QC-01 | Server prints "Listening" and exits 0 when it cannot bind | Major | P2 | Server / deployment |
| QC-02 | Non-string password crashes `/account/bootstrap` (HTTP 500, stack trace) | Major | P2 | Server / security |
| QC-11 | A typo in a budget cell wipes the existing amount to 0.00 | Minor | P2 | Budget (cycle 2) |
| QC-09 | Non-numeric amount saves a 0.00 transaction | Minor | P3 | Register |
| QC-03 | A single space is accepted as the server password | Minor | P3 | Server / security |
| QC-10 | Fresh budget shows `-0.00` | Trivial | P3 | Budget |

---

## QC-05: Starting balance `100+50` is saved as 10,050.00

- **Severity / priority:** Major / P1. Wrong money value stored silently, inconsistent with the register.
- **Steps:**
  1. Sidebar → *Add account* → *Create a local account*.
  2. Name `Expr`, Balance `100+50`.
  3. Click *Create*.
- **Expected:** balance 150.00 (the register evaluates `100+50` as 150.00, see TC-TX-01d) or a validation error.
- **Actual:** the account is created with **10,050.00**. The `+` is stripped and the digits are concatenated. No warning.
- **Evidence:** `evidence/screenshots/QC-05_QC-06_account_balances.png`, test `TC-ACC-03`.
- **Note:** The same input gives two different results in two places in the same app.

## QC-06: `1e3` is saved as 13.00 (account dialog) and as 1.00 (register)

- **Severity / priority:** Major / P1.
- **Steps:**
  1. Create an account with Balance `1e3`.
  2. In any account, *Add New* a deposit of `1e3`.
- **Expected:** 1,000.00 everywhere, or "must be a number" (the dialog already rejects `abc`).
- **Actual:** the account dialog stores **13.00**, the register stores **1.00**. Neither shows a warning.
- **Evidence:** `QC-05_QC-06_account_balances.png`, `QC-06_QC-07_QC-08_QC-09_register.png`; tests `TC-ACC-04`, `TC-TX-03`.
- **Cycle 2 update:** the budget cell has the same bug: `1e3` is budgeted as **13.00** (`TC-BUD-04`). Three money fields, two different wrong results.

## QC-07: Date `02/30/2026` is saved as `02/03/2026`

- **Severity / priority:** Major / P1. The transaction lands in the wrong month, so the monthly budget is wrong too.
- **Steps:**
  1. Account register → *Add New*.
  2. Type date `02/30/2026`, payee, deposit `10`.
  3. Click *Add*.
- **Expected:** the date is rejected, or corrected visibly (for example to 02/28) so the user can see it.
- **Actual:** saved as **02/03/2026**, a date the user never typed, with no message.
- **Evidence:** `QC-06_QC-07_QC-08_QC-09_register.png`; test `TC-TX-05`. Reproduced in every run (4/4).

## QC-08: Invalid date `13/45/2026` is replaced by today's date

- **Severity / priority:** Major / P2.
- **Steps:** same as QC-07 with date `13/45/2026`.
- **Expected:** a validation message.
- **Actual:** saved with **today's date** (10/23/2026 on the day of testing), silently.
- **Evidence:** test `TC-TX-06`.

## QC-04: Reloading the app 3 times within a minute locks the browser out

- **Severity / priority:** Major / P2.
- **Steps:**
  1. Open `http://<server>/` in a browser.
  2. Reload the page 3 times within ~20 s.
- **Expected:** the app loads every time.
- **Actual:** the 3rd load renders a blank page and the 4th shows the plain text **"Too many requests, please try
  again later."** for up to 60 s.
- **Root cause:** a global `express-rate-limit` of 500 requests/min per IP is mounted before
  `express.static`, so JS chunks, fonts and images count against it. One app load issues ~200 requests. Measured:
  the 501st request in a minute gets HTTP 429 with `Retry-After: 60`.
- **Impact:** everyone behind one public IP shares the budget (household NAT, office), and so does everyone behind
  a reverse proxy that is not listed in `trustedProxies`.
- **Suggested fix:** mount the limiter after `express.static`, or exclude static paths from it.
- **Evidence:** `QC-04_too_many_requests.png`; test `TC-AVAIL-02`.

## QC-01: Server prints "Listening" and exits 0 when it cannot bind

- **Severity / priority:** Major / P2. On an IPv6-less host (some Docker and VPS set-ups) the server dies silently.
  A process supervisor sees exit code 0 and may not restart it.
- **Steps:** on a host without IPv6, start `actual-server` with the default hostname (`::`).
- **Expected:** keep running, or exit with a non-zero code and an error such as `EAFNOSUPPORT`.
- **Actual:** the log shows `Listening on :::5006...`, and the process exits with **code 0**.
- **Root cause (confirmed):** Express 5's `app.listen(port, host, cb)` passes a bind error to `cb`. The server's
  callback ignores its argument and prints the success message. Reproduced in 3 lines with Express 5.3.0:
  `app.listen(5099, "::", err => console.log(err.code))` → `EAFNOSUPPORT`, exit 0.
- **Suggested fix:** `app.listen(port, hostname, (err) => { if (err) { console.error(err); process.exit(1); } … })`.
- **Workaround:** `ACTUAL_HOSTNAME=0.0.0.0`.
- **Evidence:** `evidence/logs/QC-01_server_exit.txt`; test `TC-AVAIL-01`.

## QC-02: Non-string password crashes `/account/bootstrap` (HTTP 500, stack trace)

- **Severity / priority:** Major / P2.
- **Steps:** `POST /account/bootstrap` with body `{"password": 12345}` (also an object or array).
- **Expected:** 400 `invalid-password`, the same as for an empty string.
- **Actual:** **HTTP 500** with an HTML error page. When `NODE_ENV` is not set (the default for an npm install, even
  though the log says "Running in production mode") the page includes the **stack trace and absolute file paths of
  the server**. With `NODE_ENV=production` the response is still 500, but without the trace.
- **Root cause:** `isValidPassword()` only checks `!= null && !== ""`. A number passes and reaches `argon2.hash()`,
  which throws.
- **Suggested fix:** `typeof password === "string" && password.length > 0`.
- **Evidence:** `evidence/logs/QC-02_bootstrap_500.html`; tests `TC-AUTH-05a/b/c`, `TC-AUTH-06`.

## QC-11: A typo in a budget cell wipes the existing amount (cycle 2)

- **Severity / priority:** Minor / P2. The budget amount is lost silently and To Budget changes, but the change is
  visible in the same cell and can be retyped.
- **Steps:**
  1. Budget page → Food → Budgeted, type `200` and press Enter.
  2. Click the same cell, type `abc`, and press Enter.
- **Expected:** the input is rejected and 200.00 stays (the account dialog rejects `abc` with "must be a number").
- **Actual:** the budget becomes **0.00** and To Budget rises by 200. No warning is shown.
- **Evidence:** test `TC-BUD-05`.

## QC-09: Non-numeric amount saves a 0.00 transaction

- **Severity / priority:** Minor / P3.
- **Steps:** register → *Add New* → deposit `abc` → *Add*.
- **Expected:** a validation message, as the account dialog gives for the same input.
- **Actual:** a 0.00 transaction is saved, and the typed text is lost.
- **Evidence:** test `TC-TX-04`.

## QC-03: A single space is accepted as the server password

- **Severity / priority:** Minor / P3. This is a security hardening issue, not a functional failure.
- **Steps:** on first run, set the password to `" "` (or `"a"`).
- **Expected:** a minimum length, and whitespace-only passwords rejected.
- **Actual:** accepted. The whole budget server is then protected by one keystroke.
- **Evidence:** tests `TC-AUTH-07a/b/c`.

## QC-10: Fresh budget shows `-0.00`

- **Severity / priority:** Trivial / P3.
- **Steps:** create a new budget and look at the month summary.
- **Expected:** `0.00`.
- **Actual:** `-0.00` under *Overspent*, *Budgeted* and *For next month*.
- **Evidence:** `evidence/screenshots/QC-10_negative_zero.png`; test `TC-UI-01`.

---

## Rejected finding (not a defect)

During exploration, 5 failed logins seemed to lock out **every** client, which would have been a critical DoS. The
re-test showed this was a test-harness error: connecting *to* `127.0.0.N` still sends traffic *from* `127.0.0.1`.
After binding the real source address, the lockout correctly applies per client (`TC-AUTH-11` passes).
The finding was withdrawn before it was reported.
