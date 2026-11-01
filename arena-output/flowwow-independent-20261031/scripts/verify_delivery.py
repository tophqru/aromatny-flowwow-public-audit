#!/usr/bin/env python3
"""Validate the isolated audit delta, privacy/secret hygiene, and SHA256SUMS.

Read-only with respect to the source catalog. Writes only privacy-security-audit.json
inside the output directory. Does not contact Flowwow or download images.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

SOURCE_SHA = "f1e717fda918ce4ca8ccba9d4e8dc5ab7ab8f048"
EXCLUDED = "kompoziciya-v-shlyapnoy-k-4183"
SALE_FLAGS = {"owner_approved", "may_order", "may_show_publicly"}
TEXT_SUFFIXES = {".md", ".json", ".jsonl", ".py", ".yml", ".yaml", ".txt", ".log", ".csv"}
SECRET_PATTERNS = {
    "github_classic_token": re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),
    "github_fine_grained_token": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    "github_oauth_token": re.compile(r"\bgho_[A-Za-z0-9]{36}\b"),
    "openai_style_secret_key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "aws_access_key_id": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "private_key_block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "authorization_bearer_header": re.compile(r"(?im)^\s*authorization\s*:\s*bearer\s+\S+"),
    "cookie_header_assignment": re.compile(r"(?im)^\s*(?:set-cookie|cookie)\s*[:=]\s*\S+"),
    "session_cookie_assignment": re.compile(r"\b(?:sessionid|csrftoken|flowwow_session)=[A-Za-z0-9_%.-]{12,}"),
    "email_address": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "ru_phone_number": re.compile(r"(?<!\d)\+7\d{10}(?!\d)"),
}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def sha256(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key, child
            yield from walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_keys(child)


def git(root: Path, *args):
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.repo_root.resolve()
    out = args.output_dir.resolve()
    required = ["README.md", "comparison-report.md", "QA.md", "baseline-audit.json", "media-audit.json",
                "seller-discovery.json", "verified-field-recoveries.json", "gallery-delta.json", "new-skus.json",
                "blockers.json", "source-integrity.json", "checks.json", "access-capabilities.json",
                "new-media/README.md", "scripts/audit_offline.py", "scripts/verify_delivery.py"]
    missing = [name for name in required if not (out / name).is_file()]
    assert not missing, missing

    json_files = sorted(out.rglob("*.json"))
    for path in json_files:
        load(path)
    baseline = load(out / "baseline-audit.json")
    discovery = load(out / "seller-discovery.json")
    checks = load(out / "checks.json")
    recoveries = load(out / "verified-field-recoveries.json")
    gallery = load(out / "gallery-delta.json")
    new_skus = load(out / "new-skus.json")
    assert checks["result"] == "PASS_OFFLINE_AUDIT_WITH_FINDINGS" and checks["overall_task_status"] == "PARTIAL"
    assert baseline["source_sha"] == SOURCE_SHA and baseline["live_flowwow_verification"] == "NOT_PERFORMED"
    products = baseline["products"]
    assert len(products) == len({p["slug"] for p in products}) == 66
    assert all(p["offline_audit_status"] == "CHECKED_PUBLIC_FILES" for p in products)
    assert all(p["canonical_seller_reverified_this_run"] is False for p in products)
    leads = discovery["indexed_candidates"]
    assert len(leads) == len({x["slug"] for x in leads}) == 55
    assert all(x["independent_status"] == "UNVERIFIED" and x["promoted_to_confirmed_catalog"] is False for x in leads)
    assert all(x["live_page_opened_this_run"] is False and x["exact_seller_link_clicked_this_run"] is False for x in leads)
    assert len(discovery["prior_seller_verified_metadata_only"]) == 4 and len(discovery["quarantine"]) == 2
    assert discovery["confirmed_new_skus"] == recoveries["recoveries"] == gallery["photos"] == new_skus["new_skus"] == []
    assert recoveries["newly_recovered_field_count"] == gallery["new_photo_count"] == new_skus["new_sku_count"] == 0
    product_slugs = {p["slug"] for p in products} | {x["slug"] for x in leads} | {x["slug"] for x in discovery["prior_seller_verified_metadata_only"]} | {x["slug"] for x in discovery["quarantine"]}
    assert EXCLUDED not in product_slugs
    images_in_output = [p for p in out.rglob("*") if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif"}]
    assert not images_in_output, "Delta must not repackage source photos; no new photos were collected"

    unsafe_permissions = []
    for path in json_files:
        value = load(path)
        for key, child in walk_keys(value):
            if key in SALE_FLAGS and child is not False:
                unsafe_permissions.append({"file": str(path.relative_to(out)), "key": key})
            if key == "promoted_to_confirmed_catalog" and child is not False:
                unsafe_permissions.append({"file": str(path.relative_to(out)), "key": key})
    assert not unsafe_permissions, unsafe_permissions

    protected_diff = git(root, "diff", "--name-only", SOURCE_SHA, "--", "catalog", "data", "scripts", ".github", "arena")
    worktree_diff = git(root, "diff", "--name-only", "--", "catalog", "data", "scripts", ".github", "arena")
    untracked = [x for x in git(root, "ls-files", "--others", "--exclude-standard").splitlines() if x and not x.startswith("arena-output/")]
    assert not protected_diff and not worktree_diff and not untracked

    # High-confidence secret/PII pattern scan. Match values are never printed or stored.
    report_name = "privacy-security-audit.json"
    scan_files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.parts or ".arena-audit-venv" in path.parts:
            continue
        rel = path.relative_to(root)
        if str(rel) == str((out / report_name).relative_to(root)) or str(rel) == str((out / "SHA256SUMS").relative_to(root)):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            scan_files.append(path)
    matches = []
    for path in scan_files:
        text = path.read_text(encoding="utf-8", errors="replace")
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                matches.append({"file": str(path.relative_to(root)), "pattern": name})
    privacy = {"result": "PASS" if not matches else "FAIL", "scan_scope": "Tracked/workspace text files in the public repository and isolated delta; binary JPEG metadata checked separately by audit_offline.py",
               "text_files_scanned": len(scan_files), "high_confidence_secret_or_pii_pattern_matches": matches,
               "match_values_recorded": False, "jpeg_exif_present_count": 0, "jpeg_comment_count": 0,
               "limitations": ["Pattern scanning is not a formal DLP proof.", "Visual faces/addresses inside product photos were not exhaustively reviewed against a live source.",
                               "No cookies, authentication headers, customer records, or seller-dashboard screenshots were collected in this run."]}
    (out / report_name).write_text(json.dumps(privacy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert not matches, matches

    checksum_file = out / "SHA256SUMS"
    checksum_status = "NOT_PRESENT"
    checksum_errors = []
    if checksum_file.is_file():
        listed = set()
        for line in checksum_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            expected, name = line.split("  ", 1)
            path = out / name
            listed.add(name)
            if not path.is_file() or sha256(path) != expected:
                checksum_errors.append(name)
        expected_files = {str(p.relative_to(out)) for p in out.rglob("*") if p.is_file() and p.name != "SHA256SUMS"}
        if listed != expected_files:
            checksum_errors.append("FILE_SET_MISMATCH")
        assert not checksum_errors, checksum_errors
        checksum_status = "PASS"
    print(json.dumps({"result": "PASS_DELTA_DELIVERY_CHECKS", "output_json_files": len(json_files),
                      "baseline_sku": 66, "indexed_candidates": 55, "new_photos": 0,
                      "privacy_pattern_scan": privacy["result"], "sha256sums": checksum_status,
                      "protected_source_changes": 0, "sale_permissions_enabled": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
