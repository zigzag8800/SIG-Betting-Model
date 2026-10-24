"""Regression tests: raw provider snapshots must be archived before cache refresh."""
import unittest
from unittest.mock import MagicMock
from persistent_store import Store, content_key

class ApiVersioningTests(unittest.TestCase):
    def test_atomic_version_insert_precedes_cache_update(self):
        store=object.__new__(Store)
        conn=MagicMock()
        context=MagicMock()
        context.__enter__.return_value=conn
        context.__exit__.return_value=False
        conn.execute.return_value.fetchone.return_value=None
        store.connect=lambda: context
        matches=[{'id':123,'score':{'fullTime':{'home':0,'away':0}}}]
        digest=store.put_api_matches('scope:PL:2026',matches)
        conn.execute.return_value.fetchone.assert_called_once()
        calls=conn.execute.call_args_list
        self.assertEqual(len(calls),4)
        self.assertIn('pg_advisory_xact_lock',calls[0].args[0])
        self.assertIn('api_matches_version',calls[2].args[0])
        self.assertIn('ON CONFLICT(kind,key) DO NOTHING',calls[2].args[0])
        self.assertIn('api_matches',calls[3].args[0])
        self.assertIn('DO UPDATE',calls[3].args[0])
        self.assertEqual(digest,content_key(matches))
        self.assertEqual(calls[2].args[1][0],'scope:PL:2026:'+digest)
        self.assertEqual(calls[3].args[1][0],'scope:PL:2026')

    def test_first_refresh_archives_preexisting_cache(self):
        store=object.__new__(Store)
        conn=MagicMock()
        context=MagicMock()
        context.__enter__.return_value=conn
        store.connect=lambda: context
        old=[{'id':10,'status':'SCHEDULED'}]
        new=[{'id':10,'status':'FINISHED'}]
        conn.execute.return_value.fetchone.return_value=(old,)
        store.put_api_matches('scope:PL:2026',new)
        calls=conn.execute.call_args_list
        self.assertEqual(len(calls),5)
        self.assertEqual(calls[2].args[1][0],
                         'scope:PL:2026:'+content_key(old))
        self.assertEqual(calls[3].args[1][0],
                         'scope:PL:2026:'+content_key(new))
        self.assertIn("VALUES('api_matches'",calls[4].args[0])

    def test_status_is_read_only_and_returns_aggregate_counts(self):
        store=object.__new__(Store)
        conn=MagicMock()
        context=MagicMock()
        context.__enter__.return_value=conn
        store.connect=lambda: context
        conn.execute.return_value.fetchall.return_value=[
            ('api_matches',12),('api_matches_version',4)]
        conn.execute.return_value.fetchone.return_value=(9,)
        status=store.api_version_status()
        self.assertEqual(status,dict(active_cache_entries=12,
                                     immutable_versions=4,
                                     cache_entries_without_matching_snapshot=9))
        self.assertEqual(conn.execute.call_count,3)
        self.assertIn('READ ONLY',conn.execute.call_args_list[0].args[0])
        self.assertNotIn('cache_key',status)

    def test_version_key_changes_when_original_response_changes(self):
        store=object.__new__(Store)
        conn=MagicMock()
        context=MagicMock()
        context.__enter__.return_value=conn
        store.connect=lambda: context
        first=store.put_api_matches('scope:PL:2026',[{'id':1,'status':'SCHEDULED'}])
        second=store.put_api_matches('scope:PL:2026',[{'id':1,'status':'FINISHED'}])
        self.assertNotEqual(first,second)

if __name__=='__main__':
    unittest.main()
