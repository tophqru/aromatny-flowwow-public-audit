"""Offline regressions from Windows checkout and a redacted live interstitial.

No challenge values, cookies, network calls or original DOM are retained here.
"""
import hashlib
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from parsing import detect_challenge
from capture import navigate, BrowserBlocked

INTERSTITIAL = '''<html><head><title></title></head><body>
<js-challenge-loader></js-challenge-loader>
<div id="id_captcha_frame_div" style="display:none"></div>
<script src="https://servicepipe.tech/static/checkjs/redacted.js"></script>
</body></html>'''

class LiveGateTests(unittest.TestCase):
    def test_empty_text_servicepipe_challenge_blocked(self):
        self.assertTrue(detect_challenge('', '', INTERSTITIAL))

    def test_hidden_captcha_frame_with_provider_blocked(self):
        self.assertTrue(detect_challenge('', '', INTERSTITIAL.replace(
            '<js-challenge-loader></js-challenge-loader>', '')))

    def test_ordinary_empty_spa_not_misclassified(self):
        self.assertFalse(detect_challenge('', '', '<body><div class="spinner"></div></body>'))

    def test_provider_script_without_challenge_not_blocked(self):
        self.assertFalse(detect_challenge('Product', 'Product',
            '<main><h1>Product</h1></main><script src="https://servicepipe.tech/a.js"></script>'))

    def test_provider_name_in_script_path_not_trusted(self):
        self.assertFalse(detect_challenge('', '', INTERSTITIAL.replace(
            'https://servicepipe.tech/', 'https://example.com/servicepipe.tech/')))

    def test_http_200_interstitial_stops_navigation(self):
        page=Mock(url='https://flowwow.com/flowers/avtorskiy-buket-s-gortenz-3168/')
        page.goto.return_value=SimpleNamespace(status=200)
        page.title.return_value=''
        page.locator.return_value.count.return_value=1
        page.locator.return_value.inner_text.return_value=''
        page.content.return_value=INTERSTITIAL
        with self.assertRaises(BrowserBlocked):
            navigate(page, page.url)
        page.goto.assert_called_once()

    def test_worktree_baseline_matches_independent_pinned_blob(self):
        repo=Path(__file__).resolve().parents[4]
        raw=(repo/'catalog/public-snapshot.json').read_bytes()
        sha=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        self.assertEqual(sha, 'b1ba9fbe10b7961d35a723d40af01686a0e10b78')

if __name__=='__main__':
    unittest.main()
