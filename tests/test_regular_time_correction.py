import copy
import unittest
from unittest.mock import Mock
from persistent_store import content_key,StorageError
from regular_time_correction import prepare_correction,commit_correction,provider_final_fields
from match_lifecycle import classify

class RegularTimeCorrectionTests(unittest.TestCase):
    def setUp(self):
        self.old=dict(source='football-data.org',match_id='557838',league='ELC',season='2025',date='2026-05-12',kickoff_utc='2026-05-12T19:00:00Z',status='FINISHED',home='H',away='A',home_team_id='1',away_team_id='2',home_goals=2,away_goals=1)
        self.raw={**self.old,'score_duration':'EXTRA_TIME','regular_time_home_goals':0,'regular_time_away_goals':0}
        self.snapshot=dict(history=[self.old],fixtures=[dict(date='future')],backtest_results=[dict(brier=.2)],backtest_signature=[1],lab_rows=[dict(brier=.3)],lab_signature=[1],benchmark_result=['unaffected'])
    def prepare(self,snapshot=None,raw=None):
        return prepare_correction(snapshot or self.snapshot,[raw or self.raw],'football-data.org','557838',corrected_at='2026-10-24T12:00:00Z')
    def test_only_target_score_changes_and_original_evidence_is_retained(self):
        before=copy.deepcopy(self.snapshot);updated,record=self.prepare();row=updated['history'][0]
        self.assertEqual((row['home_goals'],row['away_goals']),(0,0))
        self.assertEqual((row['provider_full_time_home_goals'],row['provider_full_time_away_goals']),(2,1))
        self.assertEqual(record['before'],self.old);self.assertEqual(record['evidence'],self.raw)
        self.assertEqual(self.snapshot,before);self.assertEqual(updated['fixtures'],before['fixtures'])
        self.assertNotIn('known_at',row)
    def test_old_test_arrays_retained_but_signatures_are_stale(self):
        updated,record=self.prepare()
        for name in ('backtest_results','lab_rows','benchmark_result'):self.assertEqual(updated[name],self.snapshot[name])
        self.assertEqual(updated['backtest_signature'][0],'STALE_AFTER_DATA_CORRECTION')
        self.assertEqual(updated['lab_signature'][0],'STALE_AFTER_DATA_CORRECTION')
    def test_repeat_is_noop_and_lifecycle_recognizes_corrected_scope(self):
        updated,_=self.prepare();repeat,record=self.prepare(updated)
        self.assertIsNone(record);self.assertEqual(repeat,updated)
        self.assertEqual(classify(updated['history'][0],self.raw)['action'],'verified_regular_time')
    def test_rejects_wrong_team_date_score_or_missing_regular_time(self):
        for patch in (dict(home_team_id='9'),dict(date='2026-05-13'),dict(home_goals=3),dict(regular_time_home_goals=None),dict(status='AWARDED'),dict(score_duration='REGULAR')):
            with self.subTest(patch=patch),self.assertRaises(ValueError):self.prepare(raw={**self.raw,**patch})
    def test_duplicate_evidence_cannot_select_arbitrary_winner(self):
        with self.assertRaises(ValueError):prepare_correction(self.snapshot,[self.raw,self.raw],'football-data.org','557838')
    def test_commit_refuses_stale_workspace_without_writing(self):
        store=Mock();store.audit_snapshot.return_value=dict(current=self.snapshot,api=[])
        with self.assertRaises(StorageError):commit_correction(store,'wrong','football-data.org','557838')
        store.save_workspace.assert_not_called()
    def test_save_failure_does_not_mutate_snapshot(self):
        store=Mock();before=copy.deepcopy(self.snapshot)
        response=dict(id=557838,utcDate=self.old['kickoff_utc'],status='FINISHED',homeTeam=dict(id=1,name='H'),awayTeam=dict(id=2,name='A'),score=dict(fullTime=dict(home=2,away=1),regularTime=dict(home=0,away=0),duration='EXTRA_TIME'))
        store.audit_snapshot.return_value=dict(current=self.snapshot,api=[('hash:ELC:2025',[response])]);store.save_workspace.side_effect=StorageError('concurrent update')
        with self.assertRaises(StorageError):commit_correction(store,content_key(self.snapshot),'football-data.org','557838')
        self.assertEqual(self.snapshot,before)
    def test_future_import_uses_90_minute_score_and_preserves_fulltime(self):
        fields=provider_final_fields(dict(fullTime=dict(home=2,away=1),regularTime=dict(home=0,away=0),duration='EXTRA_TIME'))
        self.assertEqual(fields['home_goals'],0);self.assertEqual(fields['away_goals'],0)
        self.assertEqual(fields['provider_full_time_home_goals'],2)
    def test_extra_time_without_regular_time_and_invalid_scores_rejected(self):
        self.assertIsNone(provider_final_fields(dict(fullTime=dict(home=2,away=1),duration='EXTRA_TIME')))
        self.assertIsNone(provider_final_fields(dict(fullTime=dict(home=True,away=0),duration='REGULAR')))
