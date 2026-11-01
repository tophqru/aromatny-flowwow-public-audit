import copy
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import capture
from pilot_targets import PilotGuardError, read_pilot_manifest, verify_pilot_db
from storage import Store

PUB='864f6e222ea58cfed063f6594f896edb67ed8e7f'
PRIV='ac74ac06983eff5b4cdd72e8cd11433baf1d7240'
S1='avtorskiy-buket-s-gortenz-3168'
S2='buket-gortenziy-23'
S3='buket-gortenziy-pionov-roz-eus'

def m():
    return {'schema_version':1, 'shop_url':'https://flowwow.com/shop/lyubov-eto-699e0e4519/',
        'safe_to_publish':False,'may_order':False,'owner_approved':False,
        'baseline_public':{'repo':'tophqru/aromatny-flowwow-public-audit','commit':PUB},
        'private_reference':{'repo':'tophqru/flower-shop','commit':PRIV},
        'exact_trial':[
            {'slug':S1,'url':f'https://flowwow.com/flowers/{S1}/','kind':'BASELINE_GAPS'},
            {'slug':S2,'url':f'https://flowwow.com/flowers/{S2}/','kind':'BASELINE_GAPS'},
            {'slug':S3,'url':f'https://flowwow.com/flowers/{S3}/','kind':'PENDING_SELLER_VERIFIED_METADATA_ONLY'}]}

def baseline():return {'products':[{'slug':s,'flowwow_url':f'https://flowwow.com/flowers/{s}/'} for s in [S1,S2]]}

