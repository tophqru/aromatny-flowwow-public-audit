#!/usr/bin/env python3
"""Independent, read-only Flowwow baseline audit for the public GitHub mirror.

Writes only machine-readable delta/audit files inside this output directory.
Never contacts Flowwow, never downloads product images, never changes catalog/,
data/, scripts/, workflows, prices, stock, or sale permissions.
Requires Pillow for JPEG decoding. Python 3.11+ recommended.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import random
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

SOURCE_BRANCH = "audit/chatgpt-description-recovery-20261031"
SOURCE_SHA = "f1e717fda918ce4ca8ccba9d4e8dc5ab7ab8f048"
MAIN_SHA = "3c35d693a2b128580beaa5f754450a38d7276d4b"
EXPECTED_CATALOG_TREE = "fe667ba7e4745dc9d6679013e89f37fe5f5a4e93"
EXPECTED_MEDIA_TREE = "e775b74898826e1f9c45d7370b6bebd247295a3e"
EXPECTED_SNAPSHOT_SHA256 = "18a1741ff949547bc52ba21550814784e214150f371790d5cc780c53d7416360"
SELLER_URL = "https://flowwow.com/shop/lyubov-eto-699e0e4519/"
EXCLUDED_SKU = "kompoziciya-v-shlyapnoy-k-4183"
PRIORITY_SEVEN = [
    "avtorskiy-buket-roza-alst-8286",
    "avtorskiy-buket-s-gortenz-3168",
    "avtorskiy-buketik-dlya-tebya-r",
    "buket-gortenzii-roza-pionovidn",
    "buket-gortenziy-23",
    "buket-iz-kustovoy-pionovi-3287",
    "buket-iz-roz-kustovoy-pio-6913",
]
DESC_OK = {"OBSERVED_SOURCE_TEXT", "SOURCE_TEXT_VERIFIED_2026-10-31"}
SALE_FLAGS = ("owner_approved", "may_order", "may_show_publicly")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def reject_constant(value: str):
    raise ValueError(f"Non-standard JSON constant: {value}")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object,
                      parse_constant=reject_constant)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def canonical_url(url: str, kind: str, slug: str | None = None) -> bool:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "flowwow.com" or parsed.query or parsed.fragment:
        return False
    if kind == "shop":
        return parsed.path == "/shop/lyubov-eto-699e0e4519/"
    return bool(slug) and parsed.path == f"/flowers/{slug}/"


def valid_dimensions(value) -> bool:
    return isinstance(value, dict) and all(
        type(value.get(key)) in (int, float) and math.isfinite(value[key]) and value[key] > 0
        for key in ("width", "height")
    )


def valid_composition(value) -> bool:
    return isinstance(value, list) and len(value) > 0 and all(
        isinstance(item, dict)
        and isinstance(item.get("component"), str) and item["component"].strip()
        and type(item.get("quantity")) in (int, float)
        and math.isfinite(item["quantity"]) and item["quantity"] > 0
        and isinstance(item.get("unit"), str) and item["unit"].strip()
        for item in value
    )


def valid_description(product: dict) -> bool:
    return isinstance(product.get("description_raw_ru"), str) and bool(product["description_raw_ru"].strip()) \
        and product.get("description_status") in DESC_OK


def parse_composition_raw(raw: str):
    """Parse the exact 'Component - N шт.' sentences used by the saved source observations."""
    result = []
    for sentence in re.split(r"(?<=шт\.)\s+", raw.strip()):
        match = re.fullmatch(r"(.+?)\s+-\s+(\d+(?:[.,]\d+)?)\s+(шт)\.", sentence.strip())
        if not match:
            return None
        component, quantity, unit = match.groups()
        number = float(quantity.replace(",", "."))
        if number.is_integer():
            number = int(number)
        result.append({"component": component.strip(), "quantity": number, "unit": unit})
    return result or None


def normalized_composition(items):
    return [(x["component"].strip().casefold(), x["quantity"], x["unit"].strip()) for x in items]


def ref(path: str, pointer: str = "") -> dict:
    return {"file": path, "json_pointer": pointer}


def write_json(path: Path, value, no_write: bool):
    if not no_write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--no-write", action="store_true", help="Validate and print summary without changing files")
    args = parser.parse_args()
    root = args.repo_root.resolve()
    out = args.output_dir.resolve()
    from PIL import Image

    started = utcnow()
    current_sha = git(root, "rev-parse", "HEAD")
    current_branch = git(root, "branch", "--show-current")
    catalog_tree = git(root, "rev-parse", "HEAD:catalog")
    media_tree = git(root, "rev-parse", "HEAD:data/flowwow/items")
    snapshot_path = root / "catalog/public-snapshot.json"
    snapshot_hash = sha256_file(snapshot_path)
    protected_diff = git(root, "diff", "--name-only", SOURCE_SHA, "--", "catalog", "data", "scripts", ".github", "arena")
    worktree_diff = git(root, "diff", "--name-only", "--", "catalog", "data", "scripts", ".github", "arena")
    untracked = [x for x in git(root, "ls-files", "--others", "--exclude-standard").splitlines()
                 if x and not x.startswith("arena-output/")]
    assert catalog_tree == EXPECTED_CATALOG_TREE, "Catalog tree changed; re-review the baseline before reuse"
    assert media_tree == EXPECTED_MEDIA_TREE, "Media tree changed; re-review the baseline before reuse"
    assert snapshot_hash == EXPECTED_SNAPSHOT_SHA256, "Snapshot bytes changed"
    assert not protected_diff and not worktree_diff and not untracked, "Protected source files changed"

    json_files = sorted((root / "catalog").rglob("*.json"))
    json_errors = []
    for path in json_files:
        try:
            load_json(path)
        except Exception as exc:
            json_errors.append({"file": str(path.relative_to(root)), "error": str(exc)})
    assert not json_errors, json_errors
    manifest = load_json(snapshot_path)
    products = manifest["products"]
    by_slug = {p["slug"]: p for p in products}
    assert len(by_slug) == len(products) == manifest["products_count"] == 66
    assert manifest["seller"] == SELLER_URL and manifest["retail_approved_count"] == 0
    assert manifest["inventory_scope"] == "PUBLIC_CONFIRMED_SKU_NOT_COMPLETE_SELLER_INVENTORY"
    assert EXCLUDED_SKU not in by_slug
    old_manifest = json.loads(git(root, "show", f"{MAIN_SHA}:catalog/public-snapshot.json"))
    old_by_slug = {p["slug"]: p for p in old_manifest["products"]}

    # Strict JSON parse of every individual card, plus exact equality with the snapshot.
    card_dirs = sorted(p for p in (root / "catalog/cards").iterdir() if p.is_dir())
    assert {p.name for p in card_dirs} == set(by_slug)
    for product in products:
        assert load_json(root / "catalog/cards" / product["slug"] / "product.json") == product

    # Check all local Markdown links in catalog/ and the ordered image links in every card.
    broken_links = []
    markdown_files = sorted((root / "catalog").rglob("*.md"))
    for path in markdown_files:
        text = path.read_text(encoding="utf-8")
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
            if target.startswith(("https://", "http://", "#", "mailto:")):
                continue
            local = unquote(target.split("#", 1)[0])
            if local and not (path.parent / local).exists():
                broken_links.append({"file": str(path.relative_to(root)), "target": target})
    assert not broken_links, broken_links

    # Remote GitHub tree was checked separately with gh api; no image bytes were fetched.
    remote_tree_check = load_json(out / "logs/github-source-tree-check.json")
    assert remote_tree_check["requested_tree_sha"] == SOURCE_SHA
    assert remote_tree_check["remote_media_blob_count"] == 435
    assert remote_tree_check["path_sets_equal"] and remote_tree_check["all_media_blob_oids_equal"]
    assert remote_tree_check["remote_tree_truncated"] is False

    tree_lines = git(root, "ls-tree", "-r", SOURCE_SHA, "data/flowwow/items").splitlines()
    git_media_oids = {}
    for line in tree_lines:
        meta, path = line.split("\t", 1)
        if path.lower().endswith((".jpg", ".jpeg")):
            git_media_oids[path] = meta.split()[2]
    physical_media = {str(p.relative_to(root)) for p in (root / "data/flowwow/items").rglob("*")
                      if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg"}}
    assert len(git_media_oids) == len(physical_media) == manifest["photos_count"] == 435

    findings = []

    def add_finding(code, severity, title, slugs, details, recommendation, evidence=None):
        findings.append({
            "id": f"F{len(findings)+1:03d}", "code": code, "severity": severity,
            "title_ru": title, "slugs": slugs, "details": details,
            "recommendation_ru": recommendation,
            "evidence": evidence or [], "confirmed_by": "OFFLINE_PUBLIC_GITHUB_FILES",
            "live_flowwow_reverified": False,
        })

    missing_composition, missing_description, missing_dimensions = [], [], []
    invalid_dimension_objects, duplicate_components = [], []
    product_rows = []
    hash_locations, url_locations = defaultdict(list), defaultdict(list)
    media_rows, media_errors = [], []
    total_bytes = 0
    jpeg_sizes, jpeg_modes = Counter(), Counter()
    exif_count = icc_count = comment_count = 0
    aggregate = hashlib.sha256()
    readme_errors = []
    readme_without_explicit_seller_link = []
    composition_raw_mismatches, dimension_observation_mismatches, description_observation_mismatches = [], [], []
    numeric_price_differences, newly_visible_prices = [], []

    for product in products:
        slug = product["slug"]
        assert re.fullmatch(r"[a-z0-9-]{1,100}", slug)
        assert canonical_url(product["flowwow_url"], "product", slug)
        assert canonical_url(product["seller_url"], "shop")
        assert product["seller_url"] == SELLER_URL
        assert all(product.get(flag) is False for flag in SALE_FLAGS)
        assert product["retail_status"] == "ADMIN_ONLY_PENDING_OWNER_APPROVAL"
        if not valid_composition(product.get("composition_items")):
            missing_composition.append(slug)
        else:
            names = [x["component"].strip().casefold() for x in product["composition_items"]]
            duplicates = sorted(name for name, count in Counter(names).items() if count > 1)
            if duplicates:
                duplicate_components.append({"slug": slug, "components": duplicates})
        if not valid_description(product):
            missing_description.append(slug)
        dims = product.get("dimensions_cm")
        if not valid_dimensions(dims):
            missing_dimensions.append(slug)
            if dims is not None:
                invalid_dimension_objects.append({"slug": slug, "value": dims})

        observation = product.get("latest_source_observation") or {}
        if observation.get("composition_raw_ru"):
            parsed = parse_composition_raw(observation["composition_raw_ru"])
            if parsed is None or normalized_composition(parsed) != normalized_composition(product["composition_items"]):
                composition_raw_mismatches.append({"slug": slug, "raw": observation["composition_raw_ru"],
                                                   "structured": product["composition_items"], "parsed": parsed})
        if observation.get("dimensions_cm") is not None and observation.get("dimensions_cm") != dims:
            dimension_observation_mismatches.append({"slug": slug, "stored": dims,
                                                     "observed": observation.get("dimensions_cm")})
        if observation.get("raw_description_ru") is not None and observation.get("raw_description_ru") != product.get("description_raw_ru"):
            description_observation_mismatches.append({"slug": slug})
        old_price = product.get("price_observed_rub")
        new_price = observation.get("price_visible_in_buy_block_rub")
        if type(old_price) in (int, float) and type(new_price) in (int, float) and old_price != new_price:
            numeric_price_differences.append({"slug": slug, "legacy_top_level_rub": old_price,
                                              "saved_buy_block_rub": new_price,
                                              "observation_date": observation.get("observed_on"),
                                              "source_url": observation.get("page_url")})
        if old_price is None and type(new_price) in (int, float):
            newly_visible_prices.append({"slug": slug, "legacy_top_level_rub": None,
                                         "saved_buy_block_rub": new_price,
                                         "observation_date": observation.get("observed_on"),
                                         "source_url": observation.get("page_url")})

        gallery = product["gallery"]
        assert gallery and len(gallery) == len({x["order"] for x in gallery})
        gallery_ok = True
        for order, image in enumerate(gallery, 1):
            expected_path = f"data/flowwow/items/{slug}/photos/{order:02d}.jpg"
            assert image["order"] == order and image["path"] == expected_path
            parsed_url = urlsplit(image["source_url"])
            assert parsed_url.scheme == "https" and re.fullmatch(r"content[1-9]\.flowwow-images\.com", parsed_url.hostname or "")
            assert re.fullmatch(r"/data/flowers/1000x1000/[0-9]+/[0-9]+_[0-9]+\.jpg", parsed_url.path)
            assert re.fullmatch(r"[0-9a-f]{64}", image["sha256"]) and image["bytes"] > 0
            path = root / expected_path
            if not path.is_file():
                media_errors.append({"path": expected_path, "error": "MISSING_FILE"})
                gallery_ok = False
                continue
            binary = path.read_bytes()
            actual_hash = sha256_bytes(binary)
            checks = {
                "bytes": len(binary) == image["bytes"],
                "sha256": actual_hash == image["sha256"],
                "git_blob_oid": git_blob_sha1(binary) == git_media_oids.get(expected_path),
            }
            try:
                with Image.open(io.BytesIO(binary)) as decoded:
                    checks["jpeg_format"] = decoded.format == "JPEG"
                    jpeg_sizes[f"{decoded.width}x{decoded.height}"] += 1
                    jpeg_modes[decoded.mode] += 1
                    exif_count += bool(decoded.getexif())
                    icc_count += bool(decoded.info.get("icc_profile"))
                    comment_count += bool(decoded.info.get("comment"))
                    decoded.verify()
                    checks["decode_verify"] = True
            except Exception as exc:
                checks["decode_verify"] = False
                media_errors.append({"path": expected_path, "error": str(exc)})
            if not all(checks.values()):
                gallery_ok = False
                media_errors.append({"path": expected_path, "failed_checks": [k for k, v in checks.items() if not v]})
            total_bytes += len(binary)
            aggregate.update(f"{expected_path}\0{len(binary)}\0{actual_hash}\n".encode())
            hash_locations[actual_hash].append({"slug": slug, "order": order, "path": expected_path,
                                                "source_url": image["source_url"]})
            url_locations[image["source_url"]].append({"slug": slug, "order": order, "sha256": actual_hash})
        card_readme = root / "catalog/cards" / slug / "README.md"
        readme = card_readme.read_text(encoding="utf-8")
        linked_images = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", readme)
        resolved_images = [str((card_readme.parent / unquote(x)).resolve().relative_to(root)) for x in linked_images]
        expected_images = [x["path"] for x in gallery]
        if resolved_images != expected_images or product["flowwow_url"] not in readme:
            readme_errors.append(slug)
        if SELLER_URL not in readme:
            readme_without_explicit_seller_link.append(slug)
        media_rows.append({"slug": slug, "gallery_records": len(gallery), "physical_files_checked": len(gallery),
                           "all_binary_checks_pass": gallery_ok, "readme_image_order_matches": resolved_images == expected_images,
                           "gallery_manifest_sha256": sha256_bytes(json.dumps(gallery, ensure_ascii=False, sort_keys=True).encode()),
                           "live_source_gallery_compared": False})
        gap_fields = [field for field, missing in (("composition_items", missing_composition),
                                                   ("description_raw_ru", missing_description),
                                                   ("dimensions_cm", missing_dimensions)) if slug in missing]
        product_rows.append({
            "slug": slug, "name_ru": product["name_ru"], "source_url": product["flowwow_url"],
            "source_category": product["source_category"], "offline_audit_status": "CHECKED_PUBLIC_FILES",
            "live_flowwow_status": "NOT_PERFORMED_NO_INTERACTIVE_BROWSER",
            "seller_url_in_source": product["seller_url"],
            "seller_evidence_in_source": product["seller_evidence"],
            "canonical_seller_reverified_this_run": False,
            "missing_or_unusable_fields": gap_fields,
            "composition_valid": valid_composition(product.get("composition_items")),
            "description_valid": valid_description(product),
            "dimensions_value": dims, "dimensions_valid": valid_dimensions(dims),
            "card_equals_snapshot": True, "gallery_binary_integrity_pass": gallery_ok,
            "gallery_count": len(gallery), "sale_flags": {flag: product[flag] for flag in SALE_FLAGS},
            "priority_seven": slug in PRIORITY_SEVEN,
        })

    assert not media_errors and not readme_errors, {"media_errors": media_errors[:10], "readme_errors": readme_errors}
    assert not composition_raw_mismatches and not dimension_observation_mismatches and not description_observation_mismatches, {"composition": composition_raw_mismatches[:3], "dimensions": dimension_observation_mismatches[:3], "description": description_observation_mismatches[:3]}
    assert total_bytes == manifest["media_expected_bytes"] == 49614983
    assert set(git_media_oids) == physical_media == {x["path"] for p in products for x in p["gallery"]}
    duplicate_hash_groups = [{"sha256": digest, "occurrences": locations}
                             for digest, locations in hash_locations.items() if len(locations) > 1]
    duplicate_url_groups = [{"source_url": url, "occurrences": locations}
                            for url, locations in url_locations.items() if len(locations) > 1]
    cross_sku_hash_groups = [g for g in duplicate_hash_groups if len({x["slug"] for x in g["occurrences"]}) > 1]
    assert not duplicate_url_groups, "Same source URL appears more than once; review before interpreting duplicates"

    # Cross-check dedicated public evidence against the current fields. These are consistency checks,
    # not new live observations and not new field recoveries.
    evidence_paths = {
        "desc_audit": "catalog/evidence/SOURCE_DESCRIPTION_AUDIT_2026-10-31.json",
        "desc_b3": "catalog/evidence/SOURCE_DESCRIPTION_RECOVERY_2026-10-31_BATCH3.json",
        "desc_b4": "catalog/evidence/SOURCE_DESCRIPTION_RECOVERY_2026-10-31_BATCH4.json",
        "desc_b5": "catalog/evidence/SOURCE_DESCRIPTION_RECOVERY_2026-10-31_BATCH5.json",
        "desc_b7": "catalog/evidence/SOURCE_DESCRIPTION_RECOVERY_2026-10-31_BATCH7.json",
        "dim_five": "catalog/evidence/FLOWWOW_FIVE_DIMENSION_PAIRS_2026-10-31.json",
        "obs_b1": "catalog/evidence/SOURCE_OBSERVATIONS_2026-10-31_BATCH1.json",
        "obs_b2": "catalog/evidence/SOURCE_OBSERVATIONS_2026-10-31_BATCH2.json",
        "obs_b6": "catalog/evidence/SOURCE_OBSERVATIONS_2026-10-31_BATCH6.json",
    }
    evidence = {key: load_json(root / path) for key, path in evidence_paths.items()}
    evidence_mismatches = []
    description_provenance = defaultdict(list)
    dimension_provenance = defaultdict(list)
    composition_provenance = defaultdict(list)

    def check_description(slug, text, key, pointer):
        if by_slug[slug].get("description_raw_ru") != text:
            evidence_mismatches.append({"slug": slug, "field": "description_raw_ru", "evidence": ref(evidence_paths[key], pointer)})
        description_provenance[slug].append(ref(evidence_paths[key], pointer))

    for index, item in enumerate(evidence["desc_audit"]["items"]):
        check_description(item["slug"], item["raw_description"], "desc_audit", f"/items/{index}/raw_description")
    for index, item in enumerate(evidence["desc_b3"]["captured_original_descriptions"]):
        check_description(item["slug"], item["source_text_ru"], "desc_b3", f"/captured_original_descriptions/{index}/source_text_ru")
    for index, item in enumerate(evidence["desc_b4"]["description_updates"]):
        check_description(item["slug"], item["raw"], "desc_b4", f"/description_updates/{index}/raw")
    b5 = evidence["desc_b5"]
    # BATCH5 says the exact indexed Merci paragraph matched text already stored for another owner SKU,
    # not that the Merci card already had a description in main.
    batch5_preexisting_text_match_slugs = sorted(slug for slug, item in old_by_slug.items()
                                                 if item.get("description_raw_ru") == by_slug[b5["slug"]].get("description_raw_ru"))
    if not batch5_preexisting_text_match_slugs:
        evidence_mismatches.append({"slug": b5["slug"], "field": "description_raw_ru", "reason": "BATCH5 claims equality with preexisting owner text, but no exact preexisting paragraph was found"})
    description_provenance[b5["slug"]].append(ref(evidence_paths["desc_b5"], "/description_verification"))
    b7 = evidence["desc_b7"]
    check_description(b7["slug"], b7["source_description_raw_ru"], "desc_b7", "/source_description_raw_ru")

    for index, item in enumerate(evidence["desc_b4"]["dimension_updates"]):
        value = {"width": item["width"], "height": item["height"]}
        if by_slug[item["slug"]].get("dimensions_cm") != value:
            evidence_mismatches.append({"slug": item["slug"], "field": "dimensions_cm", "evidence": ref(evidence_paths["desc_b4"], f"/dimension_updates/{index}")})
        dimension_provenance[item["slug"]].append(ref(evidence_paths["desc_b4"], f"/dimension_updates/{index}"))
    for index, item in enumerate(evidence["dim_five"]["five_recovered_dimension_pairs"]):
        value = {"width": item["width_cm"], "height": item["height_cm"]}
        if by_slug[item["slug"]].get("dimensions_cm") != value:
            evidence_mismatches.append({"slug": item["slug"], "field": "dimensions_cm", "evidence": ref(evidence_paths["dim_five"], f"/five_recovered_dimension_pairs/{index}")})
        dimension_provenance[item["slug"]].append(ref(evidence_paths["dim_five"], f"/five_recovered_dimension_pairs/{index}"))
    if by_slug[b7["slug"]].get("dimensions_cm") != b7["source_dimensions_cm"]:
        evidence_mismatches.append({"slug": b7["slug"], "field": "dimensions_cm", "evidence": ref(evidence_paths["desc_b7"], "/source_dimensions_cm")})
    dimension_provenance[b7["slug"]].append(ref(evidence_paths["desc_b7"], "/source_dimensions_cm"))

    saved_observation_count = 0
    historical_dimension_gaps_later_filled = []
    for key in ("obs_b1", "obs_b2"):
        for index, item in enumerate(evidence[key]["items"]):
            slug = item["slug"]
            saved_observation_count += 1
            if item.get("composition_items") != by_slug[slug].get("composition_items"):
                evidence_mismatches.append({"slug": slug, "field": "composition_items", "evidence": ref(evidence_paths[key], f"/items/{index}/composition_items")})
            older_dims = item.get("dimensions_cm")
            current_dims = by_slug[slug].get("dimensions_cm")
            if older_dims is None and valid_dimensions(current_dims) and slug in dimension_provenance:
                historical_dimension_gaps_later_filled.append({"slug": slug, "older_observation": ref(evidence_paths[key], f"/items/{index}/dimensions_cm"),
                                                               "later_evidence": dimension_provenance[slug]})
            elif older_dims != current_dims:
                evidence_mismatches.append({"slug": slug, "field": "dimensions_cm", "evidence": ref(evidence_paths[key], f"/items/{index}/dimensions_cm")})
            composition_provenance[slug].append(ref(evidence_paths[key], f"/items/{index}/composition_items"))
            if older_dims is not None:
                dimension_provenance[slug].append(ref(evidence_paths[key], f"/items/{index}/dimensions_cm"))
    parsed_b5_comp = parse_composition_raw(" ".join(b5["source_comp_index"]))
    if normalized_composition(parsed_b5_comp or []) != normalized_composition(by_slug[b5["slug"]]["composition_items"]):
        evidence_mismatches.append({"slug": b5["slug"], "field": "composition_items", "evidence": ref(evidence_paths["desc_b5"], "/source_comp_index")})
    composition_provenance[b5["slug"]].append(ref(evidence_paths["desc_b5"], "/source_comp_index"))
    assert not evidence_mismatches, evidence_mismatches

    present_descriptions = [p["slug"] for p in products if valid_description(p)]
    for slug in present_descriptions:
        observation = by_slug[slug].get("latest_source_observation") or {}
        if observation.get("raw_description_ru") == by_slug[slug]["description_raw_ru"]:
            description_provenance[slug].append({"file": "catalog/public-snapshot.json", "json_pointer": f"/products/{next(i for i,p in enumerate(products) if p['slug']==slug)}/latest_source_observation/raw_description_ru"})
    assert set(description_provenance) == set(present_descriptions)
    valid_dim_slugs = {p["slug"] for p in products if valid_dimensions(p.get("dimensions_cm"))}
    for slug in valid_dim_slugs:
        observation = by_slug[slug].get("latest_source_observation") or {}
        if observation.get("dimensions_cm") == by_slug[slug]["dimensions_cm"]:
            dimension_provenance[slug].append({"file": "catalog/public-snapshot.json", "json_pointer": f"/products/{next(i for i,p in enumerate(products) if p['slug']==slug)}/latest_source_observation/dimensions_cm"})
    inherited_dimension_slugs = []
    for slug in sorted(valid_dim_slugs - set(dimension_provenance)):
        assert by_slug[slug]["dimensions_cm"] == old_by_slug[slug].get("dimensions_cm")
        index = next(i for i, p in enumerate(products) if p["slug"] == slug)
        dimension_provenance[slug].append({"file": "catalog/public-snapshot.json", "json_pointer": f"/products/{index}/dimensions_cm",
                                           "basis": "UNCHANGED_FROM_MAIN_BASELINE_NOT_NEW_LIVE_VERIFICATION", "baseline_sha": MAIN_SHA})
        inherited_dimension_slugs.append(slug)
    assert set(dimension_provenance) == valid_dim_slugs
    inherited_composition_slugs = []
    for slug in sorted(p["slug"] for p in products if valid_composition(p.get("composition_items"))):
        if slug not in composition_provenance:
            assert by_slug[slug]["composition_items"] == old_by_slug[slug].get("composition_items")
            index = next(i for i, p in enumerate(products) if p["slug"] == slug)
            composition_provenance[slug].append({"file": "catalog/public-snapshot.json", "json_pointer": f"/products/{index}/composition_items",
                                                 "basis": "UNCHANGED_FROM_MAIN_BASELINE_NOT_NEW_LIVE_VERIFICATION", "baseline_sha": MAIN_SHA})
            inherited_composition_slugs.append(slug)

    # Historical/indexed differences: preserve both values, do not silently choose a winner.
    b6_products = evidence["obs_b6"]["products"]
    indexed_price_differences, indexed_new_prices, indexed_status_differences = [], [], []
    composition_conflict = None
    for item in b6_products:
        slug = item["slug"]
        indexed_price = item.get("indexed_price_rub")
        old_price = by_slug[slug].get("price_observed_rub")
        if type(indexed_price) in (int, float) and type(old_price) in (int, float) and indexed_price != old_price:
            indexed_price_differences.append({"slug": slug, "legacy_top_level_rub": old_price,
                                              "indexed_rub": indexed_price, "source_url": item["source_url"],
                                              "evidence": ref(evidence_paths["obs_b6"], "/products")})
        if old_price is None and type(indexed_price) in (int, float):
            indexed_new_prices.append({"slug": slug, "indexed_rub": indexed_price, "source_url": item["source_url"]})
        if item.get("indexed_status") == "READY_TO_DELIVER_ON_INDEXED_VIEW" and by_slug[slug].get("availability_observed") == "sold_out":
            indexed_status_differences.append({"slug": slug, "legacy_availability": "sold_out",
                                               "indexed_status": item["indexed_status"], "source_url": item["source_url"]})
        difference = item.get("indexed_composition_difference")
        if difference:
            actual = next((x for x in by_slug[slug]["composition_items"] if x["component"] == difference["component"]), None)
            assert actual and actual["quantity"] == difference["recorded_github_quantity"]
            composition_conflict = {"slug": slug, "component": difference["component"],
                                    "stored_quantity": actual["quantity"], "indexed_source_quantity": difference["source_quantity"],
                                    "unit": difference["unit"], "source_url": item["source_url"],
                                    "evidence": [ref(evidence_paths["obs_b6"], "/products"), ref(evidence_paths["desc_b4"], "/detected_conflict")]}
    assert composition_conflict is not None
    if by_slug[b7["slug"]].get("price_observed_rub") != b7["source_price_indexed_rub"]:
        indexed_price_differences.append({"slug": b7["slug"], "legacy_top_level_rub": by_slug[b7["slug"]].get("price_observed_rub"),
                                          "indexed_rub": b7["source_price_indexed_rub"], "source_url": b7["source_url"],
                                          "evidence": ref(evidence_paths["desc_b7"], "/source_price_indexed_rub")})

    # Discovery: four historically seller-verified metadata-only items, 55 indexed leads, two quarantined.
    pending_path = "catalog/discovery/new-verified-seller-candidates-20261031-4.json"
    pending_data = load_json(root / pending_path)
    pending = pending_data["products"]
    assert len(pending) == pending_data["record_count"] == 4
    assert pending_data["seller_canonical_url"] == SELLER_URL and pending_data["photos_saved"] == 0
    pending_rows = []
    for index, item in enumerate(pending):
        slug = item["slug"]
        assert slug not in by_slug and canonical_url(item["source_url"], "product", slug)
        assert item["seller_identity_verified"] is True and all(item.get(flag) is False for flag in SALE_FLAGS)
        assert valid_composition(item["composition_observed"]) and valid_dimensions(item["dimensions_cm"])
        assert item["source_description_raw_ru"] is None and item["original_urls_verified"] == 0
        pending_rows.append({"slug": slug, "source_url": item["source_url"], "source_category": item["source_category"],
                             "prior_record_status": "EXACT_SELLER_CONFIRMED_METADATA_ONLY",
                             "prior_seller_verification_date": pending_data["observed_at_date"],
                             "canonical_seller_reverified_this_run": False,
                             "observed_gallery_thumbnail_count": item["observed_gallery_thumbnail_count"],
                             "original_photos_previously_saved": 0, "original_photos_added_this_run": 0,
                             "raw_description_available": False, "quantitative_composition_available_in_prior_evidence": True,
                             "dimensions_available_in_prior_evidence": True,
                             "evidence": ref(pending_path, f"/products/{index}"),
                             "sale_flags": {flag: False for flag in SALE_FLAGS}})

    lead_paths = [
        "catalog/discovery/FLOWWOW_INDEXED_21_NEW_POSSIBLE_PRODUCTS_2026-10-31.json",
        "catalog/discovery/FLOWWOW_INDEXED_6_MORE_POSSIBLE_PRODUCTS_2026-10-31.json",
        "catalog/discovery/FLOWWOW_INDEXED_25_MORE_POSSIBLE_PRODUCTS_2026-10-31.json",
        "catalog/discovery/FLOWWOW_INDEXED_3_MORE_WITH_SOURCE_DETAILS_2026-10-31.json",
    ]
    leads, lead_slugs = [], set()
    reserved = set(by_slug) | {x["slug"] for x in pending} | {EXCLUDED_SKU}
    for path in lead_paths:
        data = load_json(root / path)
        for index, item in enumerate(data["items"]):
            slug = item["slug"]
            assert slug not in reserved and slug not in lead_slugs
            assert canonical_url(item["source_url"], "product", slug)
            assert item.get("displayed_seller", item.get("seller_display_name")) == "Ароматный букет"
            assert all(item.get(flag, False) is False for flag in SALE_FLAGS)
            assert item.get("do_not_add_to_retail", False) is True or item.get("may_order") is False
            prior_verified = item.get("exact_seller_identity_verified", item.get("canonical_seller_verified", item.get("canonical_shop_link_verified")))
            assert prior_verified is False
            lead_slugs.add(slug)
            leads.append({
                "slug": slug, "name_ru": item["name_ru"], "source_url": item["source_url"],
                "source_category": item.get("source_category"),
                "displayed_seller": item.get("displayed_seller", item.get("seller_display_name")),
                "source_file": path, "source_json_pointer": f"/items/{index}", "prior_source_ref": item["source_ref"],
                "prior_evidence_type": "PUBLIC_SEARCH_INDEX_SNAPSHOT",
                "prior_canonical_seller_verified": False,
                "independent_status": "UNVERIFIED", "live_page_opened_this_run": False,
                "exact_seller_link_clicked_this_run": False, "show_more_clicked_this_run": False,
                "full_gallery_verified": False, "photos_added_this_run": 0,
                "indexed_composition_present": bool(item.get("composition_items_indexed")),
                "indexed_description_present": bool(item.get("description_raw_ru_indexed")),
                "indexed_dimensions_present": valid_dimensions(item.get("dimensions_cm_indexed")),
                "promoted_to_confirmed_catalog": False, "sale_flags": {flag: False for flag in SALE_FLAGS},
            })
    assert len(leads) == len(lead_slugs) == 55

    quarantine_path = "catalog/discovery/QUARANTINED_INCOMPLETE_PUBLIC_CANDIDATES_2026-10-31.json"
    quarantine_data = load_json(root / quarantine_path)
    quarantine = quarantine_data["suspected_unfinished_candidates"]
    assert len(quarantine) == 2 and quarantine_data["confirmed_abandoned_count"] == 0
    quarantine_rows = []
    for index, item in enumerate(quarantine):
        assert item["slug"] not in reserved and item["slug"] not in lead_slugs
        assert item["exact_canonical_shop_link_verified"] is False
        if "definite_abandoned" in item:
            assert item["definite_abandoned"] is False
        assert item["not_equivalent_to_confirmed_abandoned"] is True and item["retail_include"] is False
        quarantine_rows.append({"slug": item["slug"], "source_url": item["url"], "status": "QUARANTINED_UNVERIFIED",
                                "confirmed_abandoned": False, "canonical_seller_verified_this_run": False,
                                "evidence": ref(quarantine_path, f"/suspected_unfinished_candidates/{index}"),
                                "sale_flags": {flag: False for flag in SALE_FLAGS}})

    review_path = "catalog/review/POTENTIALLY_UNFINISHED_PRODUCTS_2026-10-31.json"
    review = load_json(root / review_path)
    assert review["confirmed_blank_count"] == 0 and review["current_verified_abandoned"] == []
    assert {x["slug"] for x in review["current_review_pending"]} == set(PRIORITY_SEVEN)
    assert set(missing_composition) == set(PRIORITY_SEVEN)
    assert all(item["definite_abandoned"] is False for item in review["current_review_pending"])

    categories = sorted({p["source_category"] for p in products} | {x["source_category"] for x in leads} | {x["source_category"] for x in pending_rows})
    category_rows = [{"category_name": name, "category_url": None, "live_fully_traversed": False,
                      "show_more_clicks": 0, "end_of_list_proven": False,
                      "baseline_sku_count_offline": sum(p["source_category"] == name for p in products),
                      "indexed_candidate_count_offline": sum(x["source_category"] == name for x in leads),
                      "prior_seller_verified_pending_count": sum(x["source_category"] == name for x in pending_rows)}
                     for name in categories]

    gap_union = sorted(set(missing_composition) | set(missing_description) | set(missing_dimensions))
    assert len(missing_composition) == 7 and len(missing_description) == 30 and len(missing_dimensions) == 12
    assert len(gap_union) == 30
    assert len(invalid_dimension_objects) == 1 and invalid_dimension_objects[0]["slug"] == "avtorskiy-buket-67899"

    add_finding("MISSING_QUANTITATIVE_COMPOSITION", "HIGH", "Семь исходных количественных составов не сохранены",
                missing_composition, {"count": 7, "current_value": []},
                "Получить точный состав с исходной страницы или разрешённого экспорта; не выводить количества из названия или фото.",
                [ref(review_path, "/current_review_pending")])
    add_finding("MISSING_ORIGINAL_DESCRIPTION", "HIGH", "Тридцать исходных описаний не сохранены",
                missing_description, {"count": 30, "current_status": "NOT_CAPTURED"},
                "Не считать индексное отсутствие текста доказательством пустого поля; нужен точный источник.")
    add_finding("MISSING_DIMENSIONS", "HIGH", "Двенадцать пар размеров недоступны или непригодны",
                missing_dimensions, {"count": 12, "null_objects": 11, "objects_with_null_width_and_height": 1,
                                     "valid_pairs": 54, "non_null_dimension_objects": 55},
                "Считать валидными только положительные числовые width/height; восстановить 12 пар из точного источника.")
    add_finding("AMBIGUOUS_MISSING_DIMENSION_REPRESENTATION", "MEDIUM", "Пропуск размеров закодирован двумя разными способами",
                ["avtorskiy-buket-67899"], {"current_value": {"width": None, "height": None},
                                          "other_missing_products_use": None,
                                          "proposed_normalization_not_applied": None},
                "При будущем согласованном изменении схемы нормализовать непригодную пару к null; в этом аудите исходник не изменён.")
    add_finding("COMPOSITION_SOURCE_CONFLICT", "HIGH", "Количество пионов: 35 в каталоге против 23 в индексированном источнике",
                [composition_conflict["slug"]], composition_conflict,
                "Не перезаписывать автоматически; подтвердить актуальный рецепт у продавца/в живой карточке и сохранить период действия.")
    title_slug = "buket-hrizantem-mattiola-romas"
    add_finding("TITLE_COMPOSITION_DISCREPANCY", "MEDIUM", "Маттиола есть в названии, но отсутствует в сохранённом составе",
                [title_slug], {"title": by_slug[title_slug]["name_ru"],
                               "stored_components": [x["component"] for x in by_slug[title_slug]["composition_items"]],
                               "indexed_source_also_omits_component": True},
                "Проверить название и рецепт у источника; не добавлять компонент и количество по одному названию.",
                [ref(evidence_paths["obs_b6"], "/products")])
    add_finding("EXACT_DUPLICATE_JPEG_WITHIN_GALLERIES", "MEDIUM", "Повторяющиеся байты JPEG внутри исходных галерей",
                sorted({x["slug"] for g in duplicate_hash_groups for x in g["occurrences"]}),
                {"duplicate_hash_groups": len(duplicate_hash_groups), "redundant_occurrences": 435-len(hash_locations),
                 "groups": duplicate_hash_groups, "distinct_source_urls": True,
                 "interpretation": "Exact byte duplicates are confirmed; whether the live seller gallery intentionally repeats them is not verified."},
                "Сверить порядок и состав живой галереи; не удалять исходные кадры только по факту совпадения SHA256.")
    add_finding("LEGACY_AND_SAVED_BUY_BLOCK_PRICE_DIFFERENCES", "MEDIUM", "Сохранённые исторические цены отличаются от более поздних записей наблюдения",
                sorted({x["slug"] for x in numeric_price_differences+newly_visible_prices}),
                {"numeric_to_numeric_differences": numeric_price_differences, "legacy_null_new_numeric": newly_visible_prices,
                 "current_live_price_verified": False},
                "Хранить цену как датированное наблюдение; не объявлять текущую цену и не менять коммерческие поля без живой проверки.")
    add_finding("INDEXED_PRICE_DIFFERENCES_NOT_CURRENT_PRICE_PROOF", "MEDIUM", "Индексные цены отличаются от сохранённых исторических цен",
                sorted({x["slug"] for x in indexed_price_differences+indexed_new_prices}),
                {"numeric_differences": indexed_price_differences, "legacy_null_indexed_numeric": indexed_new_prices,
                 "index_may_be_stale": True},
                "Не использовать индексную цену как актуальную без проверки страницы, даты, города и варианта товара.")
    add_finding("INDEXED_AVAILABILITY_DIFFERENCE", "MEDIUM", "Индексный статус ready-to-deliver отличается от сохранённого sold_out",
                [x["slug"] for x in indexed_status_differences], {"observations": indexed_status_differences},
                "Не трактовать ни один исторический статус как текущий остаток и не включать продажи.",
                [ref(evidence_paths["obs_b6"], "/products")])
    add_finding("FOUR_PRIOR_VERIFIED_GALLERIES_PENDING", "HIGH", "Четыре ранее подтверждённых продавца товара всё ещё без оригинальных галерей",
                [x["slug"] for x in pending_rows], {"count": 4, "observed_thumbnails_total": sum(x["observed_gallery_thumbnail_count"] for x in pending_rows),
                                                   "original_photos_added": 0, "raw_descriptions_available": 0},
                "Подтвердить продавца и полную галерею в разрешённой сессии; сохранить только отсутствующие оригиналы с SHA256.",
                [ref(pending_path, "/products")])
    add_finding("FIFTY_FIVE_INDEXED_LEADS_UNVERIFIED", "HIGH", "55 индексных кандидатов не подтверждены точным переходом к продавцу",
                sorted(lead_slugs), {"count": 55, "display_name_matches": 55, "independent_canonical_seller_confirmations": 0},
                "Оставить UNVERIFIED; отображаемое имя магазина не является доказательством canonical seller.")
    add_finding("TWO_QUARANTINED_NOT_ABANDONED", "MEDIUM", "Две карантинные ссылки не доказаны заброшенными черновиками",
                [x["slug"] for x in quarantine_rows], {"count": 2, "confirmed_abandoned": 0},
                "Сохранить карантин до проверки точного продавца и авторитетного состояния записи.", [ref(quarantine_path)])
    add_finding("SELLER_IDENTITY_INHERITED_NOT_LIVE_REVERIFIED", "HIGH", "Принадлежность всех 66 базовых SKU продавцу унаследована из прежней проверки",
                sorted(by_slug), {"count": 66, "stored_seller_evidence": "PREVIOUSLY_VERIFIED_IN_PRIVATE_CATALOG",
                                  "live_canonical_seller_reverified_this_run": 0},
                "Не выдавать офлайн-совпадение seller_url за новый переход «Перейти в магазин».")
    add_finding("LIVE_SOURCE_AND_GALLERY_ORDER_NOT_VERIFIED", "HIGH", "Живые страницы, полнота галерей и порядок кадров не сверены",
                sorted(by_slug), {"baseline_cards_checked_offline": 66, "live_product_pages_opened": 0,
                                  "categories_fully_traversed": 0, "show_more_clicks": 0},
                "Для COMPLETE нужен разрешённый интерактивный просмотр всех категорий и карточек; данный результат только PARTIAL.")
    root_readme = (root / "README.md").read_text(encoding="utf-8")
    if "26/66 подлинных исходных описаний" in root_readme and "46/66 размеров" in root_readme:
        add_finding("ROOT_README_DESCRIBES_OLDER_MAIN_BASELINE", "LOW", "Корневой README в рабочей ветке начинается с показателей старого main",
                    [], {"file": "README.md", "advertised_descriptions": 26, "advertised_dimensions": 46,
                         "actual_source_branch_descriptions": 36, "actual_source_branch_valid_dimensions": 54},
                    "Считать актуальными snapshot и верхний блок catalog/INDEX.md; при отдельном согласовании обновить баннер README.")

    random_generator = random.Random(SOURCE_SHA)
    sample_slugs = sorted(random_generator.sample(sorted(by_slug), 3))
    sample_rows = []
    for slug in sample_slugs:
        image = by_slug[slug]["gallery"][0]
        binary = (root / image["path"]).read_bytes()
        with Image.open(io.BytesIO(binary)) as decoded:
            size = [decoded.width, decoded.height]
        sample_rows.append({"slug": slug, "source_url": by_slug[slug]["flowwow_url"], "photo_path": image["path"],
                            "github_blob_url": f"https://github.com/tophqru/aromatny-flowwow-public-audit/blob/{SOURCE_SHA}/{image['path']}",
                            "git_blob_oid": git_media_oids[image["path"]], "sha256": sha256_bytes(binary),
                            "manifest_sha256": image["sha256"], "bytes": len(binary), "jpeg_width_height": size,
                            "local_equals_manifest": sha256_bytes(binary) == image["sha256"],
                            "local_equals_source_git_blob": git_blob_sha1(binary) == git_media_oids[image["path"]]})

    base_meta = {"schema_version": "1.0", "generated_at_utc": started,
                 "source_repository": "https://github.com/tophqru/aromatny-flowwow-public-audit",
                 "source_branch": SOURCE_BRANCH, "source_sha": SOURCE_SHA, "working_branch": current_branch,
                 "working_head_at_audit": current_sha, "audit_method": "OFFLINE_PUBLIC_GITHUB_FILES",
                 "live_flowwow_verification": "NOT_PERFORMED", "interactive_browser_available": False}
    counts = {"baseline_sku": 66, "baseline_sku_checked_offline": 66, "live_flowwow_product_pages_opened": 0,
              "existing_jpeg_checked": 435, "existing_jpeg_bytes": total_bytes,
              "valid_compositions": 59, "valid_original_descriptions": 36, "valid_dimension_pairs": 54,
              "missing_compositions": 7, "missing_descriptions": 30, "missing_or_unusable_dimension_pairs": 12,
              "unique_skus_with_any_field_gap": len(gap_union), "total_missing_field_values": 49,
              "newly_recovered_fields": 0, "new_photos": 0, "new_confirmed_skus": 0,
              "indexed_candidates_reviewed": 55, "indexed_candidates_independently_seller_confirmed": 0,
              "indexed_candidates_other_seller_confirmed": 0, "indexed_candidates_unverified": 55,
              "prior_seller_verified_metadata_only": 4, "prior_verified_galleries_completed": 0,
              "quarantined_candidates": 2, "confirmed_abandoned_drafts": 0,
              "baseline_categories_inventoried_offline": len(categories), "categories_fully_traversed_live": 0,
              "show_more_clicks": 0, "exact_seller_link_clicks_this_run": 0,
              "sale_permissions_enabled": 0, "excluded_sku_reintroduced": False}
    baseline = {**base_meta, "summary": counts,
                "coverage_counts": {"composition": 59, "description": 36, "dimensions": 54},
                "source_gaps": {"composition": missing_composition, "description": missing_description,
                                "dimensions": missing_dimensions, "invalid_dimension_objects": invalid_dimension_objects,
                                "unique_slugs": gap_union},
                "products": product_rows, "findings": findings,
                "checks": {"duplicate_sku_count": 0, "duplicate_canonical_product_url_count": 0,
                           "stored_other_seller_urls": 0, "card_snapshot_mismatches": 0,
                           "catalog_json_files_strictly_parsed": len(json_files), "catalog_json_parse_errors": json_errors,
                           "catalog_markdown_files_checked": len(markdown_files), "broken_catalog_markdown_links": broken_links,
                           "card_readme_gallery_mismatches": readme_errors,
                           "card_readme_without_explicit_seller_link_informational": readme_without_explicit_seller_link,
                           "saved_raw_composition_mismatches": composition_raw_mismatches,
                           "saved_observation_dimension_mismatches": dimension_observation_mismatches,
                           "saved_observation_description_mismatches": description_observation_mismatches,
                           "dedicated_evidence_field_mismatches": evidence_mismatches,
                           "batch5_preexisting_exact_text_match_slugs": batch5_preexisting_text_match_slugs,
                           "historical_observation_dimension_gaps_later_filled": historical_dimension_gaps_later_filled,
                           "duplicate_component_names_within_sku": duplicate_components,
                           "description_provenance_covered": len(description_provenance),
                           "dimension_provenance_covered": len(dimension_provenance),
                           "saved_public_composition_observations_matched": saved_observation_count,
                           "dimension_values_inherited_unchanged_from_main": inherited_dimension_slugs,
                           "composition_values_inherited_unchanged_from_main": inherited_composition_slugs,
                           "duplicate_descriptions_are_source_generic_not_auto_error": True},
                "field_provenance_map": {"description": dict(description_provenance), "dimensions": dict(dimension_provenance),
                                         "composition_dedicated_observations": dict(composition_provenance)},
                "interpretation_limits": ["Public GitHub consistency is not a new live Flowwow observation.",
                                          "Existing seller verification is inherited, not re-performed.",
                                          "A generic description repeated by the seller is not automatically a wrong description.",
                                          "Exact duplicate image bytes are not proof of a wrong seller or an incorrect live gallery."]}
    media_audit = {**base_meta, "summary": {"manifest_photos": 435, "git_tree_photos": len(git_media_oids),
                                           "physical_photos": len(physical_media), "bytes": total_bytes,
                                           "unique_sha256": len(hash_locations), "unique_source_urls": len(url_locations),
                                           "sha256_mismatches": 0, "byte_size_mismatches": 0, "git_blob_mismatches": 0,
                                           "missing_files": 0, "extra_unmanifested_files": 0, "jpeg_decode_failures": 0,
                                           "jpeg_sizes": dict(jpeg_sizes), "jpeg_modes": dict(jpeg_modes),
                                           "exif_present_count": exif_count, "icc_profile_count": icc_count,
                                           "jpeg_comment_count": comment_count, "duplicate_hash_groups": len(duplicate_hash_groups),
                                           "cross_sku_duplicate_hash_groups": len(cross_sku_hash_groups),
                                           "redundant_duplicate_occurrences": 435-len(hash_locations),
                                           "ordered_media_manifest_sha256": aggregate.hexdigest(),
                                           "image_bytes_downloaded_from_flowwow": 0},
                   "remote_github_tree_check": remote_tree_check, "random_three_sku_checkpoint": sample_rows,
                   "sample_method": "random.Random(seed=source_sha).sample(sorted(slugs), 3); first gallery image per sampled SKU",
                   "duplicate_hash_groups": duplicate_hash_groups, "duplicate_source_url_groups": duplicate_url_groups,
                   "galleries": media_rows,
                   "not_verified": ["Live gallery frame count/order", "Visual subject-to-SKU matching against the current source",
                                    "Whether repeated frames are intentional seller content", "Completeness of hidden/archived inventory"]}
    discovery = {**base_meta, "canonical_seller_url": SELLER_URL, "summary": counts,
                 "categories": category_rows, "prior_seller_verified_metadata_only": pending_rows,
                 "indexed_candidates": leads, "quarantine": quarantine_rows,
                 "confirmed_new_skus": [], "owner_excluded_sku_reintroduced": False,
                 "status_definitions": {"EXACT_SELLER_CONFIRMED": "Exact canonical seller link verified by a real permitted source visit; none newly established in this run.",
                                        "OTHER_SELLER": "Exact source visit proves a different canonical seller; none established in this run.",
                                        "UNVERIFIED": "Only indexed/display-name evidence; not promoted.",
                                        "TEMPORARILY_UNAVAILABLE": "Source product exists but cannot currently be ordered; not an abandoned draft.",
                                        "INACCESSIBLE": "Page could not be read; existence/completeness not inferred.",
                                        "ABANDONED_DRAFT": "Authoritative seller/source state proves an unfinished abandoned record; none confirmed."}}
    recoveries = {**base_meta, "recoveries": [], "newly_recovered_field_count": 0,
                  "reason_ru": "Все проверенные точные тексты и размеры из доступных evidence уже присутствуют в source. Новых достоверных значений без живой сверки не получено. Конфликт 23/35 пионов не разрешён автоматически.",
                  "existing_fields_consistency_checked": {"descriptions": 36, "dimension_pairs": 54,
                                                          "dedicated_saved_composition_observations": saved_observation_count},
                  "policy": "No invented descriptions, compositions, dimensions, prices, stock, or permissions; SOURCE_NOT_VISIBLE is not SOURCE_CONFIRMED_EMPTY."}
    gallery_delta = {**base_meta, "photos": [], "new_photo_count": 0, "new_media_bytes": 0,
                     "reason_ru": "Интерактивного браузера нет; новые оригинальные URL и байты не собирались. Существующие 435 JPEG не скачивались и не переупаковывались.",
                     "deduplication_baseline": {"existing_source_urls": len(url_locations), "existing_sha256": len(hash_locations),
                                                "ordered_media_manifest_sha256": aggregate.hexdigest()}}
    new_skus = {**base_meta, "new_skus": [], "new_sku_count": 0,
                "reason_ru": "Ни один из 55 кандидатов не подтверждён точным переходом к canonical seller в этом запуске; четыре прежних metadata-only товара не стали новыми находками этого запуска.",
                "excluded_sku_reintroduced": False, "sale_flags": {flag: False for flag in SALE_FLAGS}}
    blockers = {**base_meta, "status": "PARTIAL", "blockers": [
        {"id": "B001", "type": "INTERACTIVE_BROWSER_UNAVAILABLE", "scope": "Live Flowwow storefront, categories, product pages and seller links",
         "effect": "No live page opens, scrolling, Show more clicks, canonical seller clicks, current price/stock or live gallery checks.",
         "attempted_live_requests_this_run": 0, "resolution": "One permitted interactive browser session, sequential navigation, no protection bypass."},
        {"id": "B002", "type": "OFFICIAL_GITHUB_CONNECTOR_UNSUPPORTED", "scope": "Arena GitHub Connector",
         "effect": "Connector cannot be used; preconfigured git/gh access is checked separately and used for public delivery if available.",
         "resolution": "Use the already authenticated git/gh environment; no token requested in chat."},
        {"id": "B003", "type": "SOURCE_FIELD_GAPS", "scope": "Baseline 66 SKU",
         "missing_compositions": missing_composition, "missing_descriptions": missing_description,
         "missing_or_unusable_dimensions": missing_dimensions, "total_missing_field_values": 49,
         "resolution": "Exact source page or permitted seller export; do not infer from titles/photos."},
        {"id": "B004", "type": "UNRESOLVED_COMPOSITION_CONFLICT", "scope": composition_conflict["slug"],
         "stored_quantity": 35, "indexed_quantity": 23, "resolution": "Seller/live-source confirmation of current recipe and observation period."},
        {"id": "B005", "type": "UNVERIFIED_CANDIDATES_AND_PENDING_GALLERIES", "scope": "55 indexed leads + 4 prior metadata-only products + 2 quarantine links",
         "resolution": "Exact seller link, complete original gallery and authoritative state before any promotion."},
        {"id": "B006", "type": "PREVIOUS_ZIP_NOT_PRESENT", "scope": "Current workspace",
         "observed_zip_files_before_audit": 0, "resolution": "No previous ZIP content was available to compare; no prior result claimed as verified."},
    ], "historical_source_access_note": "Existing repository evidence records HTTP 403 for three exact Flowwow URLs. Those are prior observations, not requests made in this run.",
        "not_confirmed_abandoned": sorted(PRIORITY_SEVEN + [x["slug"] for x in quarantine_rows])}
    source_integrity = {**base_meta, "catalog_git_tree": catalog_tree, "media_git_tree": media_tree,
                        "snapshot_sha256": snapshot_hash, "index_sha256": sha256_file(root / "catalog/INDEX.md"),
                        "task_sha256": sha256_file(root / "arena/ARENA_PUBLIC_CATALOG_INDEPENDENT_TASK_2026-10-31.md"),
                        "protected_paths_changed_vs_source": [], "protected_worktree_changes": [],
                        "untracked_protected_files": [], "remote_github_media_tree_check": remote_tree_check,
                        "previous_zip_files_found": 0, "existing_image_bytes_downloaded": 0}
    checks = {**base_meta, "result": "PASS_OFFLINE_AUDIT_WITH_FINDINGS", "catalog_completion": "INCOMPLETE",
              "overall_task_status": "PARTIAL", "counts": counts,
              "finding_count": len(findings), "findings_by_severity": dict(Counter(f["severity"] for f in findings)),
              "tests": {"strict_catalog_json": "PASS", "snapshot_card_equality": "PASS",
                        "catalog_markdown_links": "PASS", "jpeg_sha256_bytes_decode_git_blob": "PASS",
                        "remote_github_tree_blob_oids": "PASS", "saved_evidence_field_consistency": "PASS",
                        "candidate_deduplication_and_nonpromotion": "PASS", "sale_permissions_remain_false": "PASS",
                        "excluded_sku_absent_from_products_and_candidates": "PASS",
                        "live_flowwow_pages_categories_galleries_prices_stock": "NOT_PERFORMED",
                        "visual_photo_to_live_sku_matching": "NOT_PERFORMED"},
              "finished_at_utc": utcnow()}

    outputs = {"baseline-audit.json": baseline, "media-audit.json": media_audit,
               "seller-discovery.json": discovery, "verified-field-recoveries.json": recoveries,
               "gallery-delta.json": gallery_delta, "new-skus.json": new_skus,
               "blockers.json": blockers, "source-integrity.json": source_integrity, "checks.json": checks}
    for name, value in outputs.items():
        write_json(out / name, value, args.no_write)
    print(json.dumps({"result": checks["result"], "source_sha": SOURCE_SHA, "working_head": current_sha,
                      "counts": counts, "findings": len(findings), "no_write": args.no_write}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
