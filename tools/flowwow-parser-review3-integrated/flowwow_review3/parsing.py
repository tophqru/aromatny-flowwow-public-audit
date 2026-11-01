"""Conservative, testable parsing of rendered public product DOM.

Selectors are heuristic: when ambiguity exists, preserve a raw block and do not
claim a verified value. No seller/account data or hidden API is accessed.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlsplit, urlunsplit
from bs4 import BeautifulSoup, Tag

SHOP = "https://flowwow.com/shop/lyubov-eto-699e0e4519/"
PRODUCT_RE = re.compile(r"^/flowers/([a-z0-9_-]+)/?$", re.I)
SHOP_RE = re.compile(r"^/shop/([a-z0-9_-]+)/?$", re.I)
COMPONENT_RE = re.compile(r"^\s*(.+?)\s*[-–—:]\s*(\d{1,4})(?:\s*(шт\.?|штук|вет\.?|стеб\.?|pcs))?\s*$",re.I)
SIZE_RE = re.compile(r"\b(?:ширина\s*[:–-]?\s*)?(\d{1,3})\s*(?:×|x|х|\*)\s*(\d{1,3})\s*(?:см|cm)?\b",re.I)
LABELS = {
 "composition": ("состав", "состав букета", "состав композиции"),
 "description": ("описание", "описание товара"),
 "dimensions": ("размеры", "размер букета", "габариты"),
}
STOP_LABELS = tuple(x for group in LABELS.values() for x in group) + (
 "доставка", "отзывы", "похожие товары", "условия доставки", "наличие", "оплата", "уход",
)
GALLERY_HINTS = ("gallery", "галере", "swiper", "product-photo", "productphoto", "product-image", "productimage", "thumb", "слайд")
BLOCKED_HINTS = ("access denied", "403 forbidden", "подтвердите, что вы человек", "captcha", "доступ ограничен")


def canonical_product(href: str, base: str = "https://flowwow.com/") -> str | None:
    try:
        u=urlsplit(urljoin(base,href))
        if u.scheme != "https" or u.username or u.password or (u.hostname or "").lower() not in ("flowwow.com", "www.flowwow.com") or (u.port not in (None, 443)):
            return None
        match=PRODUCT_RE.fullmatch(u.path)
        if not match: return None
        return f"https://flowwow.com/flowers/{match.group(1).lower()}/"
    except (ValueError, TypeError): return None


def canonical_shop(href: str, base: str = "https://flowwow.com/") -> str | None:
    try:
        u=urlsplit(urljoin(base,href))
        if u.scheme != "https" or u.username or u.password or (u.hostname or "").lower() not in ("flowwow.com", "www.flowwow.com") or (u.port not in (None, 443)):
            return None
        m=SHOP_RE.fullmatch(u.path)
        return f"https://flowwow.com/shop/{m.group(1).lower()}/" if m else None
    except (ValueError, TypeError): return None


def same_shop_url(href: str, base: str = SHOP) -> bool:
    """True only for the canonical shop root or a subpath, with/without trailing slash."""
    try:
        u=urlsplit(urljoin(base,href))
        expected=urlsplit(SHOP)
        if u.scheme!="https" or u.username or u.password or (u.hostname or "").lower() not in ("flowwow.com","www.flowwow.com") or u.port not in (None,443):
            return False
        path=u.path.rstrip("/")
        root=expected.path.rstrip("/")
        return path==root or path.startswith(root+"/")
    except (ValueError,TypeError):
        return False


def image_url_safe(value: str | None, base: str = "https://flowwow.com/") -> str | None:
    if not value or value.startswith("data:") or value.startswith("blob:"): return None
    try:
        u=urlsplit(urljoin(base,value))
        h=(u.hostname or "").lower()
        if u.scheme != "https" or u.port not in (None, 443) or not (h=="flowwow-images.com" or h.endswith(".flowwow-images.com")):
            return None
        # Prevent accidental storage of signed URLs / credentials in reports.
        if u.username or u.password or u.query or u.fragment: return None
        return urlunsplit(("https",u.netloc.lower(),u.path,"",""))
    except (ValueError, TypeError): return None


def shop_item_links(html: str, base: str) -> list[str]:
    soup=BeautifulSoup(html,"html.parser")
    return list(dict.fromkeys(u for a in soup.find_all("a",href=True) if (u:=canonical_product(a["href"],base))))


def visible_seller_links(html: str, base: str) -> list[dict]:
    soup=BeautifulSoup(html,"html.parser")
    result=[]
    for a in soup.find_all("a",href=True):
        u=canonical_shop(a["href"],base)
        if not u: continue
        # Marked evidence of link presence, not actual click or seller verification.
        result.append({"href":u,"text":a.get_text(" ",strip=True)[:120],"dom_link_only":True})
    return result


def _text(el: Tag) -> str:
    return re.sub(r"\s+"," ",el.get_text(" ",strip=True)).strip()


def _is_label(text: str, category: str) -> bool:
    normalized=text.strip().lower().rstrip(":： ")
    return normalized in LABELS[category]


def _sibling_block(el: Tag) -> str | None:
    """Extract only nearby siblings of a real heading/label, not whole main/body."""
    chunks=[]
    for sibling in el.next_siblings:
        if not isinstance(sibling,Tag): continue
        if sibling.name in ("h1","h2","h3","h4","h5","h6"): break
        data=_text(sibling)
        if not data: continue
        if data.lower().rstrip(":： ") in STOP_LABELS: break
        chunks.append(data)
        if len(" ".join(chunks))>1800: break
    if chunks:
        return "\n".join(chunks)[:2500]
    # A label can be followed by value inside shared direct parent.
    if isinstance(el.parent,Tag) and el.parent.name not in ("body","main","article"):
        text=_text(el.parent)
        label=_text(el)
        if text.startswith(label) and len(text)>len(label)+2 and len(text)<1600:
            suffix=text[len(label):].strip(":： –-\n ")
            if suffix and not any(suffix.lower().startswith(x) for x in STOP_LABELS):
                return suffix
    return None


def extract_sections(html: str) -> dict:
    soup=BeautifulSoup(html,"html.parser")
    # Only inspect headings/labels in the main document; never parse reviews by scraping all body text.
    main=soup.find("main") or soup.find("article")
    if main is None:
        return {name:{"status":"SOURCE_NOT_VISIBLE","text":None,"reason":"MAIN_NOT_IDENTIFIED"} for name in LABELS}
    out={}
    for name in LABELS:
        matches=[]
        for node in main.find_all(["h2","h3","h4","h5","h6","strong","b","dt","span","p","button"],recursive=True):
            if _is_label(_text(node),name):
                text=_sibling_block(node)
                if text: matches.append(text)
        matches=list(dict.fromkeys(matches))
        if len(matches)==1:
            out[name]={"status":"SOURCE_SECTION_TEXT_CAPTURED","text":matches[0],"reason":None}
        elif len(matches)>1:
            out[name]={"status":"AMBIGUOUS_MULTIPLE_SECTIONS","text":None,"reason":"CONFLICTING_BLOCKS"}
        else:
            out[name]={"status":"SOURCE_NOT_VISIBLE","text":None,"reason":"NO_UNAMBIGUOUS_LABEL_BLOCK"}
    return out


def parse_composition(raw: str | None) -> dict:
    if not raw: return {"status":"SOURCE_NOT_VISIBLE","items":[],"raw":raw}
    # Source paragraphs often separate records with dot after шт. Normalize only separators.
    lines=re.split(r"(?:\n|;|(?<=шт\.)\s+)",raw.replace("\r","\n"))
    items=[]; unparsed=[]
    for raw_line in lines:
        part=raw_line.strip().strip("•· ")
        if not part: continue
        m=COMPONENT_RE.match(part)
        if not m:
            unparsed.append(part); continue
        quantity=int(m.group(2))
        if quantity<=0 or quantity>999:
            unparsed.append(part); continue
        items.append({"component":m.group(1).strip(),"quantity":quantity,"unit":(m.group(3) or "NOT_STATED").rstrip(".")})
    if unparsed or not items:
        return {"status":"UNVERIFIED_PARSE","items":[],"raw":raw,"unparsed":unparsed}
    return {"status":"PARSED_NEEDS_SELLER_CONFIRMATION","items":items,"raw":raw,"unparsed":[]}


def parse_dimensions(raw: str | None) -> dict:
    if not raw: return {"status":"SOURCE_NOT_VISIBLE","width_cm":None,"height_cm":None,"raw":raw}
    matches=SIZE_RE.findall(raw)
    if len(matches)!=1:
        widths=re.findall(r"\bширина\s*[:–-]?\s*(\d{1,3})\s*(?:см|cm)?\b",raw,re.I)
        heights=re.findall(r"\bвысота\s*[:–-]?\s*(\d{1,3})\s*(?:см|cm)?\b",raw,re.I)
        if len(matches)==0 and len(widths)==1 and len(heights)==1:
            matches=[(widths[0],heights[0])]
        else:
            return {"status":"UNVERIFIED_PARSE","width_cm":None,"height_cm":None,"raw":raw}
    w,h=map(int,matches[0])
    if w<=0 or h<=0 or w>200 or h>300:
        return {"status":"UNVERIFIED_PARSE","width_cm":None,"height_cm":None,"raw":raw}
    return {"status":"PARSED_NEEDS_SELLER_CONFIRMATION","width_cm":w,"height_cm":h,"raw":raw}


def gallery_candidates(html: str, base: str, selector: str | None = None) -> dict:
    soup=BeautifulSoup(html,"html.parser")
    main=soup.find("main") or soup.find("article")
    if main is None: return {"status":"GALLERY_NOT_IDENTIFIED","items":[],"selector":selector}
    if selector:
        try: nodes=main.select(selector)
        except Exception: return {"status":"INVALID_GALLERY_SELECTOR","items":[],"selector":selector}
    else:
        containers=[]
        for tag in main.find_all(True):
            ident=" ".join([str(tag.get("class","")),str(tag.get("id","")),str(tag.get("data-testid",""))]).lower()
            if any(s in ident for s in GALLERY_HINTS) and tag.find("img"):
                containers.append(tag)
        # Prefer one shallow gallery root; multiple unrelated galleries => unsafe to decide.
        top=[t for t in containers if not any(p in containers for p in t.parents)]
        if len(top)!=1:
            return {"status":"GALLERY_AMBIGUOUS" if top else "GALLERY_NOT_IDENTIFIED","items":[],"selector":None,"root_count":len(top)}
        nodes=top[0].find_all("img")
    if not nodes:
        return {"status":"GALLERY_NOT_IDENTIFIED","items":[],"selector":selector}
    seen=set(); urls=[]
    for node in nodes:
        if getattr(node,"name",None)!="img": continue
        # DOM srcset may include bigger originally displayed frames; never rewrite CDN paths.
        candidates=[]
        for srcset_key in ("srcset","data-srcset"):
            srcset=node.get(srcset_key) or ""
            for fragment in srcset.split(","):
                if fragment.strip():
                    raw=fragment.strip().split()[0]
                    url=image_url_safe(raw,base)
                    if url: candidates.append((url,fragment.strip()))
        for key in ("src","data-src","data-original"):
            url=image_url_safe(node.get(key),base)
            if url: candidates.append((url,key))
        # Choose highest stated width, if present; don't invent an original URL.
        if not candidates: continue
        def rank(x):
            m=re.search(r"\b(\d{2,5})w\b",x[1])
            declared=int(m.group(1)) if m else 0
            dims=re.search(r"/(\d{2,5})x(\d{2,5})/",x[0])
            from_path=max(map(int,dims.groups())) if dims else 0
            return max(declared,from_path)
        url=max(candidates,key=rank)[0]
        if url not in seen:
            seen.add(url);urls.append(url)
    return {"status":"GALLERY_CANDIDATES_UNVERIFIED_COMPLETENESS" if urls else "GALLERY_NOT_IDENTIFIED",
            "items":urls[:60],"selector":selector,"candidate_count":len(urls),"truncated":len(urls)>60}


def detect_challenge(title: str, text: str) -> bool:
    lower=(title+"\n"+text[:1500]).lower()
    return any(w in lower for w in BLOCKED_HINTS)
