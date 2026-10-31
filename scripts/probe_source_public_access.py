#!/usr/bin/env python3
"""Conservative one-shot diagnostic of publicly visible Flowwow item HTML.

No cookies/auth, no retries, no browser fingerprints, no challenge bypass.
Just log HTTP status and whether ordinary source information is available.
"""
import gzip
import json
import re
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

URLS = [
    "https://flowwow.com/flowers/avtorskiy-buket-s-gortenz-3168/",
    "https://flowwow.com/flowers/buket-gortenziy-23/",
    "https://flowwow.com/flowers/avtorskiy-buket-mattiol-roza-g/",
]
OUT = Path("flowwow-public-probe.json")

class TextReader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.ignore_depth = 0
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self.ignore_depth += 1
    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg"):
            self.ignore_depth = max(0, self.ignore_depth - 1)
    def handle_data(self, data):
        if not self.ignore_depth and data.strip():
            self.parts.append(data.strip())

def probe(url):
    req = urllib.request.Request(
        url, headers={
            "User-Agent": "Aromatny-Seller-Metadata-Check/1.0 (public item HTML; no authentication)",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Encoding": "gzip",
        })
    result = {"url": url, "http_status": None, "html_bytes": 0, "has_visible_composition": False,
              "has_next_data": False, "has_product_slug_in_html": False, "status": "UNREADABLE"}
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            data = response.read(2_000_001)
            if len(data) > 2_000_000:
                result["status"] = "TOO_LARGE"
                return result
            if response.headers.get("Content-Encoding", "").lower() == "gzip":
                data = gzip.decompress(data)
            html = data.decode("utf-8", errors="replace")
            reader = TextReader()
            reader.feed(html)
            visible = " ".join(reader.parts)
            result.update(http_status=response.status, html_bytes=len(data),
                          has_visible_composition="Состав" in visible,
                          has_next_data="__NEXT_DATA__" in html,
                          has_product_slug_in_html=url.rstrip("/").split("/")[-1] in html,
                          status="HTML_RETRIEVED" if response.status == 200 else "UNEXPECTED_RESPONSE",
                          title=" ".join(re.findall(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)[:1])[:240],
                          text_length=len(visible))
    except urllib.error.HTTPError as exc:
        result.update(http_status=exc.code, status="HTTP_BLOCK_OR_UNAVAILABLE")
    except (urllib.error.URLError, TimeoutError, ValueError, OSError, EOFError) as exc:
        result["status"] = "CONNECTION_ERROR"
        result["error_type"] = type(exc).__name__
    return result

if __name__ == "__main__":
    rows = []
    for n, url in enumerate(URLS):
        if n: time.sleep(3)
        row = probe(url)
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    OUT.write_text(json.dumps({"scope": "public_html_only_no_bypass", "results": rows},
                              ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # This probes access, not completeness or scraper correctness.
