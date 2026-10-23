# Test summary report: Actual Budget v26.10.0

**Result: exit criteria met, with open Major defects.** All 16 in-scope requirements were covered. 10 defects were
reported: 0 Critical, 7 Major, 2 Minor, 1 Trivial. Four of the Major defects store wrong money or date values
silently, so the recommendation is to **fix QC-05, QC-06 and QC-07 before the next release**.

## Execution

| | Count |
|---|---:|
| Test cases (scripted) | 42 |
| Passed | 26 |
| Failed (defect raised) | 16 |
| Exploratory charters | 3 |
| Automated | 42 / 42 (pytest: 26 passed, 16 xfailed, in ~2 min) |
| Requirements covered | 16 / 16 (7 fully passing, 9 with open defects) |

## Defects by area and severity

| Area | Major | Minor | Trivial | Total |
|---|---:|---:|---:|---:|
| Money and date entry (accounts, register) | 4 | 1 | | 5 |
| Server: availability | 2 | | | 2 |
| Server: security / setup | 1 | 1 | | 2 |
| Display | | | 1 | 1 |
| **Total** | **7** | **2** | **1** | **10** |

## What worked well in the product

- Validation in the account dialog is clear (blank name, duplicate name, non-numeric balance).
- Login is correct: case-sensitive, rejects forged tokens, and the brute-force lockout (5 failures / 15 min) applies
  per client and ignores successful logins.
- The register evaluates arithmetic (`100+50` → 150.00), rounds half-cents, and accepts the European format
  `1.234,56`.

## Main risk

The same money input is parsed **three different ways** in the same app:

| Input | Account dialog | Register |
|---|---|---|
| `100+50` | 10,050.00 | 150.00 |
| `1e3` | 13.00 | 1.00 |
| `abc` | error | 0.00 saved |

A user who copies an amount from a spreadsheet or calculator can store a wrong balance and never see a warning.
**Suggestion:** one shared amount parser for every money field, covered by one table-driven unit test.

## Lessons from this cycle

- **A false positive was caught before reporting.** 5 failed logins appeared to lock out every client, which would
  have been a Critical DoS. It was a harness mistake: traffic sent to 127.0.0.N still comes from 127.0.0.1. Re-testing
  with real source addresses showed correct per-client behaviour, and the finding was withdrawn.
- **An automation artefact was not reported.** In one early scripted run an amount looked "lost". It did not
  reproduce with slower typing, so it was treated as a test-timing issue, not a product defect.
- **Root causes were traced where possible** (QC-01, QC-02, QC-04), so the reports also suggest a fix.

## Next cycle

Budget allocation and overspending roll-over, CSV/OFX import, mobile layout, and regression of the 10 defects. The
xfail tests turn red automatically when a fix lands.
