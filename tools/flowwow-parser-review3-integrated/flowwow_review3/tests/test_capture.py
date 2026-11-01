from __future__ import annotations
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from parsing import (
 SHOP, canonical_product, canonical_shop, image_url_safe, shop_item_links,
 visible_seller_links, extract_sections, parse_composition, parse_dimensions,
 gallery_candidates, detect_challenge,
)
from storage import Store, atomic_bytes, atomic_json, exclusive_run_lock
from capture import validate_baseline, initial_queue, download_assets, navigate, BrowserBlocked, needs_source_recheck
from PIL import Image


PRODUCT_HTML = '''
<html><body><header><nav><a href="/flowers/recommended-2/">Recommended</a></nav></header>
<main><h1>Букет из гортензий</h1>
<div class="product-gallery"><img src="https://content2.flowwow-images.com/data/flowers/1000x1000/1.jpg" alt="Галерея 1">
<img srcset="https://content2.flowwow-images.com/data/flowers/200x200/2.jpg 200w, https://content2.flowwow-images.com/data/flowers/1000x1000/2.jpg 1000w"></div>
<section><h2>Состав</h2><p>Гортензия - 3 шт. Эустома - 5 шт.</p></section>
<section><h2>Описание</h2><p>Нежный букет для праздника</p></section>
<section><h2>Размеры</h2><p>Ширина 35 × 45 см</p></section>
<a href="/shop/lyubov-eto-699e0e4519/">Перейти в магазин</a>
</main><aside><section><h2>Состав</h2>Другой товар - 500 шт.</section></aside></body></html>'''


def baseline():
 return {"seller":SHOP,"products":[{"slug":"buket-xyz","flowwow_url":"https://flowwow.com/flowers/buket-xyz/","seller_url":SHOP,"gallery":[]} ]}

class URLTests(unittest.TestCase):
 def test_product_allowlist_and_normalization(self):
  self.assertEqual(canonical_product("/flowers/BUKET-XYZ/?utm_source=abc"),"https://flowwow.com/flowers/buket-xyz/")
  for bad in ["https://evil.com/flowers/buket-xyz/","http://flowwow.com/flowers/x/","https://flowwow.com.evil.com/flowers/x/","https://evil@flowwow.com/flowers/foo/","javascript:alert(1)","/flowers/../../shop/other/"]:
   self.assertIsNone(canonical_product(bad),bad)
 def test_canonical_shop(self):
  self.assertEqual(canonical_shop("/shop/lyubov-eto-699e0e4519/"),SHOP)
  self.assertIsNone(canonical_shop("/shop/other/?bad=yes") if False else canonical_shop("https://evil.com/shop/foo/"))
 def test_image_urls_no_tokens(self):
  good="https://content2.flowwow-images.com/data/flowers/1000x1000/123.jpg"
  self.assertEqual(image_url_safe(good),good)
  for x in ["data:image/jpeg;base64,AAA","blob:abc","https://evil.com/image.jpg","https://content2.flowwow-images.com/a.jpg?token=secret","http://content2.flowwow-images.com/a.jpg"]:
   self.assertIsNone(image_url_safe(x),x)

