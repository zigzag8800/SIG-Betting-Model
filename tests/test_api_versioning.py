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
        store.connect=lambda: context
        matches=[{'id':123,'score':{'fullTime':{'home':0,'away':0}}}]
        digest=store.put_api_matches('scope:PL:2026',matches)
        calls=conn.execute.call_args_list
        self.assertEqual(len(calls),3)
        self.assertIn('pg_advisory_xact_lock',calls[0].args[0])
        self.assertIn('api_matches_version',calls[1].args[0])
        self.assertIn('ON CONFLICT(kind,key) DO NOTHING',calls[1].args[0])
        self.assertIn('api_matches',calls[2].args[0])
        self.assertIn('DO UPDATE',calls[2].args[0])
        self.assertEqual(digest,content_key(matches))
        self.assertEqual(calls[1].args[1][0],'scope:PL:2026:'+digest)
        self.assertEqual(calls[2].args[1][0],'scope:PL:2026')

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
