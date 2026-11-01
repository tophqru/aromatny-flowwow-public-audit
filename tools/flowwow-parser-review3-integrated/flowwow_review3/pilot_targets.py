"""Strict three-product pilot allowlist. Does not perform network or browser actions.

This module is intentionally independent of GitHub, Playwright and application state:
Codex may first inspect the exact planned URLs and source snapshot before any browser work.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

SHOP = "https://flowwow.com/shop/lyubov-eto-699e0e4519/"
_ALLOWED_KINDS = ("BASELINE_GAPS", "BASELINE_GAPS", "PENDING_SELLER_VERIFIED_METADATA_ONLY")
_PRODUCT_PATH = re.compile(r"^/flowers/([a-z0-9_-]+)/$")
_SHA = re.compile(r"^[0-9a-f]{40}$")

class PilotGuardError(RuntimeError):
    pass


def _distinct_json_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PilotGuardError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _exact_product_url(url: str) -> str:
    if not isinstance(url, str):
        raise PilotGuardError("Product URL must be a string")
    try:
        parsed = urlsplit(url)
        m = _PRODUCT_PATH.fullmatch(parsed.path)
        if (parsed.scheme != "https" or parsed.netloc != "flowwow.com" or
                parsed.query or parsed.fragment or not m or parsed.geturl() != url):
            raise PilotGuardError("Pilot URL must be an exact canonical HTTPS product URL")
        return m.group(1)
    except ValueError as exc:
        raise PilotGuardError("Invalid pilot URL") from exc


def read_pilot_manifest(path: Path, snapshot: dict, *, expected_public_commit: str,
                        expected_private_commit: str, baseline_bytes: bytes) -> tuple[list[tuple[str, str]], str]:
    """Return ordered exact targets and content hash, or stop before any browser call.

    Validate against a frozen 66-SKU snapshot, never a mixture of moving branches.
    The caller must separately verify the snapshot came from expected_public_commit.
    """
    raw = Path(path).read_bytes()
    if len(raw) > 64_000:
        raise PilotGuardError("Pilot manifest too large")
    try:
        manifest = json.loads(raw.decode("utf-8"), object_pairs_hook=_distinct_json_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PilotGuardError("Invalid UTF-8 JSON manifest") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise PilotGuardError("Unsupported pilot manifest schema")
    if manifest.get("shop_url") != SHOP:
        raise PilotGuardError("Wrong exact Flowwow seller shop")
    for flag in ("safe_to_publish", "may_order", "owner_approved"):
        if manifest.get(flag) is not False:
            raise PilotGuardError("Sale/publication flag is not explicitly false: " + flag)
    public = manifest.get("baseline_public")
    private = manifest.get("private_reference")
    if not isinstance(public, dict) or not isinstance(private, dict):
        raise PilotGuardError("Both GitHub baseline pin references are required")
    if (public.get("repo") != "tophqru/aromatny-flowwow-public-audit" or
            private.get("repo") != "tophqru/flower-shop" or
            public.get("commit") != expected_public_commit or
            private.get("commit") != expected_private_commit or
            not _SHA.fullmatch(str(expected_public_commit)) or
            not _SHA.fullmatch(str(expected_private_commit))):
        raise PilotGuardError("Pilot baseline commit/repository mismatch")
    # Git SHA-1 is the object ID of the pinned file bytes, not a claim about a moving branch.
    blob_header = f"blob {len(baseline_bytes)}\0".encode("ascii")
    actual_blob = hashlib.sha1(blob_header + baseline_bytes).hexdigest()
    if public.get("git_blob_sha") != actual_blob:
        raise PilotGuardError("Local baseline bytes do not match manifest-pinned Git blob")
    targets = manifest.get("exact_trial")
    if not isinstance(targets, list) or len(targets) != 3:
        raise PilotGuardError("Pilot must contain exactly three ordered targets")
    known = {p.get("slug"): p.get("flowwow_url") for p in snapshot.get("products", [])}
    if len(known) != len(snapshot.get("products", [])) or not known:
        raise PilotGuardError("Invalid frozen baseline SKU list")
    seen = set()
    output = []
    for i, item in enumerate(targets):
        if not isinstance(item, dict):
            raise PilotGuardError("Pilot target must be an object")
        slug = _exact_product_url(item.get("url"))
        if slug != item.get("slug") or slug in seen:
            raise PilotGuardError("Pilot target slug mismatch or duplicate")
        if item.get("kind") != _ALLOWED_KINDS[i]:
            raise PilotGuardError("Unexpected pilot target role or order")
        if i < 2 and known.get(slug) != item["url"]:
            raise PilotGuardError("Baseline target is not in frozen snapshot")
        if i == 2 and slug in known:
            raise PilotGuardError("Pending third target already appears in baseline")
        seen.add(slug)
        output.append((item["url"], "PILOT_EXACT_" + str(i + 1)))
    return output, hashlib.sha256(raw).hexdigest()


def verify_pilot_db(store, targets: list[tuple[str, str]], manifest_sha: str) -> None:
    """Reject wrong previous run in same output directory; never reset/delete it."""
    authorized = {url for url, _ in targets}
    rows = store.db.execute("SELECT url FROM pages").fetchall()
    if any(row[0] not in authorized for row in rows):
        raise PilotGuardError("Output DB contains an unrelated SKU: use a new output directory")
    # A previous non-pilot run can leave unrelated discovery/media behind even
    # if the pages table is empty. Export includes both tables: fail closed.
    foreign_discovery = store.db.execute("SELECT url FROM discovery").fetchall()
    if any(url not in authorized for (url,) in foreign_discovery):
        raise PilotGuardError("Output DB contains discovery from an unrelated SKU")
    allowed_slugs = {url.rstrip("/").split("/")[-1] for url in authorized}
    foreign_assets = store.db.execute("SELECT slug FROM assets").fetchall()
    if any(slug not in allowed_slugs for (slug,) in foreign_assets):
        raise PilotGuardError("Output DB contains media from an unrelated SKU")
    guards = store.db.execute("SELECT detail_json FROM events WHERE kind='PILOT_ALLOWLIST_PIN'").fetchall()
    if any(json.loads(row[0]).get("manifest_sha256") != manifest_sha for row in guards):
        raise PilotGuardError("Output DB belongs to a different pilot manifest")
    sessions = store.db.execute("SELECT COUNT(*) FROM events WHERE kind='SESSION_START'").fetchone()[0]
    if sessions and not guards:
        raise PilotGuardError("Existing non-pilot session in output folder")
    if not guards:
        store.event("PILOT_ALLOWLIST_PIN", {"manifest_sha256": manifest_sha,
                                           "allowed_urls": [u for u, _ in targets],
                                           "scope": "EXACT_THREE_ONLY"})
