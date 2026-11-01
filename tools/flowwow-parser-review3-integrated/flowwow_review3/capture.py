#!/usr/bin/env python3
"""One-shop Flowwow UI capture via a local, visible Playwright browser.

Read-only. Does NOT control Flowwow seller settings, use hidden APIs, solve
CAPTCHAs or bypass access restrictions. Data are observations requiring review.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import random
import re
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import quote
from pilot_targets import PilotGuardError, read_pilot_manifest, verify_pilot_db
_IMPORT_ERROR = None
try:
    from PIL import Image, UnidentifiedImageError
    from parsing import (SHOP, canonical_product, canonical_shop, detect_challenge,
                         extract_sections, gallery_candidates, shop_item_links,
                         visible_seller_links, parse_composition, parse_dimensions,
                         image_url_safe, same_shop_url)
    from storage import Store, exclusive_run_lock, atomic_json, atomic_bytes, utc_now
    from scroll_logic import expand_shop_conservatively
    from category_logic import discover_category_labels
except ImportError as exc:  # pragma: no cover - exercised by doctor without site-packages
    _IMPORT_ERROR = exc

BASE_BRANCH="audit/chatgpt-description-recovery-20261031"
REPO="tophqru/aromatny-flowwow-public-audit"
ROOT=Path(__file__).resolve().parent
DEFAULT_OUT=ROOT/"output"
P0=[
 "avtorskiy-buket-s-gortenz-3168","avtorskiy-buket-roza-alst-8286",
 "avtorskiy-buketik-dlya-tebya-r","buket-gortenzii-roza-pionovidn",
 "buket-gortenziy-23","buket-iz-kustovoy-pionovi-3287","buket-iz-roz-kustovoy-pio-6913",
]
CANDIDATES=[
 "FLOWWOW_INDEXED_21_NEW_POSSIBLE_PRODUCTS_2026-10-31.json",
 "FLOWWOW_INDEXED_6_MORE_POSSIBLE_PRODUCTS_2026-10-31.json",
 "FLOWWOW_INDEXED_25_MORE_POSSIBLE_PRODUCTS_2026-10-31.json",
 "FLOWWOW_INDEXED_3_MORE_WITH_SOURCE_DETAILS_2026-10-31.json",
]
PENDING="new-verified-seller-candidates-20261031-4.json"
SHOW_MORE=re.compile(r"^(показать\s+(?:еще|ещё|больше)|загрузить\s+(?:еще|ещё)|show\s+more|load\s+more)$",re.I)
MAX_BYTES=18*1024*1024

class BrowserBlocked(RuntimeError): pass
class ProductUnavailable(RuntimeError): pass
class LocalIntegrityError(RuntimeError): pass


def sha_bytes(data:bytes)->str:return hashlib.sha256(data).hexdigest()


def public_gh_json(path:str)->tuple[dict,str]:
    # Official public GitHub Contents API, no auth, no scraping of private URLs.
    url=f"https://api.github.com/repos/{REPO}/contents/{path}?ref={quote(BASE_BRANCH,safe='')}"
    req=urllib.request.Request(url,headers={"Accept":"application/vnd.github+json","User-Agent":"AromatnyOwnStoreReadOnly/1.0"})
    with urllib.request.urlopen(req,timeout=25) as resp:
        envelope=json.load(resp)
    if envelope.get("encoding")!="base64" or not isinstance(envelope.get("content"),str):
        raise RuntimeError("Public GitHub response has unexpected format; cannot safely continue")
    data=base64.b64decode(envelope["content"])
    if len(data)>10*1024*1024:raise RuntimeError("Baseline too large")
    return json.loads(data),str(envelope.get("sha",""))


def load_source(out:Path,baseline_file:str|None,offline:bool=False)->tuple[dict,list[dict],dict]:
    cache=out/"cache";cache.mkdir(parents=True,exist_ok=True)
    if baseline_file:
        snapshot=json.loads(Path(baseline_file).read_text(encoding="utf-8"))
        origin={"mode":"SUPPLIED_LOCAL_JSON","file":str(baseline_file),"sha256":sha_bytes(Path(baseline_file).read_bytes())}
    else:
        path=cache/"public-snapshot.json"
        if not offline:
            try:
                snapshot,sha=public_gh_json("catalog/public-snapshot.json")
                atomic_json(path,snapshot)
                atomic_json(cache/"baseline-origin.json",{"git_blob_sha":sha,"fetched_at_utc":utc_now(),"branch":BASE_BRANCH})
            except Exception as e:
                if not path.exists():raise RuntimeError(f"Cannot fetch public source and no offline cache: {type(e).__name__}: {e}")
                print("WARNING: Using cached snapshot; public GitHub read failed:",type(e).__name__,file=sys.stderr)
        else:
            if not path.exists():raise RuntimeError("No cached baseline; run once online or pass --baseline")
            snapshot=json.loads(path.read_text(encoding="utf-8"))
        origin=json.loads((cache/"baseline-origin.json").read_text(encoding="utf-8")) if (cache/"baseline-origin.json").exists() else {"mode":"CACHE"}
    validate_baseline(snapshot)
    ledgers=[]
    # A supplied frozen local baseline in strict pilot mode must never fetch moving discovery ledgers.
    if not baseline_file:
        for name in CANDIDATES+[PENDING]:
            cache_path=cache/name
            if not offline:
                try:
                    data,sha=public_gh_json("catalog/discovery/"+name)
                    atomic_json(cache_path,data)
                except Exception as e:
                    print(f"WARNING: public discovery {name} unavailable: {type(e).__name__}",file=sys.stderr)
            if cache_path.exists():
                doc=json.loads(cache_path.read_text(encoding="utf-8"))
                for p in doc.get("items",doc.get("products",[])):
                    slug=p.get("slug")
                    u=canonical_product(p.get("source_url",p.get("flowwow_url","")))
                    if u and slug==u.rstrip("/").split("/")[-1]:
                        ledgers.append({"url":u,"kind":"PENDING4" if name==PENDING else "INDEXED_UNVERIFIED","source_file":name})
    return snapshot,ledgers,origin


def validate_baseline(snapshot:dict):
    if snapshot.get("seller")!=SHOP:raise RuntimeError("Baseline seller mismatch; abort")
    products=snapshot.get("products")
    if not isinstance(products,list) or len(products)<1:raise RuntimeError("Missing baseline products")
    ids=set()
    for p in products:
        slug=p.get("slug");url=canonical_product(p.get("flowwow_url",""))
        if not slug or slug in ids or not url or url!=f"https://flowwow.com/flowers/{slug}/":
            raise RuntimeError("Baseline product slug/URL invalid or duplicate")
        if p.get("seller_url")!=SHOP:raise RuntimeError("Unexpected seller URL in baseline")
        for flag in ("owner_approved","may_order","may_show_publicly"):
            if flag in p and p[flag] is not False:
                raise RuntimeError("Baseline sale permission must remain false: "+slug+"."+flag)
        ids.add(slug)
    if "kompoziciya-v-shlyapnoy-k-4183" in ids:raise RuntimeError("Owner-excluded SKU appears in baseline")


def needs_source_recheck(result: dict) -> bool:
    """Only a CLI opt-in may revisit an already captured but unverified item."""
    return (result.get("seller",{}).get("status")!="EXACT_SELLER_CLICK_VERIFIED"
            or result.get("composition",{}).get("status")!="PARSED_NEEDS_SELLER_CONFIRMATION"
            or result.get("dimensions",{}).get("status")!="PARSED_NEEDS_SELLER_CONFIRMATION"
            or result.get("source_sections",{}).get("description",{}).get("status")!="SOURCE_SECTION_TEXT_CAPTURED"
            or result.get("gallery",{}).get("status")!="GALLERY_CANDIDATES_UNVERIFIED_COMPLETENESS")


def needs_media_capture(result: dict, max_assets: int, out: Path | None = None) -> bool:
    """Trial captures must not silently prevent the full run from getting media.

    When an output directory is supplied, a recorded local file that was deleted
    or corrupted after the trial is treated as missing so the full run recaptures it.
    """
    if result.get("seller", {}).get("status") != "EXACT_SELLER_CLICK_VERIFIED":
        return False
    gallery = result.get("gallery", {})
    if gallery.get("status") != "GALLERY_CANDIDATES_UNVERIFIED_COMPLETENESS":
        return False
    expected = gallery.get("items", [])[:max_assets]
    if not expected:
        return False
    done = set()
    for r in result.get("image_downloads", []):
        if r.get("status") not in {"ALREADY_IN_PUBLIC_BASELINE", "ALREADY_IN_PUBLIC_BASELINE_SHA256",
                                   "ALREADY_CAPTURED", "NEW_ORIGINAL_FILE"}:
            continue
        if out is not None and r.get("relative_path"):
            try:
                target = safe_new_media_path(out, r["relative_path"])
            except LocalIntegrityError:
                continue
            if not target.is_file():
                continue
            if r.get("sha256") and sha_bytes(target.read_bytes()) != r["sha256"]:
                continue
        done.add(r.get("source_url"))
    return any(url not in done for url in expected)


def safe_new_media_path(out: Path, relative: str) -> Path:
    """Never let a manipulated progress database reference a file outside output/new-media."""
    output_root = out.resolve()
    media_root = (out / "new-media").resolve()
    target = (out / relative).resolve()
    if not media_root.is_relative_to(output_root) or not target.is_relative_to(media_root):
        raise LocalIntegrityError("MEDIA_PATH_OUTSIDE_ISOLATED_OUTPUT")
    return target


def verify_local_media(out: Path, assets: list[tuple]) -> int:
    """Check every recorded new file before exporting a successful report."""
    verified = 0
    for url, slug, sha, path, byte_count, width, height, status in assets:
        if status != "NEW_ORIGINAL_FILE":
            continue
        if not path:
            raise LocalIntegrityError("NEW_MEDIA_RECORD_HAS_NO_PATH")
        target = safe_new_media_path(out, path)
        if not target.is_file() or target.stat().st_size != byte_count:
            raise LocalIntegrityError("MISSING_OR_TRUNCATED_LOCAL_MEDIA:" + slug)
        if sha_bytes(target.read_bytes()) != sha:
            raise LocalIntegrityError("LOCAL_MEDIA_SHA256_MISMATCH:" + slug)
        verified += 1
    return verified


def initial_queue(snapshot:dict, ledgers:list[dict], discovered:list[tuple[str,str]])->list[tuple[str,str]]:
    products={p["slug"]:p for p in snapshot["products"]}
    raw=[]
    for slug in P0:
        if slug in products:raw.append((products[slug]["flowwow_url"],"BASELINE_P0"))
    raw += [(p["flowwow_url"],"BASELINE_66") for p in snapshot["products"]]
    raw += [(p["url"],p["kind"]) for p in ledgers]
    raw += [(u,"SHOP_DISCOVERY:"+c) for u,c in discovered]
    out=[];seen=set()
    for url,kind in raw:
        u=canonical_product(url)
        if not u or u in seen or u.endswith("/kompoziciya-v-shlyapnoy-k-4183/"):continue
        seen.add(u);out.append((u,kind))
    return out


def load_playwright():
    try:from playwright.sync_api import sync_playwright
    except ImportError as e:raise RuntimeError("Playwright not installed; run setup_windows.ps1") from e
    return sync_playwright


def browser_profile(out:Path)->Path:
    parent=Path(os.environ.get("LOCALAPPDATA",str(Path.home())))
    profile=(parent/"AromatnyFlowwowCapture"/"BrowserProfile").resolve()
    if profile.is_relative_to(out.resolve()) or profile.is_relative_to(ROOT.resolve()):
        raise RuntimeError("Refusing to store browser session inside output or source folder")
    profile.mkdir(parents=True,exist_ok=True)
    return profile


def launch_context(p,args,out:Path):
    options={"headless":False,"viewport":{"width":1280,"height":900},"accept_downloads":False,
             "service_workers":"allow","timeout":40000}
    # No stealth args / proxy / fingerprint spoofing / remote debugging of user's normal Chrome profile.
    profile=browser_profile(out)
    if args.browser=="chromium":
        return p.chromium.launch_persistent_context(str(profile),**options)
    return p.chromium.launch_persistent_context(str(profile),channel=args.browser,**options)


def gentle_wait(args):time.sleep(random.uniform(args.pause_min,args.pause_max))


def navigate(page,url:str):
    try:
        response=page.goto(url,wait_until="domcontentloaded",timeout=40000)
    except Exception as e:
        # A blocked network/admin policy is not a cue to hammer the next 100 SKUs.
        raise BrowserBlocked(f"BROWSER_NAVIGATION_FAILED: {type(e).__name__}") from e
    page.wait_for_timeout(1300)
    final=page.url
    host=__import__("urllib.parse",fromlist=["urlsplit"]).urlsplit(final).hostname or ""
    if host.lower() not in ("flowwow.com","www.flowwow.com"):
        raise BrowserBlocked("Navigation left official Flowwow domain")
    status=response.status if response else None
    title=page.title()
    txt=page.locator("body").inner_text(timeout=12000)[:1600] if page.locator("body").count() else ""
    if status in (401,403,429) or detect_challenge(title,txt):
        raise BrowserBlocked(f"Flowwow access restriction: status={status}; stop without retries")
    if status in (404,410):
        raise ProductUnavailable(f"HTTP_{status}_PUBLIC_PAGE_NOT_PROOF_OF_DRAFT")
    if status is None or status >= 500:
        raise BrowserBlocked(f"SOURCE_SERVER_OR_NETWORK_UNAVAILABLE: {status}")
    return {"http_status":status,"final_url":final,"title":title}


def shop_categories(page,snapshot:dict)->list[str]:
    return sorted({str(p.get("source_category","")) for p in snapshot["products"] if p.get("source_category")})


def expand_shop(page,args,store:Store,category:str)->dict:
    result=expand_shop_conservatively(page,args,store,category,gentle_wait)
    result['observed_at']=utc_now()
    return result


def collect_shop(page,store:Store,args,snapshot:dict)->list[dict]:
    nav=navigate(page,SHOP)
    result=[]
    if canonical_shop(page.url)!=SHOP:
        raise BrowserBlocked("Canonical shop redirect did not stay at requested shop")
    baseline_categories=shop_categories(page,snapshot)
    observed_categories=discover_category_labels(page.content(),page.url)
    category_plan=["Вся витрина"]+list(dict.fromkeys(baseline_categories+observed_categories))
    store.event("CATEGORY_DISCOVERY",{"known_baseline":baseline_categories,"observed_in_shop_dom":observed_categories,"attempted":category_plan,"all_categories_proven_complete":False})
    if args.max_categories:category_plan=category_plan[:args.max_categories]
    for category in category_plan:
        if category!="Вся витрина":
            navigate(page,SHOP)
            button=page.get_by_role("button",name=category,exact=True)
            link=page.get_by_role("link",name=category,exact=True)
            tab=page.get_by_role("tab",name=category,exact=True)
            try:
                if button.count()==1 and button.first.is_visible():button.first.click(timeout=7000)
                elif link.count()==1 and link.first.is_visible():link.first.click(timeout=7000)
                elif tab.count()==1 and tab.first.is_visible():tab.first.click(timeout=7000)
                else:
                    store.event("CATEGORY_NOT_ACCESSIBLE",{"category":category,"reason":"NO_UNIQUE_VISIBLE_CONTROL"})
                    continue
                page.wait_for_timeout(1000)
                # Category controls may be unrelated links; do not classify products from
                # another seller or external page as part of this shop.
                if not same_shop_url(page.url):
                    store.event("CATEGORY_NAVIGATION_OUTSIDE_SHOP",{"category":category,"observed_url":page.url[:250]})
                    raise BrowserBlocked("Category control navigated outside the requested shop; stop")
            except BrowserBlocked:
                raise
            except Exception as e:
                store.event("CATEGORY_NAVIGATION_ERROR",{"category":category,"error_type":type(e).__name__})
                continue
        observed=expand_shop(page,args,store,category)
        result.append(observed)
        if observed.get('stop_reason')=='MORE_CONTROL_NAVIGATED_OUTSIDE_SHOP':
            raise BrowserBlocked('Show-more control navigated outside canonical shop; stop')
        gentle_wait(args)
    return result


def click_seller_link(page,url_before:str)->dict:
    """Seller confirmed only after actually clicking one unambiguous visible shop link."""
    candidates=[]
    for item in page.locator("main a[href*='/shop/'], article a[href*='/shop/']").all():
        try:
            if not item.is_visible():continue
            raw=item.get_attribute("href") or ""
            shop=canonical_shop(raw,page.url)
            text=item.inner_text(timeout=1200)[:100]
            label=text.strip().casefold()
            if shop and ("перейти в магазин" in label or label=="ароматный букет"):
                # A generic navigation link labelled 'Магазин' does not prove product ownership.
                candidates.append((item,shop,text))
        except Exception:continue
    unique={shop for _,shop,_ in candidates}
    if len(candidates)!=1 or len(unique)!=1:
        return {"status":"UNVERIFIED","reason":"NO_UNAMBIGUOUS_VISIBLE_SELLER_LINK","observed_links":sorted(unique),"clicked":False}
    locator,expected,text=candidates[0]
    context=getattr(page,"context",None)
    pages_before=list(context.pages) if context is not None else []
    popup=None
    try:
        locator.click(timeout=7000)
        page.wait_for_timeout(1000)
        new_pages=[p for p in (context.pages if context is not None else []) if p not in pages_before]
        if len(new_pages)>1:
            out={"status":"UNVERIFIED","reason":"MULTIPLE_NEW_TABS_AFTER_SELLER_CLICK","clicked":True}
        else:
            if new_pages:
                popup=new_pages[0]
                try:popup.wait_for_load_state("domcontentloaded",timeout=5000)
                except Exception:pass
                observed_url=popup.url
            else:
                observed_url=page.url
            final=canonical_shop(observed_url)
            out={"status":"EXACT_SELLER_CLICK_VERIFIED" if final==SHOP and expected==SHOP else "DIFFERENT_OR_UNVERIFIED_SELLER",
                 "expected_link":expected,"final_url":observed_url,"seller_text":text,"clicked":True,
                 "opened_new_tab":bool(new_pages)}
    except Exception as e:
        out={"status":"UNVERIFIED","reason":"CLICK_FAILED:"+type(e).__name__,"clicked":False}
    finally:
        if popup is not None:
            try:popup.close()
            except Exception:pass
        # Returning to known URL is safer than browser.back() after SPA navigation.
        navigate(page,url_before)
    return out


def download_assets(context,store:Store,args,slug:str,source_urls:list[str],baseline:dict,out:Path)->list[dict]:
    by_url={x["source_url"]:x for p in baseline["products"] for x in p.get("gallery",[])}
    by_hash={x["sha256"]:x for p in baseline["products"] for x in p.get("gallery",[])}
    results=[]
    for i,url in enumerate(source_urls[:args.max_gallery_assets],1):
        safe_url=image_url_safe(url)
        if safe_url is None:
            results.append({"order":i,"source_url":str(url)[:250],"status":"UNVERIFIED_DOWNLOAD_ERROR",
                            "error_type":"UNSAFE_IMAGE_URL","error_summary":"URL failed CDN/HTTPS allowlist; no network request made"})
            continue
        url=safe_url
        if url in by_url:
            results.append({"order":i,"source_url":url,"status":"ALREADY_IN_PUBLIC_BASELINE","original_path":by_url[url]["path"]});continue
        existing=store.existing_asset(slug,url)
        if existing:
            sha,path,bytes_n,status=existing
            if status == "BASELINE_HASH_MATCH" and path is None:
                results.append({"order":i,"source_url":url,"status":"ALREADY_IN_PUBLIC_BASELINE_SHA256","sha256":sha});continue
            if path:
                existing_file = safe_new_media_path(out, path)
                if existing_file.exists():
                    if existing_file.stat().st_size != bytes_n or sha_bytes(existing_file.read_bytes()) != sha:
                        raise LocalIntegrityError("LOCAL_MEDIA_SHA256_MISMATCH:" + slug)
                    results.append({"order":i,"source_url":url,"status":"ALREADY_CAPTURED","sha256":sha,"relative_path":path});continue
        gentle_wait(args)
        try:
            response=context.request.get(url,timeout=30000,max_redirects=0)
            if response.status in (401,403,429):raise BrowserBlocked(f"Image CDN refused access: {response.status}; stop")
            if not response.ok:raise RuntimeError(f"IMAGE_STATUS_{response.status}")
            size_header=response.headers.get("content-length")
            if size_header and int(size_header)>MAX_BYTES:raise RuntimeError("IMAGE_TOO_LARGE")
            data=response.body()
            if not (64<=len(data)<=MAX_BYTES):raise RuntimeError("IMAGE_SIZE_OUT_OF_RANGE")
            with Image.open(io.BytesIO(data)) as im:
                image_type=(im.format or "").upper();width,height=im.size
                if width>6000 or height>6000 or width*height>36_000_000:
                    raise RuntimeError("IMAGE_PIXEL_LIMIT_EXCEEDED")
                im.verify()
            if image_type not in ("JPEG","PNG","WEBP") or width<480 or height<480:
                raise RuntimeError("IMAGE_NOT_HIGH_RES_PRODUCT_MEDIA")
            sha=sha_bytes(data)
            if sha in by_hash:
                old=by_hash[sha]
                results.append({"order":i,"source_url":url,"status":"ALREADY_IN_PUBLIC_BASELINE_SHA256","sha256":sha,"original_path":old["path"]})
                store.record_asset(slug,url,sha,None,len(data),width,height,"BASELINE_HASH_MATCH")
                continue
            ext={"JPEG":"jpg","PNG":"png","WEBP":"webp"}[image_type]
            relative=f"new-media/{slug}/{i:03d}-{sha[:12]}.{ext}"
            path=safe_new_media_path(out,relative)
            if path.exists() and sha_bytes(path.read_bytes())!=sha:raise LocalIntegrityError("SAVED_ASSET_CONFLICT:" + slug)
            if not path.exists():atomic_bytes(path,data)
            store.record_asset(slug,url,sha,relative,len(data),width,height,"NEW_ORIGINAL_FILE")
            results.append({"order":i,"source_url":url,"status":"NEW_ORIGINAL_FILE","relative_path":relative,
                            "sha256":sha,"bytes":len(data),"width_px":width,"height_px":height,"format":image_type})
        except (BrowserBlocked, LocalIntegrityError):
            raise
        except Exception as e:
            results.append({"order":i,"source_url":url,"status":"UNVERIFIED_DOWNLOAD_ERROR","error_type":type(e).__name__,
                            "error_summary":str(e)[:120] if not isinstance(e,BrowserBlocked) else "Access restricted"})
    return results


def record_product(page,context,store:Store,args,baseline:dict,url:str,category:str,out:Path)->dict:
    slug=url.rstrip("/").split("/")[-1]
    nav=navigate(page,url)
    if canonical_product(page.url)!=url:
        raise BrowserBlocked("Product URL redirected outside expected exact SKU; stop, do not mix product data")
    page.wait_for_timeout(700)
    dom=page.content()
    sections=extract_sections(dom)
    links=visible_seller_links(dom,page.url)
    seller=click_seller_link(page,url)
    # Seller click/return may redirect to a *different* product. Never mix galleries or names.
    if canonical_product(page.url) != url:
        raise BrowserBlocked("PRODUCT_URL_CHANGED_AFTER_SELLER_CLICK_OR_RETURN")
    # Seller click may navigate/re-render, so capture DOM a second time if it did.
    if seller.get("clicked"):
        dom=page.content();sections=extract_sections(dom)
    composition=parse_composition(sections["composition"]["text"])
    dimensions=parse_dimensions(sections["dimensions"]["text"])
    gallery=gallery_candidates(dom,page.url,args.gallery_selector)
    if page.locator("h1").count()==0:
        raise ProductUnavailable("NO_PRODUCT_H1_VISIBLE_NOT_PROOF_OF_ABANDONMENT")
    result={"slug":slug,"url":url,"category_source":category,"observed_at_utc":utc_now(),
            "page":nav,"product_h1":page.locator("h1").first.inner_text(timeout=3000)[:400] if page.locator("h1").count() else None,
            "seller":seller,"seller_links_in_dom":links,"source_sections":sections,
            "composition":composition,"dimensions":dimensions,"gallery":gallery,
            "source_method":"ACTUAL_VISIBLE_BROWSER_DOM","owner_approved":False,"may_order":False,"may_show_publicly":False,
            "publication_status":"NOT_APPROVED","image_downloads":[],
            "limitations":["Live seller stock/price and review images are not verified by this conservative extractor."]}
    if args.download_new_media and seller.get("status")=="EXACT_SELLER_CLICK_VERIFIED" and gallery["status"]=="GALLERY_CANDIDATES_UNVERIFIED_COMPLETENESS":
        result["image_downloads"]=download_assets(context,store,args,slug,gallery["items"],baseline,out)
    # Save one product transaction immediately; no modified source catalog.
    store.record_page(url,slug,category,"CAPTURED",result)
    store.event("PRODUCT_CAPTURED",{"slug":slug,"seller_status":seller.get("status"),"gallery_status":gallery["status"]})
    return result


def crawl(args):
    out=Path(args.output).expanduser().resolve();out.mkdir(parents=True,exist_ok=True)
    with exclusive_run_lock(out/"capture.lock"):
        store=Store(out/"progress.sqlite3")
        try:
            # A previous global HTTP/network block must not turn into a crawl of
            # the *next* 100 URLs merely because this process was restarted.
            blocked=store.db.execute("SELECT MAX(seq) FROM events WHERE kind IN ('SHOP_BLOCKED_STOP','ACCESS_BLOCKED_STOP')").fetchone()[0] or 0
            allowed=store.db.execute("SELECT MAX(seq) FROM events WHERE kind='OPERATOR_RETRY_AUTHORIZED'").fetchone()[0] or 0
            if blocked>allowed:
                if not args.retry_failed:
                    print("STOP: previous access block is unresolved. Do not retry automatically. After restoring permitted access, explicitly pass --retry-failed.",file=sys.stderr)
                    return 3
                store.event("OPERATOR_RETRY_AUTHORIZED",{"previous_block_event_seq":blocked,"source":"explicit CLI --retry-failed"})
            baseline,ledgers,origin=load_source(out,args.baseline,args.offline_baseline)
            pilot_targets = None
            if getattr(args, "pilot_manifest", None):
                pilot_targets, manifest_sha = read_pilot_manifest(
                    Path(args.pilot_manifest), baseline,
                    expected_public_commit="864f6e222ea58cfed063f6594f896edb67ed8e7f",
                    expected_private_commit="ac74ac06983eff5b4cdd72e8cd11433baf1d7240",
                    baseline_bytes=Path(args.baseline).read_bytes())
                verify_pilot_db(store, pilot_targets, manifest_sha)
                store.event("PILOT_PREFLIGHT_VALIDATED", {"manifest_sha256":manifest_sha,
                    "authorized_product_count":len(pilot_targets),"strict_one_store":SHOP})
            store.event("SESSION_START",{"source":origin,"browser":args.browser,"max_products":args.max_products,
                                         "strict_one_store":SHOP,"parallel_workers":1})
            with load_playwright()() as p:
                ctx=launch_context(p,args,out)
                try:
                    # Persistent Chromium may already have an initial blank tab.
                    page=ctx.pages[0] if ctx.pages else ctx.new_page()
                    if not args.skip_shop:
                        print("OPEN SHOP",SHOP,flush=True)
                        try:collect_shop(page,store,args,baseline)
                        except BrowserBlocked as e:
                            store.event("SHOP_BLOCKED_STOP",{"url":SHOP,"reason":str(e)})
                            print("STOP: shop access restricted; no retries.",file=sys.stderr)
                            return 3
                    targets=pilot_targets if pilot_targets is not None else initial_queue(baseline,ledgers,store.urls())
                    seen=0
                    for url,kind in targets:
                        if args.max_products and seen>=args.max_products:break
                        old=store.db.execute("SELECT status,result_json FROM pages WHERE url=?",(url,)).fetchone()
                        if old:
                            if old[0]=="CAPTURED":
                                previous = json.loads(old[1])
                                media_required = (args.download_new_media
                                                  and needs_media_capture(previous, args.max_gallery_assets, out))
                                source_required = (args.recheck_unverified
                                                   and needs_source_recheck(previous))
                                if not (media_required or source_required):
                                    continue
                            elif not args.retry_failed:
                                continue
                        seen+=1
                        print(f"{seen}: {kind}: {url}",flush=True)
                        gentle_wait(args)
                        try:
                            record_product(page,ctx,store,args,baseline,url,kind,out)
                        except LocalIntegrityError as e:
                            store.event("LOCAL_MEDIA_INTEGRITY_STOP",{"url":url,"reason":str(e)})
                            print("STOP: local media integrity violation. Preserve output and investigate.",file=sys.stderr)
                            return 4
                        except ProductUnavailable as e:
                            store.record_page(url,url.rstrip("/").split("/")[-1],kind,"NOT_AVAILABLE_PUBLICLY",{"reason":str(e),"not_proof_of_draft":True},str(e))
                            store.event("PRODUCT_UNAVAILABLE",{"url":url,"reason":str(e)})
                        except BrowserBlocked as e:
                            store.record_page(url,url.rstrip("/").split("/")[-1],kind,"BLOCKED",{"blocked_at":utc_now(),"reason":str(e)},str(e))
                            store.event("ACCESS_BLOCKED_STOP",{"url":url,"reason":str(e)})
                            print("STOP: browser access restricted. No retries or bypass attempted.",file=sys.stderr)
                            return 3
                        except Exception as e:
                            store.record_page(url,url.rstrip("/").split("/")[-1],kind,"ERROR",{"error_type":type(e).__name__},str(e)[:150])
                            store.event("PRODUCT_ERROR",{"url":url,"error_type":type(e).__name__,"detail":str(e)[:150]})
                    store.event("SESSION_FINISHED",{"products_attempted_this_run":seen,"all_seller_categories_proven_complete":False})
                    print(f"Finished batch: {seen} products attempted; data in {out}")
                finally:ctx.close()
        finally:store.close()
    return 0


def export(args):
    out=Path(args.output).expanduser().resolve();db_path=out/"progress.sqlite3"
    if not db_path.exists():raise RuntimeError("No progress database exists. Run crawl first.")
    store=Store(db_path)
    try:
        products=[]
        for url,slug,cat,status,at,payload,error,attempts in store.page_rows():
            item=json.loads(payload)
            item["capture_status"]=status;item["attempts"]=attempts
            products.append(item)
        discoveries=[{"url":url,"category":cat,"discovered_at":at,"method":method}
                     for url,cat,at,method in store.db.execute("SELECT url,category,observed_at,method FROM discovery ORDER BY category,url")]
        verified_local_files = verify_local_media(out, store.asset_rows())
        images=[{"source_url":url,"slug":slug,"sha256":sha,"relative_path":path,"bytes":bytes_n,
                 "width":w,"height":h,"status":status}
                for url,slug,sha,path,bytes_n,w,h,status in store.asset_rows()]
        counts={"recorded_products":len(products),"browser_captured":sum(p["capture_status"]=="CAPTURED" for p in products),
                "seller_click_verified":sum(p.get("seller",{}).get("status")=="EXACT_SELLER_CLICK_VERIFIED" for p in products),
                "new_image_files":sum(x["status"]=="NEW_ORIGINAL_FILE" for x in images),
                "new_image_files_sha256_verified":verified_local_files,
                "observed_discovery_links":len(discoveries),"all_categories_proven_complete":False,
                "automatically_approved_products":0}
        review=out/"review"
        atomic_json(review/"products.json",products)
        atomic_json(review/"discovery.json",discoveries)
        atomic_json(review/"media-delta.json",images)
        atomic_json(review/"summary.json",{"generated_at_utc":utc_now(),"counts":counts,"source":"Local browser UI (not a production catalog)",
                           "caveat":"All seller and gallery observations require review before import; no live completeness proof."})
        import html
        rows=[]
        for p in products:
            slug=html.escape(p.get("slug", ""))
            raw_url=p.get("url", "")
            safe_url=canonical_product(raw_url) or canonical_shop(raw_url)
            url_cell=(f'<a href="{html.escape(safe_url,quote=True)}" rel="noreferrer">{slug}</a>'
                      if safe_url else f'<span>{slug}</span>')
            seller=html.escape(p.get("seller",{}).get("status","—"))
            comp=html.escape(p.get("composition",{}).get("status","—"))
            dim=html.escape(p.get("dimensions",{}).get("status","—"))
            gallery=html.escape(p.get("gallery",{}).get("status","—"))
            rows.append(f'<tr><td>{url_cell}</td><td>{seller}</td><td>{comp}</td><td>{dim}</td><td>{gallery}</td></tr>')
        page='''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Ароматный букет — локальный журнал</title><style>body{font:15px/1.5 system-ui;margin:28px auto;max-width:1200px;padding:0 15px;color:#223}table{border-collapse:collapse;width:100%}th,td{padding:10px;border-bottom:1px solid #ddd;text-align:left}thead{background:#eee}tr:nth-child(2n){background:#f7f7f9}a{color:#0652a5}</style><h1>Локальный журнал Flowwow</h1><p>Это <b>не опубликованный каталог</b>. Все поля и фотографии требуют подтверждения перед импортом. Исходные продажи не изменялись.</p><table><thead><tr><th>Товар</th><th>Продавец</th><th>Состав</th><th>Размеры</th><th>Фото</th></tr></thead><tbody>'''+''.join(rows)+'''</tbody></table></html>'''
        atomic_bytes(review/"report.html",page.encode("utf-8"))
        print(json.dumps(counts,ensure_ascii=False,indent=2));print("Report:",review/"report.html")
    finally:store.close()
    return 0


def doctor(args):
    import platform
    report={"python":sys.version.split()[0],"os":platform.platform(),"ram_note":"For 12 GB RAM, keep one headed browser and one tab; no parallel workers.",
            "baseline_source":f"PUBLIC {REPO} @ {BASE_BRANCH}","output":str(Path(args.output).resolve())}
    if _IMPORT_ERROR is not None:
        report["dependencies"]="MISSING"
        report["missing_dependency"]=f"{type(_IMPORT_ERROR).__name__}: {_IMPORT_ERROR}"
        report["action"]="BLOCKED: run setup_windows.ps1 or pip install -r requirements.txt before crawl/export"
    else:
        report["dependencies"]="AVAILABLE"
    try:
        import playwright
        report["playwright"]="PYTHON_LIBRARY_AVAILABLE"
    except ImportError:report["playwright"]="MISSING_RUN_SETUP_WINDOWS_PS1"
    report["supported_browsers"]=["chromium","msedge","chrome"]
    report["session_profile"]="Separate profile under user's LOCALAPPDATA, NOT saved to output ZIP/GitHub"
    print(json.dumps(report,ensure_ascii=False,indent=2));return 0


def cli(argv=None):
    parser=argparse.ArgumentParser(description="Owner-authorized read-only single-shop Flowwow capture")
    parser.add_argument("command",choices=["doctor","crawl","export"])
    parser.add_argument("--output",default=str(DEFAULT_OUT))
    parser.add_argument("--pilot-manifest",help="Strict exactly-three-SKU manifest; requires a pinned local --baseline and isolated --output")
    parser.add_argument("--baseline",help="Local public-snapshot.json instead of GitHub auto-fetch")
    parser.add_argument("--offline-baseline",action="store_true",help="Use last cached public snapshot only")
    parser.add_argument("--browser",choices=["chromium","msedge","chrome"],default="chromium")
    parser.add_argument("--max-products",type=int,default=2,help="0 means all; default trial checks 2")
    parser.add_argument("--max-categories",type=int,default=1,help="0 means all shop categories; default trial only the shop home")
    parser.add_argument("--skip-shop",action="store_true",help="Skip shop listing (product source verification remains required)")
    parser.add_argument("--retry-failed",action="store_true",help="Explicitly retry previously blocked/failed URLs, one at a time")
    parser.add_argument("--recheck-unverified",action="store_true",help="Explicitly revisit captured but incomplete products after selector improvements")
    parser.add_argument("--gallery-selector",help="CSS selector identifying only original product gallery images within main")
    parser.add_argument("--download-new-media",action="store_true",help="Download only newly observed original gallery URLs for exact seller-verified products")
    parser.add_argument("--max-gallery-assets",type=int,default=30)
    parser.add_argument("--max-load-cycles",type=int,default=35)
    parser.add_argument("--max-scroll-steps",type=int,default=80,help="Bounded incremental scrolling per pagination cycle")
    parser.add_argument("--pause-min",type=float,default=5.0)
    parser.add_argument("--pause-max",type=float,default=12.0)
    args=parser.parse_args(argv)
    if args.pilot_manifest and (args.command!="crawl" or not args.baseline or args.output==str(DEFAULT_OUT) or args.max_products!=3 or args.max_categories!=1):
        parser.error("Pilot requires crawl, explicit --baseline, unique --output, --max-products 3 and --max-categories 1")
    if args.pause_min<3 or args.pause_max<args.pause_min or args.max_products<0 or args.max_categories<0 or not (1<=args.max_gallery_assets<=60) or not (1<=args.max_load_cycles<=100) or not (1<=args.max_scroll_steps<=300):
        parser.error("Invalid limits: pause_min>=3; max>=min; valid product/gallery/load limits required")
    try:
        if args.command=="doctor":return doctor(args)
        if _IMPORT_ERROR is not None:
            raise RuntimeError(f"Missing dependencies: {_IMPORT_ERROR}. Run setup_windows.ps1 or pip install -r requirements.txt")
        if args.command=="export":return export(args)
        return crawl(args)
    except KeyboardInterrupt:
        print("Interrupted; previously committed SQLite records remain available",file=sys.stderr)
        return 130
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}",file=sys.stderr)
        return 2

if __name__=="__main__":raise SystemExit(cli())
