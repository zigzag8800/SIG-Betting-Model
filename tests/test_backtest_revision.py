import copy
import datetime as dt
import unittest
from sig_model import Engine,load_history
from backtest_revision import recompute,revision_report,indexed

class BacktestRevisionTests(unittest.TestCase):
    def setUp(self):
        self.history=[]
        for day in range(1,16):
            for league in ('PL','ELC'):
                self.history.append(dict(date=f'2026-10-{day:02}',league=league,home='H',away='A',home_goals=1,away_goals=0))
        self.asof=dt.date(2026,10,24)
        self.stored=load_history(Engine(),self.history,cutoff=self.asof,backtest=True)
        self.previous=dict(history=copy.deepcopy(self.history),backtest_results=self.stored,backtest_signature=[len(self.history),'2026-10-24','test',0.0,[]])
    def test_controlled_replay_reproduces_old_test_and_changes_only_affected_league(self):
        changed=copy.deepcopy(self.history)
        row=next(r for r in changed if r['league']=='ELC' and r['date']=='2026-10-10');row['home_goals']=0
        new,report=recompute(changed,self.asof,0.0,[],'test',self.previous)
        self.assertTrue(report['stored_reference_reproduced']);self.assertTrue(report['same_settings_as_stored'])
        self.assertTrue(report['identical_fixture_set']);self.assertEqual(report['changed_actual_matches'],1)
        self.assertEqual(len(report['changed_input_matches']),1)
        self.assertEqual({r['league'] for r in report['changes']},{'ELC'})
        old_keyed=indexed(self.stored);new_keyed=indexed(new)
        for key in old_keyed:
            if key[0]<'2026-10-10':self.assertEqual(old_keyed[key],new_keyed[key])
        self.assertEqual(self.previous['history'],self.history)
    def test_identical_history_is_exact_replay(self):
        _,report=recompute(self.history,self.asof,0.0,[],'test',self.previous)
        self.assertEqual(report['changed_test_rows'],0)
        self.assertTrue(all(v==0 for v in report['delta_after_minus_before'].values()))
    def test_settings_mismatch_and_wrong_stored_results_are_explicit(self):
        old=copy.deepcopy(self.previous);old['backtest_results'][0]['brier']=99
        _,report=recompute(self.history,self.asof,0.16,[],'test',old)
        self.assertFalse(report['stored_reference_reproduced']);self.assertFalse(report['same_settings_as_stored'])
    def test_duplicate_fixtures_rejected(self):
        with self.assertRaises(ValueError):indexed([self.stored[0],self.stored[0]])
    def test_no_previous_snapshot_retains_normal_backtest_behavior(self):
        result,report=recompute(self.history,self.asof,0.0,[],'test')
        self.assertEqual(result,self.stored);self.assertIsNone(report)
