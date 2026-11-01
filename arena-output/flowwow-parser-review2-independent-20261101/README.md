# Flowwow Parser REVIEW2 — ARENA independent deep audit

Independent audit of the published REVIEW2 source in
[PR #4](https://github.com/tophqru/aromatny-flowwow-public-audit/pull/4), starting from the code
archive (not from a plan). This is **new** work; it does not re-report R1–R17.

## Headline result
- Author baseline independently reproduced: **53/53 offline tests OK**, compileall PASS.
- **32 new independent offline scenarios** written; **18 failed/errored on the original code**.
- **15 new defects (N01–N15)** reproduced and fixed; full regression after fixes: **85/85 OK**.
- Delivered patch applies cleanly to a fresh archive extraction and reproduces **85/85 OK**.
- Live Flowwow: **LIVE_NOT_PERFORMED** (no browser binaries). Windows/PowerShell: **NOT_PERFORMED**.
- No catalog/production/media/sale-permission changes; 0 new images; 0 live pages.

## Contents
- `ARENA_NEW_FINDINGS.md` — only newly proven defects, with original/fixed line references.
- `TEST_RESULTS.md` — executed commands, OS, outcomes, log paths.
- `FLOWWOW_LIVE_EVIDENCE.md` — all-zero live counters; honest blockers.
- `baseline-reconciliation.json` — wave F reconciliation against base branch @ `864f6e22…`.
- `environment.json` — Python/package versions and absent browser/PowerShell binaries.
- `source/flowwow_review2/` — fixed working tree (includes the 32 new tests).
- `patch/flowwow-review2-independent-fixes.patch` — delta vs the published archive.
- `logs/` — before/after and patch-verification logs.
- `input/` — verified input archive and assignment (for provenance).
- `flowwow-review2-independent-delta.zip` — portable delta (fixed source + patch + reports + logs).
- `delivery.json`, `SHA256SUMS` — delivery metadata and integrity hashes.

## Apply the patch
```
tar -xJf flowwow_review2_source_code_only.tar.xz
cd flowwow_review2
patch -p1 < /path/to/flowwow-review2-independent-fixes.patch
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v   # expect Ran 85 tests, OK
```
(The patch uses `a/flowwow_review2/...` paths; run `patch -p1` from the directory that contains
`flowwow_review2`, or `patch -p2` from inside it.)

## Delivery note (why ZIP delta, not a second Draft PR)
The assignment requests a separate Draft PR to base `audit/chatgpt-description-recovery-20261031`,
or a ZIP delta if a PR is not possible. This session is fixed to branch
`arena/ccb3137a-aromatny-flowwow-public-audit`, which already has open Draft PR #3 to that same base.
GitHub does not allow a second open PR with the identical head/base pair, and creating/switching
branches is not permitted in this session. Therefore the verified **ZIP delta + patch** is delivered
here and linked from a PR comment, rather than opening a duplicate PR. No merge was performed.

## Reproduce the audit
```
python -m unittest discover -s tests -p 'test_arena_review2_independent.py' -v  # on pristine: 18 fail
python -m unittest discover -s tests -v                                       # on fixed: 85 OK
python -S capture.py doctor                                                   # honest MISSING/BLOCKED
```
