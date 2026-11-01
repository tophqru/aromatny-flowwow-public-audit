# Arena: focused offline repair proposal, no live browsing

> HISTORICAL / NOT DISPATCHED. The owner chose to continue actual parsing on
> their ASUS browser. The first SKU was subsequently CAPTURED with all six
> frames after bounded slow-image waiting, viewport exposure and interval
> polling were fixed locally. All three SKU now retain seller proof. This is
> an optional review reference, not a request to start another audit or crawl.

Repository: https://github.com/tophqru/aromatny-flowwow-public-audit
Branch: codex/flowwow-v3-windows-20261101 (public Draft PR #7).
Pinned starting parser: Arena PR #6 @ 018a39704c2cca54159e758216a6182683fdb98a.
Inspect the current PR head before starting. Work in a separate branch/Draft PR,
do not merge and do not change main, catalog, prices, stock or sale flags.

## One remaining issue

ASUS Windows 10 Pro 22H2, Python 3.15.2 x64, Playwright 1.64.1,
Edge 156.0.4314.50. Owner explicitly resumed ordinary observation using their
stable Russian connection; a separate Edge profile independently returned RU.
No further live visits are requested from Arena.

One strict three-SKU CLI run used --skip-shop, max-products 3,
max-categories 1, max-load-cycles 5, max-scroll-steps 40, no media downloads.
Targets in order: avtorskiy-buket-s-gortenz-3168, buket-gortenziy-23,
buket-gortenziy-pionov-roz-eus.

Second and third actually captured: seller popup ->
https://flowwow.com/shop/lyubov-eto-699e0e4519/?from=product,
six distinct UI currentSrc images each (1000x1000), Moscow/ru,
composition and dimensions parsed. Third description remained unverified.

First initial attempt: seller click registered but no popup after the old
1-second wait; final URL still exact product, SELLER_UNVERIFIED.
After adding a bounded 10-second observation of the SAME click, one targeted
--retry-failed run skipped the two CAPTURED targets. The first then failed:
Page.wait_for_function: Timeout 25000ms exceeded. It reached the gallery wait
in flowwow_dom.observe_ui, after the seller gate, but ERROR persistence discarded
intermediate seller/section/frame evidence. Do not claim retained seller proof
or complete capture for this first product. Do not suggest another full crawl.

## Verified DOM contract

Desktop .product-detail has one h1 and no main element.
Main slider: .product-detail-slider [id^=mainslider_].swiper-initialized.
It loops with .swiper-slide-duplicate clones. Nonduplicate active slide has
data-swiper-slide-index. Thumb slider: [id^=thumbslider_] img.thumb,
data-index-slide 0..5, six unique thumbnails. Active main img currentSrc must
decode with naturalWidth/naturalHeight >=480. Clicking the last thumbnail in
the diagnostic actually selected index 5; inline zoom was observed, no separate
fullscreen viewer was proven. Never read application state or hidden APIs.

Composition/size: .right-content > .properties > .property-item h3.property-name;
description: .product-properties-general-desktop > .property-item .pre-line.
Visible a.show-more expands composition. Size label hyphens are normalized in
an explicit parser_text while exact source text is preserved.
Seller: .product-about-shop a.shop-link; only canonical shop and the observed
exact ?from=product query are allowed, not arbitrary shops/queries/subpaths.

## Deliver only useful work

1. Review thumbnail readiness/active-clone/initial-slide edge cases. Reproduce
   likely causes with deterministic fakes; label hypotheses as hypotheses.
2. Propose a small patch that does not wait for an impossible active selector,
   does not fabricate successful frames, and remains bounded on slow networks.
3. Preserve partial seller/section/frame evidence on a later gallery timeout
   WITHOUT marking the product CAPTURED/complete or bypassing official gates.
4. Add focused regression tests; run the full existing suite once at the end.
5. Return findings, patch, exact test counts and a Draft PR. No live Flowwow,
   no IP/proxy changes, CAPTCHA solving, cookies, raw DOM, SQLite or screenshots.

Keep Phase-2 proposal separate: the third SKU is metadata-only in the first
pilot. phase2_media.py is separately gated and must not execute real downloads.
Do not relax the strict pilot manifest or machine acceptance to manufacture PASS.
ASUS browser QA remains Codex's responsibility after the proposed repair.
