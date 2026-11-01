"""Minimal redacted structure from the permitted live desktop product.

No raw DOM, customer names, cookies, signed URLs or application state.
"""
import sys
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from flowwow_dom import layout_present, observed_sections, navigation_allowed
from parsing import SHOP, parse_composition, parse_dimensions
from unittest.mock import patch
from capture import click_seller_link
from flowwow_dom import frame_wait_budget, GalleryObservationError
import capture
from storage import Store

FIXTURE='''<div class="product-detail"><h1>Allowed product</h1>
<div class="right-content"><div class="properties">
<div class="property-item"><h3 class="property-name">Состав</h3><p class="pre-line"><span>Гортензия - 1 шт.
Эвкалипт - 7 шт.</span></p><a class="show-more">Скрыть</a></div>
<div class="property-item"><h3 class="property-name">Размер</h3><ul><li class="size-text">Ширина - 31 см</li><li class="size-text">Высота - 45 см</li></ul></div>
</div></div><div class="product-properties-general-desktop"><div class="property-item"><p class="pre-line"><span>Observed description</span></p></div></div>
<div class="product-properties-general"><div class="property-item">Hidden mobile duplicate</div></div>
</div><aside><h3>Состав</h3><p>Wrong product - 99 шт.</p></aside>'''

class ObservedDOMTests(unittest.TestCase):
    def test_slow_frame_wait_has_per_frame_and_total_bounds(self):
        self.assertEqual(frame_wait_budget(10,10),90000)
        self.assertEqual(frame_wait_budget(10,160),30000)
        with self.assertRaises(TimeoutError):frame_wait_budget(10,190)

    def test_partial_gallery_failure_retains_seller_without_captured_status(self):
        partial={'gallery':{'status':'PARTIAL_GALLERY_OBSERVATION','observed_total':6,
                            'frames':[{'index':0,'source_url':'https://content2.flowwow-images.com/a.jpg'}]},
                 'source_sections':observed_sections(FIXTURE),'ui_evidence':{'sections_expanded':True}}
        url='https://flowwow.com/flowers/avtorskiy-buket-s-gortenz-3168/'
        page=SimpleNamespace(url=url,content=lambda:FIXTURE,wait_for_timeout=Mock())
        seller={'status':'EXACT_SELLER_CLICK_VERIFIED','clicked':True,'final_url':SHOP}
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder);store=Store(out/'test.db')
            try:
                with patch('capture.navigate',return_value={'final_url':url}),patch('capture.click_seller_link',return_value=seller), \
                     patch('flowwow_dom.wait_layout_ready'),patch('flowwow_dom.observe_ui',side_effect=GalleryObservationError('IMAGE_DECODE_WAIT_FAILED_INDEX_1',partial)):
                    result=capture.record_product(page,Mock(),store,SimpleNamespace(),{'products':[]},url,'BASELINE_GAPS',out)
                self.assertEqual(store.page_rows()[0][3],'PARTIAL')
                self.assertEqual(result['seller'],seller)
                self.assertEqual(len(result['gallery']['frames']),1)
                self.assertFalse(result['may_order'])
                self.assertEqual(capture.pilot_acceptance(store,out)['status'],'BLOCKED')
            finally:store.close()
    def test_real_layout_without_main_supported(self):
        self.assertTrue(layout_present(FIXTURE))
        data=observed_sections(FIXTURE)
        self.assertEqual(data['description']['text'],'Observed description')
        self.assertEqual(len(parse_composition(data['composition']['text'])['items']),2)
        self.assertEqual(parse_dimensions(data['dimensions']['parser_text'])['width_cm'],31)
        self.assertIn('Ширина - 31 см',data['dimensions']['text'])
        self.assertNotIn('Wrong',data['composition']['text'])

    def test_duplicate_product_roots_fail_closed(self):
        self.assertFalse(layout_present(FIXTURE+FIXTURE))
        self.assertIsNone(observed_sections(FIXTURE+FIXTURE)['description']['text'])

    def test_duplicate_desktop_description_fail_closed(self):
        duplicate=FIXTURE.replace('Observed description','Different description')
        body=duplicate.split('<div class="product-properties-general-desktop">',1)[1].split('<div class="product-properties-general">',1)[0]
        changed=FIXTURE.replace('<div class="product-properties-general">','<div class="product-properties-general-desktop">'+body+'<div class="product-properties-general">')
        self.assertIsNone(observed_sections(changed)['description']['text'])

    def test_observed_seller_query_allowed(self):
        self.assertTrue(navigation_allowed(SHOP+'?from=product',set(),SHOP))
        self.assertTrue(navigation_allowed(SHOP,set(),SHOP))

    def test_unobserved_queries_and_foreign_shop_rejected(self):
        for url in (SHOP+'?from=other',SHOP+'?from=product&extra=1',SHOP+'orders/',
                    'https://flowwow.com/shop/other/?from=product'):
            self.assertFalse(navigation_allowed(url,set(),SHOP))

    def test_exact_sku_guard_preserved(self):
        target='https://flowwow.com/flowers/allowed/'
        self.assertTrue(navigation_allowed(target,{target},SHOP))
        self.assertFalse(navigation_allowed(target+'?extra=1',{target},SHOP))
        self.assertFalse(navigation_allowed('https://flowwow.com/flowers/other/',{target},SHOP))

    def test_delayed_popup_waits_without_second_click(self):
        from test_arena_review2_independent import SellerPage, PopupPage, PRODUCT
        page=SellerPage()
        count=[]
        def click(timeout=None):count.append('click')
        page._seller.click=click
        waits=[]
        def wait(ms):
            waits.append(ms)
            if len(waits)==8:page.context.pages.append(PopupPage(SHOP,page.context))
        page.wait_for_timeout=wait
        with patch('capture.navigate',return_value={}):result=click_seller_link(page,PRODUCT)
        self.assertEqual(result['status'],'EXACT_SELLER_CLICK_VERIFIED')
        self.assertEqual(count,['click'])
        self.assertEqual(len(waits),8)

if __name__=='__main__':unittest.main()
