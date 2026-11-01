# ARENA NEW FINDINGS — Flowwow Parser REVIEW2 independent audit

Source under audit: PR #4 archive `flowwow_review2_source_code_only.tar.xz`
SHA256 `8a1df3c26ec7fdeb732ffdf3d2b1dd1360c6ec7859abc558fabe67c057d365a5`.

Scope rule: this file lists **only newly reproduced defects** found by this independent
pass. It does **not** repackage R1–R17. Every finding below has an executed offline
reproduction in `tests/test_arena_review2_independent.py`, a FAIL/ERROR before the fix
(`logs/02-independent-before.log`), and a PASS after the fix (`logs/03-full-after.log`).
No live Flowwow page was opened; none of these findings claims a live-DOM fact.

Legend: `original` = pristine archive line numbers; `fixed` = patched working tree.

## N01 — `doctor` crashes without dependencies instead of honest BLOCKED
- Severity: High (usability / wave A).
- Original: `capture.py:22` top-level `from PIL import ...`; `capture.py:540` `doctor`.
- Reproduction: `python -S capture.py doctor` → `ModuleNotFoundError: No module named 'PIL'`, exit 1
  (`logs/01-no-deps-doctor-before.log`, test `test_doctor_without_site_packages_reports_missing_not_traceback`).
- Fix: guarded heavy imports with `_IMPORT_ERROR` (`fixed capture.py:22`); `doctor` reports
  `dependencies=MISSING` and returns 0 (`fixed capture.py:587`); non-doctor commands fail with a
  clear exit 2 (`fixed capture.py:631`). After: `logs/04-after-no-deps-doctor.log`.

## N02 — direct `test_review1.py` silently skips integration tests
- Severity: Medium (test integrity).
- Original: `tests/test_review1.py:137` `if __name__=='__main__': unittest.main()` placed
  **before** `ResumeIntegrationTests`.
- Reproduction: `python tests/test_review1.py -v` ran only the first class; test
  `test_review1_script_mode_runs_integration_tests` failed because `ResumeIntegrationTests` was absent.
- Fix: moved the entrypoint to EOF (`fixed tests/test_review1.py:192`). After: direct script runs
  the integration tests (`logs/05-review1-script-after.log`).

## N03 — seller click ignores `target=_blank` / popup, false UNVERIFIED
- Severity: High (wave C seller verification).
- Original: `capture.py:299` `click_seller_link`; `capture.py:320` reads only `page.url`.
- Reproduction: fake page opens the exact canonical shop in a new tab; original code never inspects
  `context.pages`, so the exact seller is reported unverified
  (`test_seller_link_new_tab_is_verified`). A wrong-seller popup is still rejected
  (`test_seller_link_new_tab_other_seller_rejected`, passed before and after).
- Fix: detect new pages, wait for the popup, verify its canonical URL, close it, then return to the
  original SKU (`fixed capture.py:319`, `fixed capture.py:343`). Multiple popups fail closed.

## N04 — “Show more” opening a new tab is treated as ordinary stability
- Severity: Medium (wave B pagination).
- Original: `scroll_logic.py` click branch did not inspect `context.pages`.
- Reproduction: fake “Показать ещё” opens a popup; original loop keeps scrolling/stability logic
  (`test_show_more_new_tab_stops_not_stable` failed with `SCROLL_STEP_LIMIT_REACHED`).
- Fix: stop with `MORE_CONTROL_OPENED_NEW_TAB` and never claim complete
  (`fixed scroll_logic.py:100`).

## N05 — same-shop URL check rejects canonical shop without trailing slash
- Severity: Medium (wave B/C navigation).
- Original: `scroll_logic.py:92` and `capture.py` category guard used
  `path.startswith(expected.path)` where `expected.path` ends in `/`.
- Reproduction: `same_shop_url(SHOP.rstrip('/'))` had no helper and the original prefix check
  rejects the canonical root without a trailing slash
  (`test_same_shop_url_accepts_trailing_slash_and_subpath_only`).
- Fix: added `parsing.same_shop_url` (`fixed parsing.py:50`) accepting root with/without slash and
  true subpaths only; used by scroll and category navigation. Credentials/ports/other hosts rejected.

## N06 — exported HTML renders stored URLs as `href` without scheme validation (XSS)
- Severity: High (wave E output escaping).
- Original: `capture.py:527` `url=html.escape(p.get("url", ""),quote=True)` then `<a href="{url}">`.
- Reproduction: a stored `javascript:alert(1)` URL became an active link
  (`test_export_report_rejects_javascript_url`).
- Fix: only `canonical_product`/`canonical_shop` URLs become links; otherwise plain `<span>`
  (`fixed capture.py:572`). Slug escaping verified separately (`test_export_html_escapes_slug`).

## N07 — `download_assets` does not re-validate URLs before network request (SSRF surface)
- Severity: High (wave E SSRF/CDN validation).
- Original: `capture.py:351` `context.request.get(url,...)` used the queued URL directly.
- Reproduction: a private metadata URL reached the mocked request layer
  (`test_download_assets_unsafe_url_no_network`).
- Fix: re-run `image_url_safe` before any request; unsafe URLs record `UNSAFE_IMAGE_URL` and make
  **no** network call (`fixed capture.py:374`). Redirects are still not followed
  (`test_image_redirect_not_followed`).

