"""Independent Round3 adversarial checks; no external network or real browser."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import capture
import storage
import pilot_targets
from test_pilot_targets import m, baseline, PUB, PRIV, S1, S2, S3
from storage import Store
from pilot_targets import PilotGuardError, read_pilot_manifest, verify_pilot_db

class Round3Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = Store(self.root/'p.db')
        self.manifest = self.root/'manifest.json'
        self.base = baseline()
        self.doc = m()
    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()
    def check_manifest(self):
        raw = json.dumps(self.base).encode()
        self.doc['baseline_public']['git_blob_sha'] = hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()
        self.manifest.write_text(json.dumps(self.doc), encoding='utf8')
        return read_pilot_manifest(self.manifest,self.base,expected_public_commit=PUB,expected_private_commit=PRIV,baseline_bytes=raw)
    def pin(self):
        rows, sha = self.check_manifest()
        verify_pilot_db(self.store, rows, sha)
        return rows, sha
    def test_replacement_pending_sku_rejected(self):
        self.doc['exact_trial'][2].update(slug='foreign',url='https://flowwow.com/flowers/foreign/')
        with self.assertRaises(PilotGuardError): self.check_manifest()
    def test_replacement_baseline_sku_rejected(self):
        self.base['products'].append({'slug':'foreign','flowwow_url':'https://flowwow.com/flowers/foreign/'})
        self.doc['exact_trial'][0].update(slug='foreign',url='https://flowwow.com/flowers/foreign/')
        with self.assertRaises(PilotGuardError): self.check_manifest()
    def test_baseline_object_must_match_hashed_bytes(self):
        self.check_manifest()
        self.base['products'].append({'slug':'foreign','flowwow_url':'https://flowwow.com/flowers/foreign/'})
        with self.assertRaises(PilotGuardError):
            read_pilot_manifest(self.manifest,self.base,expected_public_commit=PUB,expected_private_commit=PRIV,baseline_bytes=b'{}')
    def test_db_payload_foreign_url_rejected(self):
        rows, sha = self.pin()
        self.store.record_page(rows[0][0],S1,'x','CAPTURED',{'url':'https://flowwow.com/flowers/foreign/','slug':S1})
        with self.assertRaises(PilotGuardError): verify_pilot_db(self.store,rows,sha)
    def test_db_row_foreign_slug_rejected(self):
        rows, sha = self.pin()
        self.store.record_page(rows[0][0],'foreign','x','ERROR',{})
        with self.assertRaises(PilotGuardError): verify_pilot_db(self.store,rows,sha)
    def test_db_sale_flag_true_rejected(self):
        rows, sha = self.pin()
        self.store.record_page(rows[0][0],S1,'x','CAPTURED',{'url':rows[0][0],'slug':S1,'may_order':True})
        with self.assertRaises(PilotGuardError): verify_pilot_db(self.store,rows,sha)
    def test_db_captured_missing_flags_rejected(self):
        rows, sha = self.pin()
        self.store.record_page(rows[0][0],S1,'x','CAPTURED',{'url':rows[0][0],'slug':S1})
        with self.assertRaises(PilotGuardError): verify_pilot_db(self.store,rows,sha)
    def test_db_pending_metadata_only_cannot_have_media(self):
        rows, sha = self.pin()
        self.store.record_asset(S3,'https://content.flowwow-images.com/a.jpg','0'*64,None,100,500,500,'BASELINE_HASH_MATCH')
        with self.assertRaises(PilotGuardError): verify_pilot_db(self.store,rows,sha)
    def test_pin_allowed_urls_must_match(self):
        rows, sha = self.pin()
        self.store.db.execute('DELETE FROM events')
        self.store.event('PILOT_ALLOWLIST_PIN',{'manifest_sha256':sha,'allowed_urls':['https://flowwow.com/flowers/foreign/']})
        with self.assertRaises(PilotGuardError): verify_pilot_db(self.store,rows,sha)
    def test_export_takes_exclusive_lock(self):
        self.store.close()
        self.store = Store(self.root/'progress.sqlite3')
        with storage.exclusive_run_lock(self.root/'capture.lock'):
            with self.assertRaises(RuntimeError): capture.export(SimpleNamespace(output=str(self.root)))
    def test_export_rejects_post_preflight_foreign_discovery(self):
        rows, sha = self.pin()
        self.store.close()
        (self.root/'p.db').rename(self.root/'progress.sqlite3')
        self.store = Store(self.root/'progress.sqlite3')
        self.store.discover('https://flowwow.com/flowers/foreign/','x','TEST')
        with self.assertRaises(PilotGuardError): capture.export(SimpleNamespace(output=str(self.root)))
    def test_atomic_predictable_temp_symlink_not_followed(self):
        victim=self.root/'victim';victim.write_bytes(b'old')
        target=self.root/'report';target.with_name(target.name+'.tmp-'+str(os.getpid())).symlink_to(victim)
        storage.atomic_bytes(target,b'new')
        self.assertEqual(b'old',victim.read_bytes())
    def test_atomic_parent_symlink_rejected(self):
        external=self.root/'external';external.mkdir()
        link=self.root/'link';link.symlink_to(external,target_is_directory=True)
        with self.assertRaises(RuntimeError): storage.atomic_bytes(link/'report',b'x')
    def test_store_symlink_rejected_before_wal(self):
        target=self.root/'other.db';s=Store(target);s.close()
        link=self.root/'link.db';link.symlink_to(target)
        with self.assertRaises(RuntimeError): Store(link)
    def test_store_hardlink_rejected(self):
        target=self.root/'other.db';s=Store(target);s.close()
        link=self.root/'link.db';os.link(target,link)
        with self.assertRaises(RuntimeError): Store(link)
    def test_path_length_fail_before_write(self):
        long=self.root/('a'*220)/'report.json'
        with self.assertRaises(RuntimeError): storage.atomic_bytes(long,b'x')
    def test_output_catalog_rejected(self):
        repo=Path(__file__).resolve().parents[4]
        with self.assertRaises(RuntimeError): capture.checked_output(repo/'catalog')
    def test_acceptance_empty_is_partial(self):
        report=capture.pilot_acceptance(self.store,self.root)
        self.assertEqual('PARTIAL',report['status']);self.assertEqual(3,len(report['targets']))
    def test_acceptance_error_is_blocked(self):
        rows,_=self.pin();self.store.record_page(rows[0][0],S1,'x','ERROR',{})
        self.assertEqual('BLOCKED',capture.pilot_acceptance(self.store,self.root)['status'])
    def test_acceptance_candidate_gallery_never_passes(self):
        self.pin()
        for url,kind in self.check_manifest()[0]:
            self.store.record_page(url,url.rstrip('/').split('/')[-1],kind,'CAPTURED',{'url':url,'seller':{'status':'EXACT_SELLER_CLICK_VERIFIED'},'gallery':{'status':'GALLERY_CANDIDATES_UNVERIFIED_COMPLETENESS','items':['x']}})
        self.assertEqual('PARTIAL',capture.pilot_acceptance(self.store,self.root)['status'])
    def test_discovery_allowlist_at_write_boundary(self):
        rows,_=self.pin();self.store.allowed_urls={u for u,_ in rows}
        self.store.discover('https://flowwow.com/flowers/foreign/','x','TEST')
        self.assertEqual([],self.store.urls())
    def test_unsafe_request_body_not_used(self):
        # The old browser transport buffers before the size check.
        ctx=SimpleNamespace(request=Mock())
        with patch('capture.fetch_image',return_value=b'bad') as fetch:
            capture.download_assets(ctx,self.store,SimpleNamespace(max_gallery_assets=1,pause_min=0,pause_max=0),S1,['https://content.flowwow-images.com/a.jpg'],{'products':[]},self.root)
        ctx.request.get.assert_not_called();fetch.assert_called_once()
    def test_stream_private_dns_rejected(self):
        import media_transport
        with patch('media_transport.socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]),patch('media_transport.socket.create_connection') as conn:
            with self.assertRaises(RuntimeError): media_transport.fetch_image('https://content.flowwow-images.com/a.jpg',1024)
            conn.assert_not_called()
    def test_stream_mixed_dns_rejected(self):
        import media_transport
        with patch('media_transport.socket.getaddrinfo',return_value=[(2,1,6,'',('8.8.8.8',443)),(2,1,6,'',('169.254.169.254',443))]):
            with self.assertRaises(RuntimeError): media_transport.fetch_image('https://content.flowwow-images.com/a.jpg',1024)
    def test_stream_redirect_never_followed(self):
        import media_transport
        response=Mock(status=302)
        with patch('media_transport.open_response',return_value=(Mock(),response)):
            with self.assertRaises(RuntimeError): media_transport.fetch_image('https://content.flowwow-images.com/a.jpg',1024)
        response.read1.assert_not_called()
    def test_stream_compression_rejected_before_body(self):
        import media_transport
        response=Mock(status=200);response.getheader.side_effect=lambda k,*a: {'Content-Encoding':'gzip'}.get(k)
        with patch('media_transport.open_response',return_value=(Mock(),response)):
            with self.assertRaises(RuntimeError): media_transport.fetch_image('https://content.flowwow-images.com/a.jpg',1024)
        response.read1.assert_not_called()
    def test_stream_oversize_header_before_body(self):
        import media_transport
        response=Mock(status=200);response.getheader.side_effect=lambda k,*a: {'Content-Length':'1025'}.get(k)
        with patch('media_transport.open_response',return_value=(Mock(),response)):
            with self.assertRaises(RuntimeError): media_transport.fetch_image('https://content.flowwow-images.com/a.jpg',1024)
        response.read1.assert_not_called()
    def test_stream_chunked_limited_read(self):
        import media_transport
        response=Mock(status=200);response.getheader.return_value=None;response.read1.side_effect=[b'x'*1024,b'x']
        with patch('media_transport.open_response',return_value=(Mock(),response)):
            with self.assertRaises(RuntimeError): media_transport.fetch_image('https://content.flowwow-images.com/a.jpg',1024)
        self.assertTrue(all(c.args[0]<=1025 for c in response.read1.call_args_list))
        response.read.assert_not_called()
    def test_dimension_decimal_not_silently_integer(self):
        import parsing
        self.assertEqual('UNVERIFIED_PARSE',parsing.parse_dimensions('Ширина: 35,5 см Высота: 45 см')['status'])
    def test_dimension_contradictory_sizes_rejected(self):
        import parsing
        self.assertEqual('UNVERIFIED_PARSE',parsing.parse_dimensions('35x45 см; Ширина: 90 см Высота: 100 см')['status'])

class Round3IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.baseline=self.root/'baseline.json'
        repo=Path(__file__).resolve().parents[4]
        self.baseline.write_bytes((repo/'catalog/public-snapshot.json').read_bytes())
        self.manifest=self.root/'pilot.json'
        doc=m();doc['baseline_public']['git_blob_sha']='b1ba9fbe10b7961d35a723d40af01686a0e10b78'
        self.manifest.write_text(json.dumps(doc),encoding='utf8')
        self.args=SimpleNamespace(output=str(self.root/'work'),pilot_manifest=str(self.manifest),
            baseline=str(self.baseline),offline_baseline=False,retry_failed=False,max_products=3,
            max_categories=1,browser='chromium',skip_shop=True,download_new_media=False,
            max_gallery_assets=30,recheck_unverified=False,pause_min=0,pause_max=0)
        self.ctx=SimpleNamespace(pages=[SimpleNamespace(on=Mock())],close=Mock(),route=Mock(),on=Mock())
    def tearDown(self):self.tmp.cleanup()
    def run_fake(self, callback=None, **kw):
        manager=Mock();manager.__enter__=Mock(return_value=object());manager.__exit__=Mock(return_value=False)
        with patch('capture.load_playwright',return_value=lambda:manager),patch('capture.launch_context',return_value=self.ctx),patch('capture.gentle_wait'),patch('capture.record_product',side_effect=callback),patch('capture.collect_shop',side_effect=kw.get('shop')):
            return capture.crawl(self.args)
    def report(self):
        return json.loads((self.root/'work/review/pilot-acceptance.json').read_text())
    def test_actual_pinned_baseline_and_manifest_offline_preflight(self):
        b,ledgers,origin=capture.load_source(self.root,str(self.baseline))
        rows,sha=capture.check_pilot_files(self.args,b,origin)
        self.assertEqual(3,len(rows));self.assertEqual([],ledgers)
    def test_valid_self_signed_but_untrusted_baseline_rejected(self):
        b=baseline();b['seller']=pilot_targets.SHOP
        for product in b['products']:product['seller_url']=pilot_targets.SHOP
        raw=json.dumps(b).encode();self.baseline.write_bytes(raw)
        doc=m();doc['baseline_public']['git_blob_sha']=hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest();self.manifest.write_text(json.dumps(doc))
        with patch('capture.Store') as store,patch('capture.load_playwright') as browser:
            with self.assertRaises(PilotGuardError):capture.crawl(self.args)
        store.assert_not_called();browser.assert_not_called()
    def test_invalid_manifest_never_opens_wrong_database(self):
        work=self.root/'work';work.mkdir();db=work/'progress.sqlite3';db.write_bytes(b'NOT SQL')
        self.manifest.write_text('{}')
        with patch('capture.Store') as store:
            with self.assertRaises(PilotGuardError):capture.crawl(self.args)
        store.assert_not_called();self.assertEqual(b'NOT SQL',db.read_bytes());self.assertEqual('BLOCKED',self.report()['status'])
    def test_mid_session_manifest_change_stops_next_product(self):
        seen=[]
        def change(*args):
            seen.append(args[5]);self.manifest.write_text('{}')
        with self.assertRaises(PilotGuardError):self.run_fake(change)
        self.assertEqual(1,len(seen));self.assertEqual('BLOCKED',self.report()['status'])
    def test_mid_session_baseline_change_stops_next_product(self):
        seen=[]
        def change(*args):seen.append(args[5]);self.baseline.write_bytes(b'{}')
        with self.assertRaises(PilotGuardError):self.run_fake(change)
        self.assertEqual(1,len(seen));self.assertEqual('BLOCKED',self.report()['status'])
    def test_product_errors_cannot_return_success(self):
        code=self.run_fake(lambda *args: (_ for _ in ()).throw(RuntimeError('simulated crash')))
        self.assertEqual(5,code);self.assertEqual('BLOCKED',self.report()['status'])
        self.assertEqual(3,len(self.report()['targets']))
    def test_product_unavailable_cannot_return_success(self):
        code=self.run_fake(lambda *args: (_ for _ in ()).throw(capture.ProductUnavailable('404')))
        self.assertEqual(5,code);self.assertEqual('BLOCKED',self.report()['status'])
    def test_global_block_stops_first_target(self):
        seen=[]
        def blocked(*args):seen.append(args[5]);raise capture.BrowserBlocked('403')
        self.assertEqual(3,self.run_fake(blocked));self.assertEqual(1,len(seen));self.assertEqual('BLOCKED',self.report()['status'])
    def test_failed_browser_launch_invalidates_old_pass(self):
        work=self.root/'work/review';work.mkdir(parents=True)
        (work/'pilot-acceptance.json').write_text('{"status":"PASS"}')
        with patch('capture.load_playwright',side_effect=RuntimeError('No visible browser')):
            with self.assertRaises(RuntimeError):capture.crawl(self.args)
        self.assertEqual('BLOCKED',self.report()['status'])
    def test_shop_foreign_discovery_never_persisted(self):
        self.args.skip_shop=False
        def shop(_page,store,*rest):
            store.discover('https://flowwow.com/flowers/foreign/','x','MOCK')
            store.discover(m()['exact_trial'][0]['url'],'x','MOCK')
        self.assertEqual(5,self.run_fake(shop=shop))
        s=Store(self.root/'work/progress.sqlite3')
        try:self.assertEqual(1,len(s.urls()));self.assertIn(S1,s.urls()[0][0])
        finally:s.close()
    def test_metadata_only_download_is_rejected_before_network(self):
        s=Store(self.root/'p.db');s.allowed_urls={t['url'] for t in m()['exact_trial']}
        try:
            with patch('capture.fetch_image') as fetch:
                with self.assertRaises(PilotGuardError):capture.download_assets(Mock(),s,self.args,S3,['https://content.flowwow-images.com/a.jpg'],{'products':[]},self.root)
                fetch.assert_not_called()
        finally:s.close()
    def test_other_sku_baseline_photo_never_counts_as_owned(self):
        s=Store(self.root/'p.db');url='https://content.flowwow-images.com/a.jpg'
        try:
            with patch('capture.fetch_image',side_effect=RuntimeError('offline')) as fetch,patch('capture.gentle_wait'):
                r=capture.download_assets(Mock(),s,self.args,S1,[url],{'products':[{'slug':S2,'gallery':[{'source_url':url,'sha256':'0'*64,'path':'foreign.jpg'}]}]},self.root)
            fetch.assert_called_once();self.assertEqual('UNVERIFIED_DOWNLOAD_ERROR',r[0]['status']);self.assertNotIn('original_path',r[0])
        finally:s.close()
    def test_unrelated_sqlite_schema_unchanged(self):
        import sqlite3
        path=self.root/'other.db';db=sqlite3.connect(path);db.execute('CREATE TABLE valuable(x)');db.commit();db.close();before=path.read_bytes()
        with self.assertRaises(RuntimeError):Store(path)
        self.assertEqual(before,path.read_bytes());self.assertFalse(Path(str(path)+'-wal').exists())
    def test_corrupted_sqlite_no_repair_or_reset(self):
        path=self.root/'bad.db';path.write_bytes(b'bad sqlite');before=path.read_bytes()
        with self.assertRaises(Exception):Store(path)
        self.assertEqual(before,path.read_bytes())
    def test_symlink_wal_rejected(self):
        path=self.root/'db';s=Store(path);s.close();victim=self.root/'victim';victim.write_bytes(b'old')
        Path(str(path)+'-wal').symlink_to(victim)
        with self.assertRaises(RuntimeError):Store(path)
        self.assertEqual(b'old',victim.read_bytes())
    def test_export_scope_marker_cannot_be_downgraded(self):
        self.assertEqual(5,self.run_fake())
        s=Store(self.root/'work/progress.sqlite3');s.db.execute('DELETE FROM events');s.close()
        with self.assertRaises(PilotGuardError):capture.export(self.args)
        self.assertEqual('BLOCKED',self.report()['status'])
    def test_corrupted_db_export_invalidates_old_acceptance(self):
        work=self.root/'work/review';work.mkdir(parents=True)
        (work/'pilot-acceptance.json').write_text('{"status":"PASS"}')
        (work.parent/'progress.sqlite3').write_bytes(b'CORRUPTED')
        with self.assertRaises(Exception):capture.export(self.args)
        self.assertEqual('BLOCKED',self.report()['status'])

    def test_export_after_rejected_foreign_db_never_falls_back_to_nonpilot(self):
        work=self.root/'work';work.mkdir();store=Store(work/'progress.sqlite3')
        store.record_page('https://flowwow.com/flowers/foreign/','foreign','x','ERROR',{'url':'https://flowwow.com/flowers/foreign/','slug':'foreign'})
        store.close()
        with self.assertRaises(PilotGuardError):capture.crawl(self.args)
        with self.assertRaises(PilotGuardError):capture.export(self.args)
        self.assertFalse((work/'review/products.json').exists())

    def test_export_cannot_upgrade_interrupted_run(self):
        def blocked(*args):raise capture.BrowserBlocked('403')
        self.assertEqual(3,self.run_fake(blocked))
        with patch('capture.pilot_acceptance',return_value={'status':'PASS','targets':[]}):
            self.assertEqual(5,capture.export(self.args))
        self.assertEqual('BLOCKED',self.report()['status'])
        self.assertEqual('PREVIOUS_RUN_DID_NOT_FINISH',self.report()['reason'])

    def test_document_redirect_blocked_before_request(self):
        ctx=Mock(pages=[]);capture.configure_pilot_navigation(ctx,{t['url'] for t in m()['exact_trial']})
        guard=ctx.route.call_args.args[1]
        for url in ['http://127.0.0.1/','https://evil.example/','https://flowwow.com/flowers/foreign/',pilot_targets.SHOP+'?redirect=https://evil.example/']:
            route=Mock();route.request.resource_type='document';route.request.url=url;guard(route)
            route.abort.assert_called_once();route.continue_.assert_not_called()
        route=Mock();route.request.resource_type='document';route.request.url=pilot_targets.SHOP;guard(route);route.continue_.assert_called_once()
    def test_media_transport_closes_on_failure(self):
        import media_transport
        conn=Mock();response=Mock(status=403)
        with patch('media_transport.open_response',return_value=(conn,response)):
            with self.assertRaises(media_transport.MediaAccessBlocked):media_transport.fetch_image('https://content.flowwow-images.com/a.jpg',1024)
        conn.close.assert_called_once();response.close.assert_called_once();response.read1.assert_not_called()
    def test_media_transport_success_and_truncation(self):
        import media_transport
        for actual,expected in [(64,64),(64,128)]:
            conn=Mock();response=Mock(status=200);response.getheader.side_effect=lambda k,*a: str(expected) if k=='Content-Length' else None;response.read1.side_effect=[b'x'*actual,b'']
            with patch('media_transport.open_response',return_value=(conn,response)):
                if actual==expected:self.assertEqual(b'x'*64,media_transport.fetch_image('https://content.flowwow-images.com/a.jpg',1024))
                else:
                    with self.assertRaises(RuntimeError):media_transport.fetch_image('https://content.flowwow-images.com/a.jpg',1024)
            conn.close.assert_called_once()
    def test_tls_connection_uses_pinned_ip_and_hostname(self):
        import media_transport
        tls=Mock()
        with patch('media_transport.ssl.create_default_context',return_value=tls),patch('media_transport.socket.create_connection') as connect:
            conn=media_transport.PinnedHTTPSConnection('content.flowwow-images.com','8.8.8.8');conn.connect()
            connect.assert_called_once_with(('8.8.8.8',443),15)
            self.assertEqual('content.flowwow-images.com',tls.wrap_socket.call_args.kwargs['server_hostname'])

class Round3RecoveryTests(unittest.TestCase):
    def test_process_kill_releases_lock_and_keeps_committed_wal(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            code="""import sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from storage import Store, exclusive_run_lock