class TestPilot(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'manifest.json'
        self.m=m();self.snapshot=baseline()
    def tearDown(self):self.tmp.cleanup()
    def check(self,m=None):
        raw=json.dumps(self.snapshot).encode('utf-8')
        obj=self.m if m is None else m
        obj.setdefault('baseline_public',{})['git_blob_sha']=hashlib.sha1(f'blob {len(raw)}\0'.encode('ascii')+raw).hexdigest()
        self.path.write_text(json.dumps(obj,ensure_ascii=False),encoding='utf-8')
        return read_pilot_manifest(self.path,self.snapshot,expected_public_commit=PUB,expected_private_commit=PRIV,baseline_bytes=raw)
    def test_exact_three_order(self):
        rows,sha=self.check();self.assertEqual(3,len(rows));self.assertEqual(rows[-1][0],self.m['exact_trial'][2]['url']);self.assertEqual(64,len(sha))
    def test_wrong_seller(self):
        self.m['shop_url']='https://flowwow.com/shop/other/';self.assertRaises(PilotGuardError,self.check)
    def test_pinned_blob_changed(self):
        raw=json.dumps(self.snapshot).encode('utf-8')
        self.m['baseline_public']['git_blob_sha']='f'*40
        self.path.write_text(json.dumps(self.m),encoding='utf-8')
        with self.assertRaises(PilotGuardError):
            read_pilot_manifest(self.path,self.snapshot,expected_public_commit=PUB,expected_private_commit=PRIV,baseline_bytes=raw)
    def test_wrong_pinned_commit(self):
        self.m['private_reference']['commit']='0'*40;self.assertRaises(PilotGuardError,self.check)
    def test_wrong_public_repo(self):
        self.m['baseline_public']['repo']='evil/evil';self.assertRaises(PilotGuardError,self.check)
    def test_sale_flags(self):
        for k in ['safe_to_publish','owner_approved','may_order']:
            m=copy.deepcopy(self.m);m[k]=True
            self.assertRaises(PilotGuardError,self.check,m)
    def test_wrong_count(self):
        self.m['exact_trial']=self.m['exact_trial'][:2];self.assertRaises(PilotGuardError,self.check)
    def test_duplicate_sku(self):
        self.m['exact_trial'][1]['slug']=S1;self.m['exact_trial'][1]['url']=self.m['exact_trial'][0]['url'];self.assertRaises(PilotGuardError,self.check)
    def test_url_query(self):
        self.m['exact_trial'][1]['url']+='?trick=x';self.assertRaises(PilotGuardError,self.check)
    def test_unrelated_domain(self):
        self.m['exact_trial'][0]['url']=self.m['exact_trial'][0]['url'].replace('flowwow.com','flowwow.com.evil')
        self.assertRaises(PilotGuardError,self.check)
    def test_baseline_target_missing(self):
        self.snapshot['products']=self.snapshot['products'][:1];self.assertRaises(PilotGuardError,self.check)
    def test_pending_must_be_missing_from_baseline(self):
        self.snapshot['products'].append({'slug':S3,'flowwow_url':self.m['exact_trial'][2]['url']})
        self.assertRaises(PilotGuardError,self.check)
    def test_duplicate_json_keys(self):
        self.path.write_text('{"schema_version":1,"schema_version":1}',encoding='utf-8')
        self.assertRaises(PilotGuardError,read_pilot_manifest,self.path,self.snapshot,expected_public_commit=PUB,expected_private_commit=PRIV,baseline_bytes=b'{}')
    def test_crawl_uses_only_pilot_targets_not_discovered(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)
            base=self.snapshot
            raw=json.dumps(base).encode('utf-8')
            baseline_file=out/'baseline.json';baseline_file.write_bytes(raw)
            m=copy.deepcopy(self.m)
            m['baseline_public']['git_blob_sha']=hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()
            manifest_file=out/'pilot.json';manifest_file.write_text(json.dumps(m))
            class FakePlaywright:
                def __enter__(self):return object()
                def __exit__(self,*_):return False
            args=SimpleNamespace(output=str(out/'work'),pilot_manifest=str(manifest_file),
                baseline=str(baseline_file),offline_baseline=False,retry_failed=False,
                max_products=3,max_categories=1,browser='chromium',skip_shop=True,
                download_new_media=False,max_gallery_assets=30,recheck_unverified=False,
                pause_min=0,pause_max=0)
            baseline={'seller':'https://flowwow.com/shop/lyubov-eto-699e0e4519/','products':base['products']}
            seen=[]
            def record(_page,_ctx,_db,_args,_baseline,url,*rest):seen.append(url)
            with patch('capture.load_source',return_value=(baseline,[],{'mode':'MOCK'})), \
                 patch('capture.load_playwright',return_value=lambda:FakePlaywright()), \
                 patch('capture.launch_context',return_value=SimpleNamespace(pages=[object()],close=Mock())), \
                 patch('capture.gentle_wait',return_value=None), \
                 patch('capture.record_product',side_effect=record):
                self.assertEqual(0,capture.crawl(args))
            self.assertEqual([p['url'] for p in m['exact_trial']],seen)

    def test_crawl_rejects_unrelated_prior_database_before_browser(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)
            raw=json.dumps(self.snapshot).encode('utf-8')
            baseline_file=out/'baseline.json';baseline_file.write_bytes(raw)
            m=copy.deepcopy(self.m)
            m['baseline_public']['git_blob_sha']=hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()
            manifest_file=out/'pilot.json';manifest_file.write_text(json.dumps(m))
            work=out/'work';work.mkdir()
            store=Store(work/'progress.sqlite3')
            store.record_page('https://flowwow.com/flowers/unrelated/','unrelated','x','CAPTURED',{})
            store.close()
            args=SimpleNamespace(output=str(work),pilot_manifest=str(manifest_file),baseline=str(baseline_file),offline_baseline=False,retry_failed=False,
                max_products=3,max_categories=1,browser='chromium',skip_shop=True,download_new_media=False,
                max_gallery_assets=30,recheck_unverified=False,pause_min=0,pause_max=0)
            baseline={'seller':'https://flowwow.com/shop/lyubov-eto-699e0e4519/','products':self.snapshot['products']}
            with patch('capture.load_source',return_value=(baseline,[],{'mode':'MOCK'})), \
                 patch('capture.load_playwright') as launch:
                with self.assertRaises(PilotGuardError):capture.crawl(args)
                launch.assert_not_called()

    def _store(self):
        return Store(Path(self.tmp.name)/'pilot.sqlite3')
    def test_db_isolated(self):
        rows,sha=self.check(); s=self._store()
        try:
            verify_pilot_db(s,rows,sha)
            verify_pilot_db(s,rows,sha)
            self.assertEqual(1,s.db.execute("SELECT COUNT(*) FROM events WHERE kind='PILOT_ALLOWLIST_PIN'").fetchone()[0])
            with self.assertRaises(PilotGuardError):verify_pilot_db(s,rows,'0'*64)
            s.record_page('https://flowwow.com/flowers/unrelated/','unrelated','x','CAPTURED',{})
            with self.assertRaises(PilotGuardError):verify_pilot_db(s,rows,sha)
        finally:s.close()
    def test_prior_non_pilot_session_rejected(self):
        rows,sha=self.check(); s=self._store()
        try:
            s.event('SESSION_START',{'x':1})
            with self.assertRaises(PilotGuardError):verify_pilot_db(s,rows,sha)
        finally:s.close()

if __name__=='__main__':unittest.main()
