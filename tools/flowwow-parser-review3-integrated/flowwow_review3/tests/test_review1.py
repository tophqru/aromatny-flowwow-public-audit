"""Additional independently written regression tests for the 2026-11-01 continuation.

No Flowwow network access; checks code paths, not a live-browser validation.
"""
from __future__ import annotations
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from parsing import SHOP, canonical_product, canonical_shop, image_url_safe
from storage import Store, atomic_bytes
from capture import (BrowserBlocked, LocalIntegrityError, download_assets, export,
                     needs_media_capture, record_product, safe_new_media_path,
                     verify_local_media)

SOURCE_URL="https://content2.flowwow-images.com/data/flowers/1000x1000/a.jpg"
PRODUCT="https://flowwow.com/flowers/buket-example/"

def previously_captured(downloads=None, seller="EXACT_SELLER_CLICK_VERIFIED"):
    return {"seller":{"status":seller},
            "gallery":{"status":"GALLERY_CANDIDATES_UNVERIFIED_COMPLETENESS",
                       "items":[SOURCE_URL,SOURCE_URL.replace('a.jpg','b.jpg')]},
            "image_downloads":downloads or []}

class NewSafetyTests(unittest.TestCase):
    def test_trial_without_media_is_rechecked_during_full_run(self):
        self.assertTrue(needs_media_capture(previously_captured(),30))

    def test_completed_media_need_not_be_refetched(self):
        downloads=[{"source_url":SOURCE_URL,"status":"NEW_ORIGINAL_FILE"},
                   {"source_url":SOURCE_URL.replace('a.jpg','b.jpg'),"status":"ALREADY_IN_PUBLIC_BASELINE"}]
        self.assertFalse(needs_media_capture(previously_captured(downloads),30))

    def test_failed_media_is_rechecked_during_full_run(self):
        downloads=[{"source_url":SOURCE_URL,"status":"UNVERIFIED_DOWNLOAD_ERROR"},
                   {"source_url":SOURCE_URL.replace('a.jpg','b.jpg'),"status":"NEW_ORIGINAL_FILE"}]
        self.assertTrue(needs_media_capture(previously_captured(downloads),30))

    def test_unverified_seller_is_not_auto_downloaded(self):
        self.assertFalse(needs_media_capture(previously_captured(seller="UNVERIFIED"),30))

    def test_media_recheck_respects_explicit_max_assets(self):
        downloads=[{"source_url":SOURCE_URL,"status":"NEW_ORIGINAL_FILE"}]
        self.assertFalse(needs_media_capture(previously_captured(downloads),1))
        self.assertTrue(needs_media_capture(previously_captured(downloads),2))

    def test_unexpected_ports_are_rejected(self):
        self.assertIsNone(canonical_product('https://flowwow.com:4443/flowers/buket-example/'))
        self.assertIsNone(canonical_shop('https://flowwow.com:4443/shop/lyubov-eto-699e0e4519/'))
        self.assertIsNone(image_url_safe('https://content2.flowwow-images.com:4443/a.jpg'))
        self.assertEqual(canonical_product('https://flowwow.com:443/flowers/buket-example/'),PRODUCT)

    def test_recovery_link_cannot_redirect_to_other_product(self):
        class SwitchedPage:
            url=PRODUCT
            def wait_for_timeout(self,*_): pass
            def content(self): return '<main><h1>Test</h1></main>'
        page=SwitchedPage()
        def wrong_navigation(page_arg,url_arg):
            page_arg.url='https://flowwow.com/flowers/other-seller-product/'
            return {'clicked':True,'status':'UNVERIFIED'}
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'progress.sqlite3')
            with patch('capture.navigate',return_value={'http_status':200,'final_url':PRODUCT}), \
                 patch('capture.click_seller_link',side_effect=wrong_navigation):
                with self.assertRaisesRegex(BrowserBlocked,'PRODUCT_URL_CHANGED_AFTER_SELLER'):
                    record_product(page,Mock(),store,SimpleNamespace(download_new_media=False,gallery_selector=None),
                                   {'products':[]},PRODUCT,'TEST',Path(folder))
            self.assertEqual(store.page_rows(),[])
            store.close()

    def test_path_traversal_database_asset_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)
            for attempt in ['../outside/private.txt','new-media/../../private.txt','/tmp/other.jpg']:
                with self.assertRaises(LocalIntegrityError):safe_new_media_path(out,attempt)

    def test_correct_preexisting_media_not_downloaded_again(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)
            data=b'valid previously saved bytes, not necessarily new download'
            target=out/'new-media'/'sku'/'media.jpg'
            atomic_bytes(target,data)
            store=Store(out/'db.sqlite3')
            sha=hashlib.sha256(data).hexdigest()
            store.record_asset('sku',SOURCE_URL,sha,'new-media/sku/media.jpg',len(data),640,640,'NEW_ORIGINAL_FILE')
            ctx=SimpleNamespace(request=Mock())
            result=download_assets(ctx,store,SimpleNamespace(max_gallery_assets=3,pause_min=0,pause_max=0),
                                   'sku',[SOURCE_URL],{'products':[]},out)
            self.assertEqual(result[0]['status'],'ALREADY_CAPTURED')
            ctx.request.get.assert_not_called()
            store.close()

    def test_corrupt_preexisting_media_halts_without_network(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)
            path='new-media/sku/media.jpg'
            atomic_bytes(out/path,b'corrupted')
            store=Store(out/'db.sqlite3')
            store.record_asset('sku',SOURCE_URL,'0'*64,path,9,640,640,'NEW_ORIGINAL_FILE')
            ctx=SimpleNamespace(request=Mock())
            with self.assertRaisesRegex(LocalIntegrityError,'LOCAL_MEDIA_SHA256_MISMATCH'):
                download_assets(ctx,store,SimpleNamespace(max_gallery_assets=3,pause_min=0,pause_max=0),
                                'sku',[SOURCE_URL],{'products':[]},out)
            ctx.request.get.assert_not_called()
            store.close()

    def test_export_detects_corrupt_new_media(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)
            store=Store(out/'progress.sqlite3')
            store.record_asset('sku',SOURCE_URL,'0'*64,'new-media/sku/media.jpg',7,640,640,'NEW_ORIGINAL_FILE')
            store.close()
            with self.assertRaises(LocalIntegrityError): export(SimpleNamespace(output=str(out)))
            self.assertFalse((out/'review'/'report.html').exists())

    def test_good_media_is_verified(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)
            data=b'my recorded file'
            atomic_bytes(out/'new-media'/'sku'/'media.jpg',data)
            sha=hashlib.sha256(data).hexdigest()
            self.assertEqual(verify_local_media(out,[(SOURCE_URL,'sku',sha,'new-media/sku/media.jpg',len(data),640,640,'NEW_ORIGINAL_FILE')]),1)

    def test_powershell_propagates_nonzero_capture_status(self):
        root=Path(__file__).resolve().parents[1]
        for name in ('run_full.ps1','run_trial.ps1'):
            content=(root/name).read_text(encoding='utf-8')
            self.assertIn('$crawlExitCode = $LASTEXITCODE',content)
            self.assertIn('if ($crawlExitCode -ne 0) { exit $crawlExitCode }',content)

