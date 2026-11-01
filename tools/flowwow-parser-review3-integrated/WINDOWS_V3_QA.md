# Windows V3 gate — 2026-11-01

Source: `018a39704c2cca54159e758216a6182683fdb98a` (Arena PR #6).

Windows 10 Pro 22H2 build 19045.5737, Python 3.15.2 x64, Playwright
1.64.1, Edge 156.0.4314.50, Pillow 12.3.0. Headed Edge data-URL smoke
returned the expected title and H1 in a separate temporary profile. Native
window inventory also showed the Edge smoke window; the Computer Use screenshot
tool refused the data URL, so no native screenshot verification is claimed.

## Changes and evidence

- Git core.autocrlf=true converted the pinned catalog fixture to CRLF. Its
  worktree bytes then failed the independent blob gate. `.gitattributes` keeps
  this one JSON byte-exact; expected/actual Git blob is
  `b1ba9fbe10b7961d35a723d40af01686a0e10b78`. Catalog content is unchanged.
- The atomic-write test required a POSIX directory fsync even though storage
  deliberately omits it on Windows. The test now checks file fsync before
  replace on both platforms, and directory fsync on POSIX. Production storage
  and its safety gates are unchanged.
- The kill/recovery test can launch a Windows venv redirector rather than the
  actual lock-owning interpreter. It now launches the base interpreter directly
  on Windows for this stdlib-only subprocess. No skip or retry was added.
- One permitted live product navigation returned HTTP 200 with empty title,
  body text and H1. The visible screenshot showed a spinner. A second snapshot
  of the same page still had no product UI. Local DOM inspection identified a
  `js-challenge-loader`, hidden `id_captcha_frame_div` and Servicepipe script.
  This is protective interstitial evidence, not product content.
- The navigation gate now inspects those structural DOM markers. Seven new
  offline tests cover blank-text challenge detection, negative controls,
  navigation stopping and byte-exact baseline. The SellerPage test double
  supplies content for the newly required DOM check.

## Actual checks

- Before fixes, 173 original tests ran on Windows with real platform and
  sandbox failures. After restoring pinned bytes and fixing the platform
  assertion, 173/173 passed, exit 0.
- Seven new targeted regressions: 7/7 passed, exit 0.
- Final full suite: **180/180 passed, 0 failures, 0 errors, 0 skipped**, exit 0.
- Final compileall: exit 0. Full raw local logs remain outside Git.
- Intermediate final runs exposed missing fake-page content and a Windows
  recovery subprocess failure; both were corrected, not hidden or skipped.

No protection bypass, IP rotation, cookies, raw DOM, screenshots, browser
profiles, SQLite or challenge values are included. Live work stopped at the
first interstitial; two further products were not visited. No three-SKU pilot,
seller/gallery proof, new photos, catalog completeness or import readiness is
claimed. Slow connectivity remains a separate consideration; the structural
challenge evidence is what triggered the stop. CI status must be read from
the PR checks, separately from these actual ASUS results.

## Owner-resumed pilot on stable Russian connection

The owner later configured Edge for Russian sites and explicitly resumed work.
A separate Edge profile returned RU from a public routing diagnostic (IP not
recorded). The permitted first product then loaded without a challenge; no
protective page was solved or modified. No further network switching was done.

The real desktop DOM required a narrow adapter: one .product-detail without
main, label-less desktop description, scoped composition/size, visible show-more,
unique indexed thumbnails, and exclusion of Swiper loop clones. The seller
guard admits only the observed canonical shop query ?from=product.

One strict 3-SKU run was executed using Windows PowerShell 5.1, --skip-shop,
fresh isolated SQLite and the checked dedicated browser profile. No media
download flag. Second and third products were seller-click verified and each
had all six displayed 1000x1000 frames clicked and decoded by the browser.
Their composition and dimensions were captured; third description stayed
unverified. The first seller click was initially not observed within 1s.
After a bounded delayed-popup fix, a single --retry-failed run skipped the two
CAPTURED products. The first reached the gallery wait but timed out (25s).
Intermediate evidence was not persisted as a successful first capture.
See ARENA_TARGETED_FIRST_SKU.md for a focused offline repair task; no more live
visits were attempted. Machine acceptance remains unmodified; crawl/export
returned 5 in both runs, and the first ERROR keeps overall acceptance BLOCKED.

Final suite after the adapter and separately gated Phase-2 proposal:
**194/194 PASS**, 0 fail/error/skip; compileall exit 0. Phase-2 negative gate
tests make zero requests and its positive JPEG test uses mocked transport.
No real Phase-2 download was authorized or executed. The first-pilot third-SKU
metadata-only guard remains unchanged. Maximum resolution beyond the actual
displayed 1000x1000 sources remains unproven, as does full catalog completeness.
