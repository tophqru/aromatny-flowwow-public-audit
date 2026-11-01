import unittest
from category_logic import discover_category_labels

class CategoryTests(unittest.TestCase):
 def test_nav_tabs(self):
  html='<main><div role="tablist"><button role="tab">Авторские букеты</button><button role="tab">Розы</button><button role="tab">Розы</button></div></main>'
  self.assertEqual(discover_category_labels(html),['Авторские букеты','Розы'])
 def test_reject_external_category(self):
  html='<main><a class="category" href="https://evil.example/shop/lyubov-eto-699e0e4519/">Fake</a><a class="category" href="/shop/other-seller/">Wrong seller</a><a class="category" href="/shop/lyubov-eto-699e0e4519/roses">Розы</a></main>'
  self.assertEqual(discover_category_labels(html),['Розы'])
 def test_dont_click_review_show_more(self):
  html='<main><button class="category">Показать ещё</button><button class="category">Отзывы</button></main>'
  self.assertEqual(discover_category_labels(html),[])
 def test_header_categories_not_counted(self):
  self.assertEqual(discover_category_labels('<nav><a class="category">Подарки</a></nav><main></main>'),[])

if __name__=='__main__':unittest.main()
