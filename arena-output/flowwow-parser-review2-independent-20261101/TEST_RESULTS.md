# TEST RESULTS — REVIEW2 independent audit

Environment: `environment.json` (Linux 6.1.158, Python 3.11.2; venv Playwright 1.64.1,
beautifulsoup4 4.15.0, Pillow 12.3.0). **No** `pwsh`, `powershell`, `chromium`,
`chromium-browser`, or `google-chrome` binaries. No live Flowwow network access attempted.

All commands below were actually executed. Logs are in `logs/`.

## 1. Author baseline (independently reproduced, not trusted)
```
cd <pristine archive>/flowwow_review2
python -m compileall -q .
python -m unittest discover -s tests -v
```
- compileall: PASS.
- unittest: **Ran 53 tests, OK** — `logs/00-baseline-53-tests.log`.
- The PR #4 claim of 53 passing offline tests is confirmed on this machine.

## 2. Missing-dependency doctor (before fix)
```
/usr/bin/python3 -S capture.py doctor
```
- Exit 1, `ModuleNotFoundError: No module named 'PIL'` — `logs/01-no-deps-doctor-before.log`.
- This is finding N01.

## 3. Independent new scenarios against pristine archive (FAIL-before)
```
cd <pristine archive>/flowwow_review2
python -m unittest discover -s tests -p 'test_arena_review2_independent.py' -v
```
- **Ran 32 tests; FAILED (failures=14, errors=4)** — `logs/02-independent-before.log`.
- 18 scenarios fail/error on the original code; 14 characterization scenarios pass.
- Failing tests map to findings N01–N15 (see `ARENA_NEW_FINDINGS.md`).

## 4. Full regression after fixes (PASS-after)
```
cd source/flowwow_review2
python -m compileall -q .
python -m unittest discover -s tests -v
```
- compileall: PASS.
- unittest: **Ran 85 tests, OK** (53 original + 32 independent) — `logs/03-full-after.log`.
- No original test was weakened; the only original-test edit is moving the `test_review1.py`
  `__main__` guard to EOF (N02).

## 5. Missing-dependency doctor (after fix)
```
/usr/bin/python3 -S capture.py doctor
```
- Exit 0, JSON `dependencies=MISSING`, `action=BLOCKED...` — `logs/04-after-no-deps-doctor.log`.
- `python -S capture.py crawl --offline-baseline ...` exits 2 with a friendly message and no
  traceback (covered by `test_crawl_without_dependencies_fails_friendly`).

## 6. Direct test_review1 script (after fix)
```
python tests/test_review1.py -v
```
- Exit 0; includes `ResumeIntegrationTests` — `logs/05-review1-script-after.log`.

## 7. Patch verification on a fresh extraction
```
patch -p1 < patch/flowwow-review2-independent-fixes.patch   # in a fresh archive extraction
python -m unittest discover -s tests -v
```
- Patch applies cleanly; **Ran 85 tests, OK** — `logs/06-patch-apply.log`.
- This proves the delivered patch reproduces the fixed tree from the published archive.

## 8. Offline baseline reconciliation (wave F)
- Read base branch `audit/chatgpt-description-recovery-20261031` @
  `864f6e222ea58cfed063f6594f896edb67ed8e7f` via `git show` (no checkout, no catalog edits).
- 66 SKU / 435 gallery URLs; local 435 JPEG / 49,614,983 bytes; 59 compositions, 36 descriptions,
  54 valid dimension pairs; 49 missing field values across 30 SKU; 4 seller-verified pending,
  55 indexed unverified candidates, 2 quarantined; owner-excluded SKU absent; all permission flags
  `False`. See `baseline-reconciliation.json`.

## Not performed (honest blockers)
- Live Flowwow browsing, seller clicks, pagination, gallery fullscreen: **LIVE_NOT_PERFORMED**
  (no browser binaries; no authorized session used). See `FLOWWOW_LIVE_EVIDENCE.md`.
- Windows / PowerShell 5.1 execution: **NOT_PERFORMED** (no pwsh/powershell). `.ps1` changes are
  static-checked only.
- Remote CI: not triggered (prior `gh workflow run` returned HTTP 403 for this integration).