## N08 — baseline validation ignores sale-permission flags
- Severity: High (wave F / no automatic sale approval).
- Original: `capture.py:110` `validate_baseline` checked seller/slug/excluded SKU but not
  `owner_approved`, `may_order`, `may_show_publicly`.
- Reproduction: a baseline product with `may_order=True` was accepted
  (`test_baseline_rejects_sale_flags_true`).
- Fix: any present permission flag must be exactly `False` (`fixed capture.py:127`).
  Owner-excluded SKU rejection re-verified (`test_baseline_excluded_sku_rejected`).

## N09 — gallery candidate list silently truncates at 60
- Severity: Medium (wave D gallery completeness honesty).
- Original: `parsing.py:211` returned `items[:60]` with no truncation flag.
- Reproduction: 61 candidates produced 60 items and no `truncated` key
  (`test_gallery_truncation_flag`, ERROR before).
- Fix: return `candidate_count` and `truncated` (`fixed parsing.py:232`). Status remains
  `GALLERY_CANDIDATES_UNVERIFIED_COMPLETENESS`; this is not a completeness proof.

## N10 — gallery ignores lazy `data-srcset` / `data-original`
- Severity: Medium (wave D lazy-load/original resolution).
- Original: `parsing.py:191` read only `srcset`, `src`, `data-src`.
- Reproduction: an image whose only original is in `data-srcset` was missed
  (`test_gallery_data_srcset_lazy`).
- Fix: parse `srcset` + `data-srcset` and `src`/`data-src`/`data-original`
  (`fixed parsing.py:210`). No URL rewriting; renamed thumbnails still cannot prove originals.

## N11 — labelled “Ширина … Высота …” dimensions not parsed
- Severity: Low/Medium (wave C field recovery).
- Original: `parsing.py:155` `parse_dimensions` only matched `W×H`.
- Reproduction: `Ширина: 35 см. Высота: 45 см.` returned `UNVERIFIED_PARSE`
  (`test_dimensions_labelled_width_height`).
- Fix: conservative labelled fallback requiring exactly one width and one height
  (`fixed parsing.py:173`). Ambiguous multiple sizes still fail closed
  (`test_dimensions_ambiguous_multiple_unverified`).

## N12 — atomic write lacks directory fsync (power-loss durability gap)
- Severity: Medium (wave E crash/recovery).
- Original: `storage.py:21` `os.replace(tmp,path)` without persisting the directory entry.
- Reproduction: mocked `os.fsync` called once (file only)
  (`test_atomic_bytes_fsyncs_directory`).
- Fix: fsync the parent directory on POSIX after replace (`fixed storage.py:25`).
  Windows has no portable directory fsync; file flush + atomic replacement remains the available
  guarantee. This is a durability improvement, **not** a claimed power-loss test.

## N13 — nested-scroll flag is a document-height heuristic (false ±)
- Severity: Medium (wave B nested scrollables).
- Original: `scroll_logic.py:54` `height <= viewport+4`.
- Reproduction: short page flagged nested=True; a real nested container on a tall page flagged
  nested=False (`test_nested_scroll_flag_not_short_page`, `test_nested_scroll_flag_detects_container`).
- Fix: JS detects actual `overflowY:auto|scroll` containers with overflow; flag uses `state.nested`
  (`fixed scroll_logic.py:59`). Still only an observation, never completeness proof.

## N14 — trial→full resume trusts recorded media without checking the local file
- Severity: High (wave E media loss trial→full).
- Original: `capture.py:133` `needs_media_capture(result, max_assets)` marked URLs done from DB
  status alone.
- Reproduction: a recorded `NEW_ORIGINAL_FILE` whose file was deleted still returned False;
  passing an output dir raised TypeError (`test_needs_media_capture_detects_missing_local_file`,
  `test_needs_media_capture_accepts_present_local_file`).
- Fix: optional `out` verifies path safety, existence and SHA256 before treating media as done;
  crawl passes `out` (`fixed capture.py:141`). Missing/corrupt files trigger recapture.

## N15 — `setup_windows.ps1` prints SETUP SUCCESS even if Chromium install failed
- Severity: Medium (wave A Windows honesty).
- Original: `setup_windows.ps1:25` unconditional `SETUP SUCCESS`.
- Reproduction: static assertion that success is conditional failed
  (`test_setup_windows_does_not_claim_success_without_browser`).
- Fix: track `$browserReady`; print `SETUP PARTIAL` and exit 1 when bundled Chromium is absent
  (`fixed setup_windows.ps1:22`, `:26`). PowerShell 5.1 execution itself was NOT_PERFORMED here.

## Characterization checks that passed before and after (not new defects)
Canonical-product homograph/credential host rejection; image URL allowlist (private/data/javascript);
decimal composition quantity fails closed; category labels ignore “Показать ещё” and external links;
gallery status never says COMPLETE; image 301 not followed; SQLite WAL reopen; exclusive lock released
after exception; HTML slug escaping; owner-excluded SKU rejection; Cyrillic/space paths for atomic
write and SQLite. These are recorded to bound the audit, not claimed as fixes.

## Explicit non-findings / limits
- No live Flowwow DOM was observed; selector behavior on the real SPA remains unverified.
- No Windows/PowerShell 5.1 runtime was available; `.ps1` changes are static-checked only.
- No claim that 66 SKU / 435 JPEG are complete; see `baseline-reconciliation.json`.
- R1–R17 are intentionally excluded from this file.