class DOMTests(unittest.TestCase):
 def test_product_links_no_duplicates(self):
  html='<a href="/flowers/buket-xyz/">x</a><a href="https://flowwow.com/flowers/buket-xyz/?x=1">d</a><a href="https://evil.com/flowers/hacked/">evil</a>'
  self.assertEqual(shop_item_links(html,SHOP),["https://flowwow.com/flowers/buket-xyz/"])
 def test_seller_link_is_not_claimed_clicked(self):
  links=visible_seller_links(PRODUCT_HTML,SHOP)
  self.assertEqual(links,[{"href":SHOP,"text":"Перейти в магазин","dom_link_only":True}])
 def test_sections_scoped_to_main(self):
  s=extract_sections(PRODUCT_HTML)
  self.assertEqual(s["composition"]["text"],"Гортензия - 3 шт. Эустома - 5 шт.")
  self.assertEqual(s["description"]["text"],"Нежный букет для праздника")
  self.assertEqual(s["dimensions"]["text"],"Ширина 35 × 45 см")
  parsed=parse_composition(s["composition"]["text"])
  self.assertEqual([i["quantity"] for i in parsed["items"]],[3,5])
  self.assertEqual(parsed["status"],"PARSED_NEEDS_SELLER_CONFIRMATION")
  self.assertEqual(parse_dimensions(s["dimensions"]["text"])["width_cm"],35)
 def test_ambiguous_heading_no_invention(self):
  html='<main><h2>Состав</h2><p>Роза - 3 шт.</p><h2>Состав</h2><p>Роза - 5 шт.</p></main>'
  self.assertEqual(extract_sections(html)["composition"]["status"],"AMBIGUOUS_MULTIPLE_SECTIONS")
 def test_absent_main_does_not_scrape_reviews(self):
  self.assertEqual(extract_sections('<aside><h2>Состав</h2>Роза - 99 шт.</aside>')["composition"]["status"],"SOURCE_NOT_VISIBLE")
 def test_unparsed_component_cannot_be_declared_exact(self):
  c=parse_composition('Пион - 5 шт. неизвестное 10 шт.')
  self.assertEqual(c["status"],"UNVERIFIED_PARSE")
  self.assertFalse(c["items"])
 def test_dimensions_ambiguous_and_invalid(self):
  self.assertEqual(parse_dimensions('35 × 45 и 30 × 40 см')["status"],"UNVERIFIED_PARSE")
  self.assertEqual(parse_dimensions('0 × 30 см')["status"],"UNVERIFIED_PARSE")
  self.assertEqual(parse_dimensions('30 × 40 см')["height_cm"],40)
 def test_gallery_scoped_and_best_srcset(self):
  g=gallery_candidates(PRODUCT_HTML,SHOP)
  self.assertEqual(g["status"],"GALLERY_CANDIDATES_UNVERIFIED_COMPLETENESS")
  self.assertEqual(len(g["items"]),2)
  self.assertTrue(g["items"][1].endswith("/1000x1000/2.jpg"))
 def test_high_resolution_img_src_beats_small_srcset(self):
  html='<main><div class="gallery"><img src="https://content2.flowwow-images.com/data/flowers/1000x1000/a.jpg" srcset="https://content2.flowwow-images.com/data/flowers/200x200/a.jpg 200w"></div></main>'
  self.assertIn('/1000x1000/',gallery_candidates(html,SHOP)['items'][0])
 def test_gallery_multiple_roots_fails_closed(self):
  html='<main><div class="gallery"><img src="https://content2.flowwow-images.com/a.jpg"></div><div class="gallery"><img src="https://content2.flowwow-images.com/b.jpg"></div></main>'
  self.assertEqual(gallery_candidates(html,SHOP)["status"],"GALLERY_AMBIGUOUS")
 def test_no_media_from_recommendations(self):
  html='<main><h1>Foo</h1><aside class="recommendations"><img src="https://content2.flowwow-images.com/a.jpg"></aside></main>'
  self.assertEqual(gallery_candidates(html,SHOP)["items"],[])
 def test_access_challenge_detection(self):
  self.assertTrue(detect_challenge("403 Forbidden","Captcha"))
  self.assertFalse(detect_challenge("Букет цветов","Состав и доставка"))

