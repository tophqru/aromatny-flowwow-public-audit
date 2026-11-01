import unittest
from types import SimpleNamespace
from unittest.mock import patch
from scroll_logic import (scan_links, sweep_incrementally, visible_more_controls, expand_shop_conservatively)

SHOP='https://flowwow.com/shop/lyubov-eto-699e0e4519/'

def item(n): return f'<a href="/flowers/buket-{n}/">{n}</a>'

class FakeLocator:
    def __init__(self,buttons): self.buttons=buttons
    def count(self): return 1
    @property
    def first(self): return self
    def get_by_role(self,role,name=None):
        return SimpleNamespace(all=lambda:[x for x in self.buttons if x.role==role and name.search(x.label)])

class FakeButton:
    def __init__(self,page,label,role='button'):
        self.page=page;self.label=label;self.role=role
    def is_visible(self): return True
    def is_enabled(self): return True
    def click(self,timeout=7000): self.page.clicks+=1;self.page.mode+=1;self.page.pos=0

class Page:
    url=SHOP
    def __init__(self,groups,*,infinite=False,controls=True,virtual=False):
        self.groups=groups;self.mode=0;self.pos=0;self.clicks=0;self.infinite=infinite;self.virtual=virtual
        self.buttons=[FakeButton(self,'Показать ещё')] if controls else []
    def content(self):
        items=self.groups[min(self.mode,len(self.groups)-1)]
        if self.virtual: items=items[max(0,self.pos-1):self.pos+1]
        else: items=items[:self.pos+1]
        return '<main>'+''.join(map(item,items))+'</main>'
    def evaluate(self,js):
        self.pos+=1
        return dict(y=self.pos*100,height=(10000 if self.infinite else max(200,(len(self.groups[self.mode])+5)*100)),viewport=400)
    def wait_for_timeout(self,ms): pass
    def locator(self,selector):
        return FakeLocator(self.buttons if self.mode<len(self.groups)-1 else [])

class Store:
    def __init__(self):self.urls=set();self.events=[]
    def discover(self,u,c,m):self.urls.add(u)
    def event(self,kind,data):self.events.append((kind,data))

class ScrollTests(unittest.TestCase):
    def test_incremental_sweep_collects_intermediate_virtualized_items(self):
        p=Page([['a','b','c','d','e']],virtual=True);s=Store();found=set()
        result=sweep_incrementally(p,s,'all',found,max_steps=12,delay_ms=0)
        self.assertEqual(len(found),5)
        self.assertTrue(result['observed_document_bottom'])
    def test_scroll_budget_hit_never_claims_complete(self):
        p=Page([['a']],infinite=True);s=Store()
        result=expand_shop_conservatively(p,SimpleNamespace(max_scroll_steps=3,max_load_cycles=4),s,'all',lambda _:None)
        self.assertEqual(result['stop_reason'],'SCROLL_STEP_LIMIT_REACHED')
        self.assertFalse(result['end_of_category_proven'])
    def test_show_more_click_then_scroll_new_items(self):
        p=Page([['a','b'],['a','b','c','d']]);s=Store()
        result=expand_shop_conservatively(p,SimpleNamespace(max_scroll_steps=10,max_load_cycles=5),s,'all',lambda _:None)
        self.assertEqual(result['show_more_clicks'],1)
        self.assertEqual(result['observed_product_links'],4)
        self.assertFalse(result['end_of_category_proven'])
    def test_ambiguous_more_controls_fail_closed(self):
        p=Page([['a'],['a','b']]);p.buttons.append(FakeButton(p,'Загрузить ещё'));s=Store()
        result=expand_shop_conservatively(p,SimpleNamespace(max_scroll_steps=10,max_load_cycles=5),s,'all',lambda _:None)
        self.assertEqual(result['stop_reason'],'AMBIGUOUS_SHOW_MORE_CONTROLS')
        self.assertEqual(p.clicks,0)
    def test_missing_main_does_not_click_header(self):
        p=Page([['a']]);p.locator=lambda s: SimpleNamespace(count=lambda:0);s=Store()
        result=expand_shop_conservatively(p,SimpleNamespace(max_scroll_steps=10,max_load_cycles=3),s,'all',lambda _:None)
        self.assertEqual(result['stop_reason'],'MAIN_NOT_UNAMBIGUOUS')
        self.assertEqual(p.clicks,0)
    def test_link_more_is_supported(self):
        p=Page([['a'],['a','b']]);p.buttons=[FakeButton(p,'Load more products','link')];s=Store()
        result=expand_shop_conservatively(p,SimpleNamespace(max_scroll_steps=10,max_load_cycles=5),s,'all',lambda _:None)
        self.assertEqual(result['show_more_clicks'],1)
        self.assertIn(item('b').split('"')[1].replace('/flowers/','https://flowwow.com/flowers/'),s.urls)
    def test_more_control_redirect_to_other_seller_stops_before_discovery(self):
        p=Page([['a'],['a','b']]);s=Store()
        def redirect(timeout=7000):
            p.clicks+=1;p.url='https://flowwow.com/shop/other-seller/'
        p.buttons[0].click=redirect
        result=expand_shop_conservatively(p,SimpleNamespace(max_scroll_steps=10,max_load_cycles=5),s,'all',lambda _:None)
        self.assertEqual(result['stop_reason'],'MORE_CONTROL_NAVIGATED_OUTSIDE_SHOP')
        self.assertEqual(result['observed_product_links'],1)
        self.assertFalse(result['end_of_category_proven'])

    def test_unrelated_button_not_clicked(self):
        p=Page([['a']]);p.buttons=[FakeButton(p,'Показать отзывы')];s=Store()
        result=expand_shop_conservatively(p,SimpleNamespace(max_scroll_steps=10,max_load_cycles=5),s,'all',lambda _:None)
        self.assertEqual(p.clicks,0)
        self.assertEqual(result['stop_reason'],'NO_MORE_VISIBLE_CONTROL_STABLE_NOT_PROVEN_COMPLETE')

if __name__=='__main__':unittest.main()
