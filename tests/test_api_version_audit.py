import copy
import unittest
from archive_audit import build_report
from persistent_store import content_key,api_version_valid

class ApiVersionAuditTests(unittest.TestCase):
    def fixture(self):
        matches=[dict(id=1,utcDate='2026-10-24T12:00:00Z',homeTeam=dict(id=1,name='H'),awayTeam=dict(id=2,name='A'),status='TIMED')]
        raw=dict(matches=matches,filters=dict(season='2026'));cache_key='synthetic:PL:2026';digest=content_key(raw)
        version=dict(cache_key=cache_key,payload_hash=digest,matches=matches,response=raw,raw_scope='full_json',origin='response_archived_at')
        snapshot=dict(api=[(cache_key,matches)],current={},inventory=[],versions=[],api_versions=[(cache_key+':'+digest,version,'2026-10-24')])
        return snapshot,version
    def test_full_json_version_protects_current_cache_without_exporting_raw_response(self):
        snapshot,version=self.fixture();report,_=build_report(snapshot,{})
        self.assertEqual(report['api_version_summary']['protected_current_cache_records'],1)
        self.assertEqual(report['api_version_summary']['full_json_versions'],1)
        self.assertTrue(report['api_versions'][0]['is_current_cache_version'])
        self.assertNotIn('response',report['api_versions'][0])
    def test_inconsistent_response_cannot_count_as_protected(self):
        snapshot,version=self.fixture();version['matches']=[]
        report,_=build_report(snapshot,{})
        self.assertEqual(report['api_version_summary']['protected_current_cache_records'],0)
        self.assertEqual(report['api_version_summary']['checksum_failures'],1)
    def test_corrupt_or_missing_scope_is_not_validated(self):
        snapshot,version=self.fixture();key=snapshot['api_versions'][0][0]
        self.assertTrue(api_version_valid(key,version))
        self.assertFalse(api_version_valid(key,{**version,'payload_hash':'wrong'}))
        self.assertFalse(api_version_valid(key,{**version,'raw_scope':'matches_only'}))
