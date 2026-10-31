#!/usr/bin/env python3
"""Offline validation of publicly indexed leads — NEVER promotion to verified catalog."""
import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "catalog" / "discovery"
def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))

def main():
    baseline = read("catalog/public-snapshot.json")
    verified = read("catalog/discovery/new-verified-seller-candidates-20261031-4.json")
    quarantine = read("catalog/discovery/QUARANTINED_INCOMPLETE_PUBLIC_CANDIDATES_2026-10-31.json")
    first = read("catalog/discovery/FLOWWOW_INDEXED_21_NEW_POSSIBLE_PRODUCTS_2026-10-31.json")
    second = read("catalog/discovery/FLOWWOW_INDEXED_6_MORE_POSSIBLE_PRODUCTS_2026-10-31.json")
    third = read("catalog/discovery/FLOWWOW_INDEXED_25_MORE_POSSIBLE_PRODUCTS_2026-10-31.json")
    known = set(p["slug"] for p in baseline["products"])
    known.update(p["slug"] for p in verified["products"])
    known.update(p["slug"] for p in quarantine["suspected_unfinished_candidates"])
    assert len(baseline["products"]) == 66 and len(verified["products"]) == 4
    assert len(quarantine["suspected_unfinished_candidates"]) == 2
    assert first["items_count"] == len(first["items"]) == 21
    assert second["total_new_this_batch"] == len(second["items"]) == 6
    assert second["combined_prior_candidates"] == 27
    assert third["previous_unverified_leads"] == 27
    assert third["new_leads"] == len(third["items"]) == 25
    assert third["total_unverified_leads"] == 52
    assert third["status"] == "INDEXED_DISPLAY_SELLER_NOT_CANONICALLY_CONFIRMED"
    assert third["visited_live_source_pages"] == 0 and third["clicked_show_more_count"] == 0
    assert first["status"] == "INDEXED_SELLER_DISPLAY_MATCH_ONLY_CANONICAL_SHOP_NOT_YET_VERIFIED"
    assert second["status"] == "INDEXED_DISPLAY_SELLER_NOT_CANONICALLY_CONFIRMED"
    assert first["source_access"]["direct_shop_open"] == "CACHE_MISS"
    assert first["source_access"]["connected_browser"] == "NOT_AVAILABLE_ORIGINATING_EXTENSION_CONTEXT_REQUIRED"
    assert first["source_access"]["visible_show_more_text"] == "YES_BUT_CANNOT_CLICK_JS_BUTTON_IN_THIS_SESSION"
    newly_seen = set()
    for p in first["items"] + second["items"] + third["items"]:
        slug = p["slug"]
        assert slug not in known and slug not in newly_seen, f"Duplicate or existing SKU: {slug}"
        assert slug != baseline["excluded_owner_sku"]
        newly_seen.add(slug)
        url = urlsplit(p["source_url"])
        assert url.scheme == "https" and url.hostname == "flowwow.com"
        assert url.path == f"/flowers/{slug}/"
        assert url.query == "" and url.fragment == ""
        assert p["displayed_seller"] == "Ароматный букет"
        assert p["seller_city_in_search_title"] == "Москва"
        assert p["source_ref"].startswith("turn") and "search" in p["source_ref"]
        assert p["observed_price_rub"] > 0
        assert p["may_order"] is False if "may_order" in p else p["do_not_add_to_retail"] is True
        assert p["exact_seller_identity_verified"] is False
        if "photos_saved" in p:
            assert p["photos_saved"] == 0
        else:
            assert p["photo_originals_saved"] == 0
    assert len(newly_seen) == 52
    print(json.dumps({"validation":"PASS_INDEXED_CANDIDATES","source_only":True,
                      "new_unverified_leads":len(newly_seen),
                      "existing_verified_cards":len(baseline["products"]),
                      "retail_additions":0,"photos_newly_saved":0,
                      "owner_excluded_reintroduced":False}))

if __name__ == "__main__":
    main()
