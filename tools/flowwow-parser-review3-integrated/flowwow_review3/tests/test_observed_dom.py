"""Minimal redacted structure from the permitted live desktop product.

No raw DOM, customer names, cookies, signed URLs or application state.
"""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from flowwow_dom import layout_present, observed_sections, navigation_allowed
from parsing import SHOP, parse_composition, parse_dimensions

FIXTURE='''<div class="product-detail"><h1>Allowed product</h1>
<div class="right-content"><div class="properties">
<div class="property-item"><h3 class="property-name">Состав</h3><p class="pre-line"><span>Гортензия - 1 шт.
Эвкалипт - 7 шт.</span></p><a class="show-more">Скрыть</a></div>
<div class="property-item"><h3 class="property-name">Размер</h3><ul><li class="size-text">Ширина - 31 см</li><li class="size-text">Высота - 45 см</li></ul></div>
</div></div><div class="product-properties-general-desktop"><div class="property-item"><p class="pre-line"><span>Observed description</span></p></div></div>
<div class="product-properties-general"><div class="property-item">Hidden mobile duplicate</div></div>
</div><aside><h3>Состав</h3><p>Wrong product - 99 шт.</p></aside>'''

class ObservedDOMTests(unittest.TestCase):
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

if __name__=='__main__':unittest.main()