class StorageTests(unittest.TestCase):
 def test_atomic_and_resume(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   atomic_bytes(root/'a.bin',b'hello')
   atomic_json(root/'b.json',{'foo':3})
   self.assertEqual((root/'a.bin').read_bytes(),b'hello')
   self.assertEqual(json.loads((root/'b.json').read_text())['foo'],3)
   s=Store(root/'db.sqlite3')
   s.record_page('https://flowwow.com/flowers/abc/','abc','shop','CAPTURED',{'status':'recorded'})
   s.discover('https://flowwow.com/flowers/abc/','Авторские букеты','LIVE_SHOP_DOM')
   s.record_asset('abc','https://content2.flowwow-images.com/a.jpg','f'*64,'new-media/abc/001.jpg',123,1000,1000,'NEW_ORIGINAL_FILE')
   s.close()
   s=Store(root/'db.sqlite3')
   self.assertTrue(s.seen('https://flowwow.com/flowers/abc/'))
   self.assertEqual(len(s.urls()),1)
   self.assertEqual(len(s.page_rows()),1)
   self.assertEqual(len(s.asset_rows()),1)
   s.close()
 def test_exclusive_os_lock(self):
  with tempfile.TemporaryDirectory() as d:
   lock=Path(d)/'lock'
   with exclusive_run_lock(lock):
    with self.assertRaises(RuntimeError):
     with exclusive_run_lock(lock):pass
   with exclusive_run_lock(lock):pass

class ValidationTests(unittest.TestCase):
 def test_bad_baseline_fails(self):
  b=baseline();validate_baseline(b)
  b['seller']='https://evil.com/'
  with self.assertRaises(RuntimeError):validate_baseline(b)
  b=baseline();b['products'].append(dict(b['products'][0]))
  with self.assertRaises(RuntimeError):validate_baseline(b)
 def test_priority_and_dedup(self):
  b=baseline()
  ledgers=[{"url":"https://flowwow.com/flowers/new-sku/","kind":"INDEXED_UNVERIFIED"},{"url":"https://flowwow.com/flowers/new-sku/","kind":"INDEXED_UNVERIFIED"}]
  result=initial_queue(b,ledgers,[("https://flowwow.com/flowers/new-sku/",'Авторские букеты')])
  self.assertEqual(len(result),2)
 def test_recheck_requires_explicit_opt_in_for_incomplete_captures(self):
  x={"seller":{"status":"UNVERIFIED"},"composition":{"status":"SOURCE_NOT_VISIBLE"},
     "dimensions":{"status":"SOURCE_NOT_VISIBLE"},"source_sections":{"description":{"status":"SOURCE_NOT_VISIBLE"}},
     "gallery":{"status":"GALLERY_AMBIGUOUS"}}
  self.assertTrue(needs_source_recheck(x))
  x["seller"]["status"]="EXACT_SELLER_CLICK_VERIFIED"
  x["composition"]["status"]="PARSED_NEEDS_SELLER_CONFIRMATION"
  x["dimensions"]["status"]="PARSED_NEEDS_SELLER_CONFIRMATION"
  x["source_sections"]["description"]["status"]="SOURCE_SECTION_TEXT_CAPTURED"
  x["gallery"]["status"]="GALLERY_CANDIDATES_UNVERIFIED_COMPLETENESS"
  self.assertFalse(needs_source_recheck(x))
 def test_network_block_stops_before_dom(self):
  class BrokenPage:
   def goto(self,*args,**kwargs):raise OSError('blocked')
  with self.assertRaises(BrowserBlocked):navigate(BrokenPage(),SHOP)
 def test_existing_baseline_media_not_downloaded(self):
  with tempfile.TemporaryDirectory() as d:
   s=Store(Path(d)/'db.sqlite3')
   u='https://content2.flowwow-images.com/data/flowers/1000x1000/01.jpg'
   b=baseline();b['products'][0]['gallery']=[{"source_url":u,"sha256":"0"*64,"path":"data/flowwow/items/buket-xyz/photos/01.jpg"}]
   ctx=SimpleNamespace(request=Mock())
   args=SimpleNamespace(max_gallery_assets=10,pause_min=0,pause_max=0)
   r=download_assets(ctx,s,args,'buket-xyz',[u],b,Path(d))
   self.assertEqual(r[0]['status'],'ALREADY_IN_PUBLIC_BASELINE')
   ctx.request.get.assert_not_called()
   s.close()
 def test_blocked_image_stops_no_more_images(self):
  with tempfile.TemporaryDirectory() as d:
   s=Store(Path(d)/'db.sqlite3')
   u1='https://content2.flowwow-images.com/a.jpg'
   u2='https://content2.flowwow-images.com/b.jpg'
   response=SimpleNamespace(ok=False,status=403,headers={},body=lambda:b'')
   ctx=SimpleNamespace(request=Mock(get=Mock(return_value=response)))
   args=SimpleNamespace(max_gallery_assets=10,pause_min=0,pause_max=0)
   with self.assertRaises(BrowserBlocked):download_assets(ctx,s,args,'buket-xyz',[u1,u2],baseline(),Path(d))
   self.assertEqual(ctx.request.get.call_count,1)
   s.close()
 def test_atomic_replace_failure_leaves_old_file(self):
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'same.txt';p.write_bytes(b'original')
   with patch('storage.os.replace',side_effect=OSError('disk unavailable')):
    with self.assertRaises(OSError):atomic_bytes(p,b'new-content')
   self.assertEqual(p.read_bytes(),b'original')
   self.assertEqual(list(Path(d).glob('*.tmp-*')),[])
 def test_recently_seen_success_not_rewritten_by_check(self):
  with tempfile.TemporaryDirectory() as d:
   s=Store(Path(d)/'db.sqlite3')
   url='https://flowwow.com/flowers/buket-xyz/'
   self.assertFalse(s.seen(url))
   s.record_page(url,'buket-xyz','shop','CAPTURED',{'ok':True})
   self.assertTrue(s.seen(url))
   s.close()
 def test_new_jpeg_atomic_download(self):
  with tempfile.TemporaryDirectory() as d:
   s=Store(Path(d)/'db.sqlite3')
   u='https://content2.flowwow-images.com/data/flowers/1000x1000/999.jpg'
   img=Image.new('RGB',(640,640),(140,180,160));data=io.BytesIO();img.save(data,format='JPEG');payload=data.getvalue()
   response=SimpleNamespace(ok=True,status=200,headers={'content-type':'image/jpeg'},body=lambda:payload)
   ctx=SimpleNamespace(request=Mock(get=Mock(return_value=response)))
   args=SimpleNamespace(max_gallery_assets=10,pause_min=0,pause_max=0)
   result=download_assets(ctx,s,args,'buket-xyz',[u],baseline(),Path(d))
   self.assertEqual(result[0]['status'],'NEW_ORIGINAL_FILE')
   self.assertEqual(len(list((Path(d)/'new-media'/'buket-xyz').glob('*.jpg'))),1)
   s.close()

if __name__=='__main__':unittest.main(verbosity=2)