# Integration-level regression: a trial capture is persisted, and the full-run
# control flow actually invokes the product handler again for missing media.
class ResumeIntegrationTests(unittest.TestCase):
    def test_crawl_revisits_trial_capture_for_media(self):
        from capture import crawl
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)
            store=Store(output/'progress.sqlite3')
            store.record_page(PRODUCT,'buket-example','BASELINE_66','CAPTURED',previously_captured())
            store.close()
            fakepage=SimpleNamespace(url=PRODUCT)
            fake_context=SimpleNamespace(pages=[fakepage],close=Mock())
            class FakeBrowser:
                def __enter__(self):return object()
                def __exit__(self,*args):return False
            args=SimpleNamespace(output=str(output),retry_failed=False,baseline=None,offline_baseline=False,
                                 max_products=0,max_categories=0,browser='chromium',skip_shop=True,
                                 download_new_media=True,max_gallery_assets=30,recheck_unverified=False,
                                 pause_min=0,pause_max=0)
            base={'seller':SHOP,'products':[{'slug':'buket-example','flowwow_url':PRODUCT,'seller_url':SHOP,'gallery':[]}]}
            with patch('capture.load_source',return_value=(base,[],{'mode':'MOCK'})), \
                 patch('capture.load_playwright',return_value=lambda:FakeBrowser()), \
                 patch('capture.launch_context',return_value=fake_context), \
                 patch('capture.gentle_wait',return_value=None), \
                 patch('capture.record_product',return_value={}) as recorded:
                code=crawl(args)
            self.assertEqual(code,0)
            recorded.assert_called_once()

    def test_dont_revisit_completed_capture(self):
        from capture import crawl
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)
            prev=previously_captured([
                {'source_url':SOURCE_URL,'status':'NEW_ORIGINAL_FILE'},
                {'source_url':SOURCE_URL.replace('a.jpg','b.jpg'),'status':'ALREADY_IN_PUBLIC_BASELINE'}])
            store=Store(output/'progress.sqlite3')
            store.record_page(PRODUCT,'buket-example','BASELINE_66','CAPTURED',prev)
            store.close()
            class FakeBrowser:
                def __enter__(self):return object()
                def __exit__(self,*args):return False
            args=SimpleNamespace(output=str(output),retry_failed=False,baseline=None,offline_baseline=False,
                                 max_products=0,max_categories=0,browser='chromium',skip_shop=True,
                                 download_new_media=True,max_gallery_assets=30,recheck_unverified=False,
                                 pause_min=0,pause_max=0)
            base={'seller':SHOP,'products':[{'slug':'buket-example','flowwow_url':PRODUCT,'seller_url':SHOP,'gallery':[]}]}
            with patch('capture.load_source',return_value=(base,[],{'mode':'MOCK'})), \
                 patch('capture.load_playwright',return_value=lambda:FakeBrowser()), \
                 patch('capture.launch_context',return_value=SimpleNamespace(pages=[object()],close=Mock())), \
                 patch('capture.record_product',return_value={}) as recorded:
                self.assertEqual(crawl(args),0)
            recorded.assert_not_called()


if __name__=='__main__': unittest.main()
