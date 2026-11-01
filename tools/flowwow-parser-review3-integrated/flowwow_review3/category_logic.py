"""Conservative shop-category names from explicitly marked navigation controls.

Not a proof that all seller categories are present in the rendered DOM.
"""
from __future__ import annotations
from bs4 import BeautifulSoup
from parsing import canonical_shop, SHOP
from scroll_logic import SHOW_MORE


def discover_category_labels(html:str, page_url:str=SHOP)->list[str]:
    soup=BeautifulSoup(html,'html.parser')
    main=soup.find('main')
    if not main:return []
    found=[];seen=set()
    for el in main.select('[role="tab"], [data-testid*="category" i], [class*="category" i]'):
        if el.name not in ('a','button') and el.get('role')!='tab':continue
        text=el.get_text(' ',strip=True)
        if not (2<=len(text)<=70) or SHOW_MORE.fullmatch(text) or text.lower() in ('все','главная','отзывы','каталог'):
            continue
        # Category links must stay inside this exact shop. Buttons/tabs don't navigate via an href.
        href=el.get('href')
        if href:
            # Keep category URLs only under the same canonical shop prefix.
            from urllib.parse import urljoin,urlsplit
            u=urlsplit(urljoin(page_url,href));base=urlsplit(SHOP)
            if u.scheme!='https' or u.hostname not in ('flowwow.com','www.flowwow.com') or u.port not in (None,443) or not u.path.startswith(base.path):continue
        key=text.casefold()
        if key not in seen:seen.add(key);found.append(text)
    return found
