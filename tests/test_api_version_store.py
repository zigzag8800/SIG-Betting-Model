"""Real PostgreSQL transactions in a dedicated disposable CI test database.

The production Store still enforces TLS; this test-only subclass connects to the
isolated localhost CI service. Never configure a production DSN in this variable.
"""
import datetime as dt
import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
try:
    import psycopg
    from psycopg import sql
    from psycopg.types.json import Jsonb
except ImportError:
    psycopg=None
from persistent_store import Store,StorageError,content_key

DSN=os.environ.get('SIG_TEST_DATABASE_URL','')

@unittest.skipUnless(DSN and psycopg,'Requires isolated SIG_TEST_DATABASE_URL PostgreSQL service')
class ApiVersionStoreTests(unittest.TestCase):
    def setUp(self):
        self.schema='sig_test_'+uuid.uuid4().hex
        with psycopg.connect(DSN) as conn:conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
        schema=self.schema
        class TestStore(Store):
            def connect(self):return psycopg.connect(DSN,options='-c search_path='+schema)
        self.store=TestStore(DSN);self.store.initialize();self.key='synthetic:PL:2026'
    def tearDown(self):
        with psycopg.connect(DSN) as conn:conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))
    def reserve(self,resource='PL:2026'):
        return self.store.reserve('football-data.org',resource,minimum_seconds=0)
    def rows(self,kind):
        with self.store.connect() as conn:return conn.execute('SELECT key,payload,saved_at FROM sig_archive WHERE kind=%s ORDER BY key',(kind,)).fetchall()
    def test_changed_refresh_keeps_both_payloads_and_success_is_atomic(self):
        a=[dict(id=1,status='TIMED')];b=[dict(id=1,status='FINISHED')]
        first=self.reserve();self.assertEqual(self.store.save_api_response(self.key,a,first),a)
        second=self.reserve();self.assertEqual(self.store.save_api_response(self.key,b,second),b)
        self.assertEqual(self.store.get('api_matches',self.key),b)
        versions=self.rows('api_matches_version');self.assertEqual(len(versions),2)
        self.assertEqual({r[1]['payload_hash'] for r in versions},{content_key(a),content_key(b)})
        self.assertEqual(len(self.rows('api_matches_observation')),2)
        with self.store.connect() as conn:self.assertEqual(conn.execute('SELECT DISTINCT status FROM sig_downloads').fetchall(),[('success',)])
    def test_identical_content_preserves_first_recorded_time_but_records_each_download(self):
        a=[dict(id=1)];first=self.reserve();self.store.save_api_response(self.key,a,first)
        old_version=self.rows('api_matches_version')[0]
        self.store.save_api_response(self.key,a,self.reserve())
        self.assertEqual(self.rows('api_matches_version'),[old_version]);self.assertEqual(len(self.rows('api_matches_observation')),2)
    def test_backfill_is_idempotent_and_does_not_refresh_ttl_or_download_ledger(self):
        a=[dict(id=1)];saved=dt.datetime(2020,1,1,tzinfo=dt.timezone.utc)
        with self.store.connect() as conn:conn.execute("INSERT INTO sig_archive(kind,key,payload,saved_at) VALUES('api_matches',%s,%s,%s)",(self.key,Jsonb(a),saved))
        before=self.rows('api_matches');report=self.store.backfill_api_versions()
        self.assertEqual(report['versions_added'],1);self.assertEqual(self.rows('api_matches'),before)
        self.assertEqual(self.rows('api_matches_version')[0][2],saved)
        self.assertEqual(self.rows('api_matches_version')[0][1]['origin'],'legacy_cache_saved_at')
        self.assertEqual(self.store.backfill_api_versions()['versions_added'],0)
        with self.store.connect() as conn:self.assertEqual(conn.execute('SELECT count(*) FROM sig_downloads').fetchone()[0],0)
    def test_failure_rolls_back_versions_cache_observation_and_success(self):
        a=[dict(id=1)];self.store.save_api_response(self.key,a,self.reserve())
        before={k:self.rows(k) for k in ('api_matches','api_matches_version','api_matches_observation','api_matches_head')}
        reservation=self.reserve()
        with self.store.connect() as conn:
            conn.execute("""CREATE FUNCTION reject_observation() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN IF NEW.kind='api_matches_observation' THEN RAISE EXCEPTION 'test injected failure'; END IF; RETURN NEW; END $$""")
            conn.execute('CREATE TRIGGER reject_observation BEFORE INSERT ON sig_archive FOR EACH ROW EXECUTE FUNCTION reject_observation()')
        with self.assertRaises(psycopg.Error):self.store.save_api_response(self.key,[dict(id=2)],reservation)
        self.assertEqual({k:self.rows(k) for k in before},before)
        with self.store.connect() as conn:self.assertEqual(conn.execute('SELECT status FROM sig_downloads WHERE id=%s',(reservation,)).fetchone()[0],'reserved')
    def test_older_request_arriving_last_cannot_replace_newer_cache(self):
        first=self.reserve();second=self.reserve();new=[dict(version=2)];old=[dict(version=1)]
        self.store.save_api_response(self.key,new,second)
        self.assertEqual(self.store.save_api_response(self.key,old,first),new)
        self.assertEqual(self.store.get('api_matches',self.key),new);self.assertEqual(len(self.rows('api_matches_version')),2)
        older=self.store.get('api_matches_observation',str(first));self.assertFalse(older['selected_as_cache'])
    def test_concurrent_writes_keep_both_versions_and_latest_request_pointer(self):
        ids=[self.reserve(),self.reserve()];payloads=[[dict(version=1)],[dict(version=2)]]
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda pair:self.store.save_api_response(self.key,pair[1],pair[0]),zip(ids,payloads)))
        self.assertEqual(self.store.get('api_matches',self.key),payloads[1]);self.assertEqual(len(self.rows('api_matches_version')),2)
        self.assertEqual(len(self.rows('api_matches_observation')),2)
    def test_replaying_same_download_is_noop_and_conflicting_reuse_is_rejected(self):
        reservation=self.reserve();a=[dict(id=1)];self.store.save_api_response(self.key,a,reservation)
        before={k:self.rows(k) for k in ('api_matches','api_matches_version','api_matches_observation','api_matches_head')}
        self.store.save_api_response(self.key,a,reservation)
        self.assertEqual({k:self.rows(k) for k in before},before)
        with self.assertRaises(StorageError):self.store.save_api_response(self.key,[dict(id=2)],reservation)
    def test_wrong_reservation_and_unversioned_write_are_rejected(self):
        with self.assertRaises(StorageError):self.store.save_api_response(self.key,[],self.reserve('ELC:2026'))
        self.assertFalse(self.rows('api_matches_version'))
        for kind in ('api_matches','api_matches_version','api_matches_observation','api_matches_head'):
            with self.assertRaises(StorageError):self.store.put(kind,'key',[])
    def test_full_json_envelope_changes_are_preserved_even_when_matches_are_identical(self):
        matches=[dict(id=1)]
        a=dict(matches=matches,filters=dict(season='2026'),resultSet=dict(count=1))
        b={**a,'resultSet':dict(count=1,lastUpdated='later')}
        self.store.save_api_response(self.key,matches,self.reserve(),raw_response=a)
        self.store.save_api_response(self.key,matches,self.reserve(),raw_response=b)
        versions=self.rows('api_matches_version');self.assertEqual(len(versions),2)
        self.assertEqual({r[1]['payload_hash'] for r in versions},{content_key(a),content_key(b)})
        self.assertTrue(all(r[1]['raw_scope']=='full_json' for r in versions))
        self.assertEqual(self.store.backfill_api_versions()['versions_added'],0)
    def test_inconsistent_full_response_is_rejected_before_any_write(self):
        with self.assertRaises(ValueError):self.store.save_api_response(self.key,[dict(id=1)],self.reserve(),raw_response=dict(matches=[]))
        self.assertFalse(self.rows('api_matches_version'))
