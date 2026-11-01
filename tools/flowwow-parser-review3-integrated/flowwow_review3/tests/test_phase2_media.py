import copy
import json
import hashlib
import io
from PIL import Image
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import phase2_media
from parsing import SHOP
from pilot_targets import EXACT_SLUGS

def proposal():
    return {'mode':'PHASE2_EXACT_MEDIA_ONLY','slug':EXACT_SLUGS[2],
        'owner_approved':False,'may_order':False,'may_show_publicly':False,
        'seller_evidence':{'status':'EXACT_SELLER_CLICK_VERIFIED','clicked':True,'final_url':SHOP+'?from=product'},
        'gallery_evidence':{'status':'ALL_GALLERY_FRAMES_OBSERVED','observed_total':1,'truncated':False,
                            'visited_original_urls':['https://content2.flowwow-images.com/a.jpg']}}

class Phase2Tests(unittest.TestCase):
    def test_exact_verified_plan_valid(self):
        self.assertEqual(len(phase2_media.validate_proposal(proposal())),1)
    def test_foreign_target_and_seller_fail(self):
        for key,value in [('slug',EXACT_SLUGS[0]),('seller_evidence',{'status':'UNVERIFIED'})]:
            doc=proposal();doc[key]=value
            with self.assertRaises(ValueError):phase2_media.validate_proposal(doc)
    def test_sale_flags_fail(self):
        for key in ('owner_approved','may_order','may_show_publicly'):
            doc=proposal();doc[key]=True
            with self.assertRaises(ValueError):phase2_media.validate_proposal(doc)
    def test_unsafe_url_and_duplicate_frames_fail(self):
        for urls in (['https://example.com/a.jpg'],['https://content2.flowwow-images.com/a.jpg']*2):
            doc=proposal();doc['gallery_evidence'].update(visited_original_urls=urls,observed_total=len(urls))
            with self.assertRaises(ValueError):phase2_media.validate_proposal(doc)
    def test_no_approval_never_downloads(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'manifest.json';path.write_text(json.dumps(proposal()))
            with patch('phase2_media.fetch_image') as fetch:
                with self.assertRaisesRegex(ValueError,'EXPLICIT_SAFE_TEST'):phase2_media.run(path,None,Path(folder)/'out')
                fetch.assert_not_called()
    def test_wrong_manifest_approval_never_downloads(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'manifest.json';path.write_text(json.dumps(proposal()))
            gate=Path(folder)/'approval.json';gate.write_text('{}')
            with patch('phase2_media.fetch_image') as fetch:
                with self.assertRaisesRegex(ValueError,'APPROVAL_MISMATCH'):phase2_media.run(path,gate,Path(folder)/'out')
                fetch.assert_not_called()

    def test_separately_gated_mocked_jpeg_decodes_and_preserves_bytes(self):
        buffer=io.BytesIO();Image.new('RGB',(500,500),'white').save(buffer,format='JPEG')
        data=buffer.getvalue()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'manifest.json';path.write_text(json.dumps(proposal()))
            gate=Path(folder)/'approval.json'
            gate.write_text(json.dumps({'authorization':'OWNER_EXPLICIT_MEDIA_ONLY_SAFE_TEST',
                'manifest_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'allowed_slug':EXACT_SLUGS[2],'max_requests':1}))
            with patch('phase2_media.fetch_image',return_value=data) as fetch:
                rows=phase2_media.run(path,gate,Path(folder)/'out')
            fetch.assert_called_once()
            self.assertEqual(rows[0]['sha256'],hashlib.sha256(data).hexdigest())
            self.assertEqual((Path(folder)/'out'/rows[0]['file']).read_bytes(),data)
            self.assertFalse(rows[0]['approved_for_sale'])

if __name__=='__main__':unittest.main()
