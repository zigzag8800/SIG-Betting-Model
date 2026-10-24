import unittest
from archive_audit import *

class ArchiveAuditTests(unittest.TestCase):
    def setUp(self):
        self.old=dict(date='2025-08-01',league='PL',home='H',away='A',home_goals=1,away_goals=0)
        self.cached={**self.old,'match_id':'1','home_team_id':'2','away_team_id':'3','source':'football-data.org','kickoff_utc':'2025-08-01T12:00:00Z','season':'2025','status':'FINISHED'}
    def test_exact_recovery_only_fills_metadata(self):
        rows,stats=enrich_from_cache([self.old],[self.cached])
        self.assertEqual(stats['updated'],1)
        self.assertEqual(rows[0]['match_id'],'1')
        self.assertNotIn('known_at',rows[0])
        for f in self.old:self.assertEqual(rows[0][f],self.old[f])
        self.assertNotIn('match_id',self.old)
    def test_score_or_identity_conflict_never_repaired(self):
        for candidate in ({**self.cached,'home_goals':2},{**self.cached,'home':'Other'}):
            rows,stats=enrich_from_cache([self.old],[candidate])
            self.assertEqual(rows,[self.old]);self.assertEqual(stats['updated'],0)
        rows,stats=enrich_from_cache([self.old],[self.cached,{**self.cached,'match_id':'9'}])
        self.assertEqual(rows,[self.old]);self.assertEqual(stats['conflicts'],1)
    def test_sparse_import_preserves_ids_and_known_at(self):
        old={**self.cached,'known_at':'2025-08-02'}
        self.assertEqual(merge_metadata([old],[{**self.old,'match_id':''}]),[old])
    def test_conflicting_import_is_rejected(self):
        with self.assertRaises(ValueError):merge_metadata([self.cached],[{**self.old,'home_goals':2}])
        with self.assertRaises(ValueError):merge_metadata([self.cached],[{**self.old,'match_id':'9'}])
    def test_validity_rejects_fraction_boolean_infinity(self):
        for bad in (-1,1.5,True,'NaN','inf',None):
            self.assertFalse(valid_score({**self.old,'home_goals':bad}))
    def test_report_separates_cache_session_and_current(self):
        payload=[dict(id=1,utcDate='2025-08-01T12:00:00Z',homeTeam=dict(id=2,name='H'),awayTeam=dict(id=3,name='A'),status='FINISHED',score=dict(fullTime=dict(home=1,away=0)))]
        snap=dict(api=[('hash:PL:2025',payload)],inventory=[],versions=[],current=dict(history=[self.old]))
        report,cached=build_report(snap,dict(history=[]))
        self.assertEqual(cached[0]['season'],'2025')
        scopes={r['scope']:r for r in report['coverage']}
        self.assertEqual(scopes['postgres:workspace/current']['missing_match_id'],1)
        self.assertEqual(scopes['postgres:api_cache']['missing_match_id'],0)
        self.assertEqual(scopes['postgres:workspace/current']['season'],'unknown')
