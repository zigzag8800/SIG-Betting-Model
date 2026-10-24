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
    def test_raw_source_and_versions_audited_separately(self):
        import base64
        raw=b'Div,Date,HomeTeam,AwayTeam,FTHG,FTAG\nE0,01/08/2025,H,A,1,0\n'
        snap=dict(api=[],inventory=[],versions=[],current={},files=[('digest',dict(name='E0.csv',content=base64.b64encode(raw).decode()))],old_workspaces=[('v1',dict(history=[self.old]))])
        report,_=build_report(snap,{})
        self.assertEqual(report['raw_files'][0]['coverage'][0]['valid_results'],1)
        self.assertEqual(report['raw_files'][0]['coverage'][0]['season'],'unknown')
        self.assertEqual(report['historical_versions'][0]['coverage'][0]['rows'],1)
        self.assertEqual(report['coverage'],[])

class BundleAuditTests(unittest.TestCase):
    def bundle(self,entries):
        import io,zipfile,base64
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:
            for name,raw in entries:z.writestr(name,raw)
        return dict(name='saved.zip',content=base64.b64encode(out.getvalue()).decode())
    def test_every_division_audited_including_unselected(self):
        raw=b'Div,Date,HomeTeam,AwayTeam,FTHG,FTAG\nF2,01/08/2025,H,A,1,0\n'
        report=audit_bundle(self.bundle([('F2.csv',raw),('E0.csv',raw.replace(b'F2',b'E0'))]))
        self.assertTrue(report['complete']);self.assertEqual(len(report['members']),2)
        self.assertEqual(report['members'][0]['coverage'][0]['competition'],'F2')
        self.assertTrue(report['members'][0]['status_unverified'])
    def test_traversal_and_non_csv_are_reported_not_extracted(self):
        report=audit_bundle(self.bundle([('../bad.csv',b'bad'),('readme.txt',b'notes')]))
        self.assertFalse(report['complete']);self.assertIn('error',report['members'][0])
        self.assertEqual(report['members'][1]['skipped'],'non-CSV member')
    def test_oversized_expansion_stops_audit(self):
        report=audit_bundle(self.bundle([('large.csv',b'x'*(5*1024*1024+1))]))
        self.assertFalse(report['complete']);self.assertIn('error',report['members'][0])
    def test_non_integer_scores_and_date_conflicts_counted(self):
        rows=[dict(league='PL',date='2025-01-01',home='H',away='A',home_goals=1.2,away_goals=0,kickoff_utc='2025-01-02T12:00:00Z')]
        report=summarize(rows,'test')[0]
        self.assertEqual(report['valid_results'],0);self.assertEqual(report['date_kickoff_mismatch'],1)
    def test_invalid_source_results_are_identified_without_changing_archive(self):
        raw=b'Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR\nF2,01/08/2025,H,A,,,\nF2,02/08/2025,C,D,1,0,A\n'
        report=audit_csv(raw,'F2.csv','test')
        self.assertEqual(report['invalid_result_count'],1)
        self.assertEqual(report['invalid_result_rows'][0]['row_number'],2)
        self.assertEqual(report['result_code_conflicts'],1)
