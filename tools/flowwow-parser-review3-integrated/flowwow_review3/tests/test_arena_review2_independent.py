"""ARENA independent REVIEW2 scenarios (offline only).

These tests were written from the published REVIEW2 source, not copied from the
author's test suite. They use fakes/mocks and subprocesses; none opens live Flowwow.
Run with: python -m unittest discover -s tests -v
"""
from __future__ import annotations
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import capture
import parsing
import scroll_logic
import category_logic
import storage
from storage import Store, atomic_bytes, exclusive_run_lock

SHOP = parsing.SHOP
PRODUCT = "https://flowwow.com/flowers/buket-example/"
IMG = "https://content2.flowwow-images.com/data/flowers/1000x1000/a.jpg"


class PopupPage:
    def __init__(self, url, context):
        self.url = url
        self.context = context

    def wait_for_load_state(self, *a, **k):
        return None

    def close(self):
        if self in self.context.pages:
            self.context.pages.remove(self)


class SellerContext:
    def __init__(self, page):
        self.pages = [page]


class SellerLocator:
    def __init__(self, page, href, new_tab=True):
        self.page = page
        self.href = href
        self.new_tab = new_tab

    def is_visible(self):
        return True

    def get_attribute(self, name):
        return self.href if name == "href" else None

    def inner_text(self, timeout=None):
        return "Перейти в магазин"

    def click(self, timeout=None):
        if self.new_tab:
            self.page.context.pages.append(PopupPage(self.href, self.page.context))
        else:
            self.page.url = self.href


class SellerLocatorSet:
    def __init__(self, items):
        self.items = items

    def all(self):
        return self.items


class BodyLocator:
    def count(self):
        return 0


class SellerPage:
    def __init__(self, target=SHOP, new_tab=True):
        self.url = PRODUCT
        self.context = SellerContext(self)
        self._seller = SellerLocator(self, target, new_tab)

    def locator(self, selector):
        if selector == "body":
            return BodyLocator()
        return SellerLocatorSet([self._seller])

    def wait_for_timeout(self, ms):
        return None

    def goto(self, url, **kwargs):
        self.url = url
        return SimpleNamespace(status=200)

    def title(self):
        return "Flowwow"

    def content(self):
        return "<main></main>"


class MoreButton:
    def __init__(self, page):
        self.page = page

    def is_visible(self):
        return True

    def is_enabled(self):
        return True

    def click(self, timeout=None):
        self.page.context.pages.append(PopupPage(SHOP, self.page.context))


class MainRoot:
    def __init__(self, page):
        self.page = page

    def count(self):
        return 1

    @property
    def first(self):
        return self

    def get_by_role(self, role, name=None):
        items = [MoreButton(self.page)] if role == "button" else []
        return SimpleNamespace(all=lambda: items)


class MorePage:
    def __init__(self, nested=False, short=False):
        self.url = SHOP
        self.context = SellerContext(self)
        self.nested = nested
        self.short = short

    def locator(self, selector):
        return MainRoot(self)

    def evaluate(self, script):
        height = 800 if self.short else 2400
        return {"y": 0, "height": height, "viewport": 800, "nested": self.nested}

    def content(self):
        return "<main></main>"

    def wait_for_timeout(self, ms):
        return None