root=Path(sys.argv[2])
with exclusive_run_lock(root/'capture.lock'):
 s=Store(root/'progress.sqlite3')
 s.record_page('https://flowwow.com/flowers/a/','a','x','ERROR',{'interrupted':True})
 print('READY',flush=True)
 sys.stdin.read()
"""
            # Windows venv python.exe can be a launcher: killing only it may
            # leave the actual interpreter holding the OS lock. Storage needs
            # only stdlib, so target the interpreter process directly here.
            executable=getattr(sys, '_base_executable', sys.executable) if os.name=='nt' else sys.executable
            proc=subprocess.Popen([executable,'-c',code,str(Path(capture.__file__).parent),folder],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                self.assertEqual('READY',proc.stdout.readline().strip())
                with self.assertRaises(RuntimeError):
                    with storage.exclusive_run_lock(root/'capture.lock'):pass
                proc.kill();proc.wait(timeout=10)
                with storage.exclusive_run_lock(root/'capture.lock'):
                    store=Store(root/'progress.sqlite3')
                    try:
                        self.assertEqual(1,len(store.page_rows()))
                        self.assertEqual([('ok',)],store.db.execute('PRAGMA quick_check').fetchall())
                    finally:store.close()
            finally:
                if proc.poll() is None:proc.kill();proc.wait(timeout=10)
                proc.stdin.close();proc.stdout.close();proc.stderr.close()
    def test_unverified_seller_fields_and_photos_are_quarantined(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);store=Store(root/'p.db');url=m()['exact_trial'][0]['url']
            heading=Mock();heading.count.return_value=1;heading.first.inner_text.return_value='Foreign product'
            page=SimpleNamespace(url=url,content=lambda:'<main><h1>Foreign product</h1></main>',wait_for_timeout=Mock(),locator=Mock(return_value=heading))
            try:
                with patch('capture.navigate',return_value={'final_url':url}),patch('capture.click_seller_link',return_value={'status':'DIFFERENT_OR_UNVERIFIED_SELLER'}),patch('capture.gallery_candidates',return_value={'status':'GALLERY_NOT_IDENTIFIED','items':[]}) as gallery:
                    result=capture.record_product(page,Mock(),store,SimpleNamespace(download_new_media=False,gallery_selector=None),{'products':[]},url,'PILOT',root)
                self.assertEqual('SELLER_UNVERIFIED',store.page_rows()[0][3])
                self.assertNotIn('composition',result);self.assertNotIn('gallery',result);gallery.assert_not_called()
            finally:store.close()
    def test_media_path_cannot_belong_to_other_target(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'new-media'/S2/'a.jpg';storage.atomic_bytes(path,b'a'*64)
            sha=hashlib.sha256(b'a'*64).hexdigest()
            with self.assertRaises(capture.LocalIntegrityError):capture.verify_local_media(root,[('url',S1,sha,f'new-media/{S2}/a.jpg',64,500,500,'NEW_ORIGINAL_FILE')])
    def test_show_more_popup_is_propagated_to_session_stop(self):
        page=SimpleNamespace(url=pilot_targets.SHOP,content=lambda:'<main></main>')
        with patch('capture.navigate',return_value={}),patch('capture.expand_shop',return_value={'stop_reason':'MORE_CONTROL_OPENED_NEW_TAB'}):
            with self.assertRaises(capture.BrowserBlocked):capture.collect_shop(page,Mock(),SimpleNamespace(max_categories=1),{'products':[]})
    def test_multiple_seller_popups_are_closed(self):
        from test_arena_review2_independent import SellerPage, PopupPage, PRODUCT
        page=SellerPage()
        def open_many(**kw):
            page.context.pages.extend([PopupPage(pilot_targets.SHOP,page.context),PopupPage(pilot_targets.SHOP,page.context)])
        page._seller.click=open_many
        result=capture.click_seller_link(page,PRODUCT)
        self.assertEqual('UNVERIFIED',result['status']);self.assertEqual(1,len(page.context.pages))

    def test_recheck_cannot_treat_candidate_gallery_as_complete(self):
        p={'seller':{'status':'EXACT_SELLER_CLICK_VERIFIED'},'composition':{'status':'PARSED_NEEDS_SELLER_CONFIRMATION'},
           'dimensions':{'status':'PARSED_NEEDS_SELLER_CONFIRMATION'},'source_sections':{'description':{'status':'SOURCE_SECTION_TEXT_CAPTURED'}},
           'gallery':{'status':'GALLERY_CANDIDATES_UNVERIFIED_COMPLETENESS'}}
        self.assertTrue(capture.needs_source_recheck(p))

    def test_windows_failed_lock_does_not_unlock_active_owner_mock(self):
        active=[False]
        def locking(fd,mode,length):
            if mode==1:
                if active[0]:raise OSError('locked')
                active[0]=True
            else:active[0]=False
        module=SimpleNamespace(locking=locking,LK_NBLCK=1,LK_UNLCK=2)
        fake_os=SimpleNamespace(name='nt',path=os.path)
        with tempfile.TemporaryDirectory() as folder,patch('storage.os',fake_os),patch.dict(sys.modules,{'msvcrt':module}):
            with storage.exclusive_run_lock(Path(folder)/'lock'):
                with self.assertRaises(RuntimeError):
                    with storage.exclusive_run_lock(Path(folder)/'lock'):pass
                self.assertTrue(active[0])
            self.assertFalse(active[0])

    def test_large_local_media_is_not_read_into_ram(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'big'
            with open(path,'wb') as file:file.truncate(capture.MAX_BYTES+1)
            with patch('pathlib.Path.read_bytes',side_effect=AssertionError('unbounded read')):
                with self.assertRaises(capture.LocalIntegrityError):capture.media_sha(path)
    def test_large_baseline_is_bounded(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'big'
            with open(path,'wb') as file:file.truncate(10*1024*1024+1)
            with self.assertRaises(capture.LocalIntegrityError):capture.load_source(Path(folder),str(path))
    def test_failing_online_read_actually_uses_existing_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);cache=root/'cache';cache.mkdir()
            b=baseline();b['seller']=pilot_targets.SHOP
            for item in b['products']:item['seller_url']=pilot_targets.SHOP
            (cache/'public-snapshot.json').write_text(json.dumps(b))
            with patch('capture.public_gh_json',side_effect=OSError('offline')):
                value,_,_=capture.load_source(root,None,False)
            self.assertEqual(b,value)
    def test_browser_profile_never_stored_under_repository(self):
        repo=Path(__file__).resolve().parents[4]
        with patch.dict(os.environ,{'LOCALAPPDATA':str(repo)}):
            with self.assertRaises(RuntimeError):capture.browser_profile(Path('/tmp/unrelated'))
    def test_no_manifest_cli_never_loads_browser(self):
        with tempfile.TemporaryDirectory() as folder,patch('capture.crawl',return_value=0) as crawl:
            self.assertEqual(2,capture.cli(['crawl','--baseline','missing.json','--output',folder]))
            crawl.assert_not_called()
    def test_invalid_utf8_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'m';path.write_bytes(b'\xff')
            with self.assertRaises(PilotGuardError):read_pilot_manifest(path,{},expected_public_commit=PUB,expected_private_commit=PRIV,baseline_bytes=b'{}')
    def test_oversized_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'m';path.write_bytes(b' '*64001)
            with self.assertRaises(PilotGuardError):read_pilot_manifest(path,{},expected_public_commit=PUB,expected_private_commit=PRIV,baseline_bytes=b'{}')
    def test_animated_media_rejected_without_write(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);store=Store(root/'p.db')
            image=Mock(format='PNG',size=(500,500),n_frames=2);manager=Mock();manager.__enter__=Mock(return_value=image);manager.__exit__=Mock(return_value=False)
            try:
                with patch('capture.fetch_image',return_value=b'x'*64),patch('capture.Image.open',return_value=manager),patch('capture.gentle_wait'):
                    result=capture.download_assets(Mock(),store,SimpleNamespace(max_gallery_assets=1),S1,['https://content.flowwow-images.com/a.png'],{'products':[]},root)
                self.assertEqual('UNVERIFIED_DOWNLOAD_ERROR',result[0]['status']);image.verify.assert_not_called();self.assertFalse((root/'new-media').exists())
            finally:store.close()
    def test_pixel_bomb_rejected_before_decode(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);store=Store(root/'p.db')
            image=Mock(format='PNG',size=(6001,6000));manager=Mock();manager.__enter__=Mock(return_value=image);manager.__exit__=Mock(return_value=False)
            try:
                with patch('capture.fetch_image',return_value=b'x'*64),patch('capture.Image.open',return_value=manager),patch('capture.gentle_wait'):
                    result=capture.download_assets(Mock(),store,SimpleNamespace(max_gallery_assets=1),S1,['https://content.flowwow-images.com/a.png'],{'products':[]},root)
                self.assertEqual('UNVERIFIED_DOWNLOAD_ERROR',result[0]['status']);image.verify.assert_not_called();self.assertFalse((root/'new-media').exists())
            finally:store.close()

if __name__=='__main__': unittest.main()