class CLITests(unittest.TestCase):
    def test_doctor_without_site_packages_reports_missing_not_traceback(self):
        r = subprocess.run([sys.executable, "-S", str(ROOT / "capture.py"), "doctor"],
                           cwd=ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("MISSING", r.stdout)
        self.assertNotIn("Traceback", r.stderr)

    def test_crawl_without_dependencies_fails_friendly(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run([sys.executable, "-S", str(ROOT / "capture.py"), "crawl",
                                "--offline-baseline", "--output", tmp],
                               cwd=ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("Missing dependencies", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_review1_script_mode_runs_integration_tests(self):
        r = subprocess.run([sys.executable, str(ROOT / "tests" / "test_review1.py"), "-v"],
                           cwd=ROOT, capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ResumeIntegrationTests", r.stdout + r.stderr)


class SellerClickTests(unittest.TestCase):
    def test_popup_verification_does_not_reload_unchanged_product(self):
        page=SellerPage(target=SHOP,new_tab=True)
        with patch('capture.navigate') as navigate:
            result=capture.click_seller_link(page,PRODUCT)
        self.assertEqual(result['status'],'EXACT_SELLER_CLICK_VERIFIED')
        navigate.assert_not_called()
        self.assertEqual(page.url,PRODUCT)

    def test_same_tab_seller_click_restores_exact_product(self):
        page=SellerPage(target=SHOP,new_tab=False)
        def restore(p,url):p.url=url;return {}
        with patch('capture.navigate',side_effect=restore) as navigate:
            result=capture.click_seller_link(page,PRODUCT)
        self.assertEqual(result['status'],'EXACT_SELLER_CLICK_VERIFIED')
        navigate.assert_called_once_with(page,PRODUCT)
        self.assertEqual(page.url,PRODUCT)

    def test_seller_link_new_tab_is_verified(self):
        page = SellerPage(target=SHOP, new_tab=True)
        result = capture.click_seller_link(page, PRODUCT)
        self.assertEqual(result["status"], "EXACT_SELLER_CLICK_VERIFIED")
        self.assertTrue(result.get("opened_new_tab"))
        self.assertEqual(page.url, PRODUCT)

    def test_seller_link_new_tab_other_seller_rejected(self):
        page = SellerPage(target="https://flowwow.com/shop/other-shop/", new_tab=True)
        result = capture.click_seller_link(page, PRODUCT)
        self.assertEqual(result["status"], "DIFFERENT_OR_UNVERIFIED_SELLER")
        self.assertEqual(page.url, PRODUCT)


class ShopNavigationTests(unittest.TestCase):
    def test_show_more_new_tab_stops_not_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "p.sqlite3")
            page = MorePage(short=True)
            args = SimpleNamespace(max_load_cycles=3, max_scroll_steps=2,
                                   pause_min=0, pause_max=0)
            result = scroll_logic.expand_shop_conservatively(
                page, args, store, "ALL", lambda a: None)
            store.close()
        self.assertEqual(result["stop_reason"], "MORE_CONTROL_OPENED_NEW_TAB")
        self.assertFalse(result.get("complete", False))

    def test_same_shop_url_accepts_trailing_slash_and_subpath_only(self):
        self.assertTrue(parsing.same_shop_url(SHOP.rstrip("/")))
        self.assertTrue(parsing.same_shop_url(SHOP))
        self.assertTrue(parsing.same_shop_url(SHOP + "buket-example/"))
        self.assertFalse(parsing.same_shop_url("https://evil.com/shop/lyubov-eto-699e0e4519/"))
        self.assertFalse(parsing.same_shop_url("https://user:pass@flowwow.com/shop/lyubov-eto-699e0e4519/"))

    def test_nested_scroll_flag_not_short_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "p.sqlite3")
            found = set()
            result = scroll_logic.sweep_incrementally(MorePage(short=True), store, "ALL", found, max_steps=2)
            store.close()
        self.assertFalse(result["possible_nested_scroll"])

    def test_nested_scroll_flag_detects_container(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "p.sqlite3")
            found = set()
            result = scroll_logic.sweep_incrementally(MorePage(nested=True), store, "ALL", found, max_steps=2)
            store.close()
        self.assertTrue(result["possible_nested_scroll"])


class SecurityTests(unittest.TestCase):
    def test_export_report_rejects_javascript_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            store = Store(out / "progress.sqlite3")
            store.record_page("javascript:alert(1)", "evil", "BASELINE_66", "CAPTURED",
                              {"slug": "evil", "url": "javascript:alert(1)"})
            store.close()
            capture.export(SimpleNamespace(output=str(out)))
            html = (out / "review" / "report.html").read_text(encoding="utf-8")
        self.assertNotIn('href="javascript', html)
        self.assertIn("<span>evil</span>", html)

    def test_export_html_escapes_slug(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            store = Store(out / "progress.sqlite3")
            store.record_page(PRODUCT, "<script>alert(1)</script>", "BASELINE_66", "CAPTURED",
                              {"slug": "<script>alert(1)</script>", "url": PRODUCT})
            store.close()
            capture.export(SimpleNamespace(output=str(out)))
            html = (out / "review" / "report.html").read_text(encoding="utf-8")
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>alert(1)</script>", html)

    def test_download_assets_unsafe_url_no_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            store = Store(out / "p.sqlite3")
            get = Mock()
            context = SimpleNamespace(request=SimpleNamespace(get=get))
            args = SimpleNamespace(max_gallery_assets=10, pause_min=0, pause_max=0)
            results = capture.download_assets(context, store, args, "buket-example",
                                              ["http://169.254.169.254/latest/meta-data/"],
                                              {"products": []}, out)
            store.close()
        get.assert_not_called()
        self.assertEqual(results[0]["error_type"], "UNSAFE_IMAGE_URL")

    def test_image_redirect_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            store = Store(out / "p.sqlite3")
            resp = SimpleNamespace(status=301, ok=False, headers={}, body=Mock(return_value=b""))
            get = Mock(return_value=resp)
            context = SimpleNamespace(request=SimpleNamespace(get=get))
            args = SimpleNamespace(max_gallery_assets=10, pause_min=0, pause_max=0)
            with patch('capture.fetch_image',side_effect=RuntimeError('IMAGE_STATUS_301_NO_REDIRECTS')) as fetch:
                results = capture.download_assets(context, store, args, "buket-example",
                                                  [IMG], {"products": []}, out)
            store.close()
            self.assertEqual(fetch.call_count, 1)
            get.assert_not_called()
            self.assertEqual(results[0]["status"], "UNVERIFIED_DOWNLOAD_ERROR")
            self.assertFalse(list(out.glob("new-media/**/*")))

    def test_baseline_rejects_sale_flags_true(self):
        data = {"seller": SHOP, "products": [{"slug": "buket-example", "flowwow_url": PRODUCT,
                                              "seller_url": SHOP, "may_order": True}]}
        with self.assertRaises(RuntimeError):
            capture.validate_baseline(data)

    def test_baseline_excluded_sku_rejected(self):
        data = {"seller": SHOP, "products": [{"slug": "kompoziciya-v-shlyapnoy-k-4183",
                                              "flowwow_url": "https://flowwow.com/flowers/kompoziciya-v-shlyapnoy-k-4183/",
                                              "seller_url": SHOP}]}
        with self.assertRaises(RuntimeError):
            capture.validate_baseline(data)

    def test_canonical_product_rejects_homograph_host(self):
        self.assertIsNone(parsing.canonical_product("https://flowwow.com@evil.com/flowers/x/"))
        self.assertIsNone(parsing.canonical_product("https://flowwоw.com/flowers/x/"))

    def test_image_url_safe_rejects_private_and_data_urls(self):
        self.assertIsNone(parsing.image_url_safe("http://127.0.0.1/a.jpg"))
        self.assertIsNone(parsing.image_url_safe("data:image/jpeg;base64,AAAA"))
        self.assertIsNone(parsing.image_url_safe("javascript:alert(1)"))


class ParsingTests(unittest.TestCase):
    def test_gallery_truncation_flag(self):
        html = "<main>" + "".join(
            f'<img src="https://content2.flowwow-images.com/{i}.jpg">' for i in range(61)) + "</main>"
        result = parsing.gallery_candidates(html, PRODUCT, selector="img")
        self.assertEqual(result["candidate_count"], 61)
        self.assertEqual(len(result["items"]), 60)
        self.assertTrue(result["truncated"])

    def test_gallery_data_srcset_lazy(self):
        html = ('<main><img src="https://content2.flowwow-images.com/placeholder.jpg" '
                'data-srcset="https://content2.flowwow-images.com/1200x1200/original.jpg 1200w"></main>')
        result = parsing.gallery_candidates(html, PRODUCT, selector="img")
        self.assertIn("https://content2.flowwow-images.com/1200x1200/original.jpg", result["items"])

    def test_gallery_status_never_complete(self):
        html = '<main><img src="https://content2.flowwow-images.com/a.jpg"></main>'
        result = parsing.gallery_candidates(html, PRODUCT, selector="img")
        self.assertNotEqual(result["status"], "COMPLETE")
        self.assertIn("UNVERIFIED", result["status"])

    def test_dimensions_labelled_width_height(self):
        result = parsing.parse_dimensions("Ширина: 35 см. Высота: 45 см.")
        self.assertEqual(result["status"], "PARSED_NEEDS_SELLER_CONFIRMATION")
        self.assertEqual((result["width_cm"], result["height_cm"]), (35, 45))

    def test_dimensions_ambiguous_multiple_unverified(self):
        result = parsing.parse_dimensions("35×45 см и 50×60 см")
        self.assertEqual(result["status"], "UNVERIFIED_PARSE")

    def test_composition_decimal_quantity_unverified(self):
        result = parsing.parse_composition("Роза — 1.5 шт")
        self.assertEqual(result["status"], "UNVERIFIED_PARSE")

    def test_category_labels_ignore_show_more_and_external(self):
        html = ('<main><button role="tab">Показать ещё</button>'
                '<a role="tab" href="https://evil.com/shop/x/">Внешняя</a>'
                '<button role="tab">Букеты</button></main>')
        self.assertEqual(category_logic.discover_category_labels(html), ["Букеты"])


class StorageResumeTests(unittest.TestCase):
    def test_atomic_bytes_fsyncs_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "file.bin"
            operations = []
            real_fsync, real_replace = os.fsync, os.replace
            def sync_file(fd):
                operations.append("fsync")
                return real_fsync(fd)
            def replace_file(source, destination):
                self.assertEqual(operations, ["fsync"])
                operations.append("replace")
                return real_replace(source, destination)
            with patch("storage.os.fsync", side_effect=sync_file) as fsync, \
                    patch("storage.os.replace", side_effect=replace_file):
                atomic_bytes(path, b"payload")
            # Windows cannot fsync directory handles via os.open; production
            # deliberately syncs only the file there. POSIX syncs both.
            self.assertEqual(fsync.call_count, 1 if os.name == "nt" else 2)
            self.assertEqual(operations, ["fsync", "replace"] if os.name == "nt"
                             else ["fsync", "replace", "fsync"])
            self.assertEqual(path.read_bytes(), b"payload")

    def test_atomic_bytes_cyrillic_space_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "каталог с пробелом" / "файл.bin"
            atomic_bytes(path, "данные".encode("utf-8"))
            self.assertEqual(path.read_bytes(), "данные".encode("utf-8"))

    def test_sqlite_cyrillic_space_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "база данных" / "p.sqlite3"
            store = Store(path)
            store.record_page(PRODUCT, "buket-example", "BASELINE_66", "CAPTURED", {"ok": True})
            rows = store.page_rows()
            store.close()
        self.assertEqual(len(rows), 1)

    def test_sqlite_wal_reopen_preserves_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "p.sqlite3"
            store = Store(path)
            store.record_page(PRODUCT, "buket-example", "BASELINE_66", "CAPTURED", {"ok": True})
            store.close()
            store2 = Store(path)
            rows = store2.page_rows()
            store2.close()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], "buket-example")

    def test_exclusive_lock_released_after_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp) / "run.lock"
            with self.assertRaises(ValueError):
                with exclusive_run_lock(lock):
                    raise ValueError("boom")
            with exclusive_run_lock(lock):
                pass

    def test_needs_media_capture_detects_missing_local_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            result = {"seller": {"status": "EXACT_SELLER_CLICK_VERIFIED"},
                      "gallery": {"status": "GALLERY_CANDIDATES_UNVERIFIED_COMPLETENESS",
                                  "items": [IMG]},
                      "image_downloads": [{"source_url": IMG, "status": "NEW_ORIGINAL_FILE",
                                           "relative_path": "new-media/buket-example/001-abc.jpg",
                                           "sha256": "0" * 64}]}
            self.assertTrue(capture.needs_media_capture(result, 10, out))

    def test_needs_media_capture_accepts_present_local_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            rel = "new-media/buket-example/001-abc.jpg"
            target = out / rel
            target.parent.mkdir(parents=True)
            target.write_bytes(b"jpeg-bytes")
            import hashlib
            sha = hashlib.sha256(b"jpeg-bytes").hexdigest()
            result = {"seller": {"status": "EXACT_SELLER_CLICK_VERIFIED"},
                      "gallery": {"status": "GALLERY_CANDIDATES_UNVERIFIED_COMPLETENESS",
                                  "items": [IMG]},
                      "image_downloads": [{"source_url": IMG, "status": "NEW_ORIGINAL_FILE",
                                           "relative_path": rel, "sha256": sha}]}
            self.assertFalse(capture.needs_media_capture(result, 10, out))


class WindowsScriptTests(unittest.TestCase):
    def test_setup_windows_does_not_claim_success_without_browser(self):
        content = (ROOT / "setup_windows.ps1").read_text(encoding="utf-8")
        self.assertIn("$browserReady", content)
        self.assertIn("if ($browserReady)", content)
        self.assertIn("SETUP PARTIAL", content)


if __name__ == "__main__":
    unittest.main()
