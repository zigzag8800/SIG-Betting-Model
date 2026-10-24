"""Real Streamlit reruns with synthetic matches and mocked supplier HTTP only."""
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch
try:
    import streamlit as st
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest=None

@unittest.skipIf(AppTest is None,'Streamlit test dependency not installed')
class AppImportFlows(unittest.TestCase):
    def setUp(self):
        st.cache_data.clear()
        self.old=dict(date='2026-09-01',league='PL',home='Home',away='Away',home_goals=1,away_goals=0)
        self.match=dict(id=42,utcDate='2026-09-01T12:00:00Z',homeTeam=dict(id=1,name='Home'),awayTeam=dict(id=2,name='Away'),status='FINISHED',score=dict(fullTime=dict(home=1,away=0)))
    def app(self,history=None,fixtures=None):
        at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'));at.secrets['SIG_DATABASE_URL']=''
        at.session_state['history']=history or [];at.session_state['fixtures']=fixtures or []
        at.run(timeout=20)
        next(t for t in at.text_input if t.label=='Din API-nøgle (skjult)').set_value('synthetic-test-key')
        next(m for m in at.multiselect if m.label=='Ligaer').set_value(['Premier League'])
        next(m for m in at.multiselect if m.label=='Sæsonernes startår').set_value([2026])
        return at
    def run_import(self,at,matches):
        with patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(dict(matches=matches)).encode())) as network:
            next(b for b in at.button if b.label=='Hent kampdata').click().run(timeout=20)
        self.assertEqual(len(at.exception),0)
        self.assertEqual(network.call_count,1)
    def test_success_preserves_model_fields_and_sets_job_season(self):
        at=self.app([self.old]);self.run_import(at,[self.match])
        row=at.session_state['history'][0]
        for key,value in self.old.items():self.assertEqual(row[key],value)
        self.assertEqual(row['match_id'],'42');self.assertEqual(row['season'],'2026')
        self.assertIn('PL:2026',at.session_state['loaded_combos'])
    def test_fixture_conflict_does_not_partially_replace_history_or_combos(self):
        fixture=dict(date='2026-10-25',league='PL',home='Other H',away='Other A',kickoff_utc='2026-10-25T12:00:00Z',source='football-data.org')
        at=self.app([self.old],[fixture])
        scheduled=dict(id=43,utcDate='2026-10-25T15:00:00Z',homeTeam=dict(id=3,name='Other H'),awayTeam=dict(id=4,name='Other A'),status='TIMED')
        self.run_import(at,[self.match,scheduled])
        self.assertEqual(at.session_state['history'],[self.old])
        self.assertEqual(at.session_state['fixtures'],[fixture])
        self.assertNotIn('loaded_combos',at.session_state)
        self.assertTrue(any('Importkonflikt' in w.value for w in at.warning))
    def test_conflicting_score_keeps_original(self):
        at=self.app([self.old]);bad={**self.match,'score':dict(fullTime=dict(home=2,away=0))}
        self.run_import(at,[bad])
        self.assertEqual(at.session_state['history'],[self.old])
    def test_private_archive_requires_password_before_store_construction(self):
        at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'));at.secrets['SIG_DATABASE_URL']='synthetic-dsn';at.secrets['SIG_OWNER_PASSWORD']='synthetic-owner'
        with patch('persistent_store.Store') as store:
            at.run(timeout=20);store.assert_not_called()
        self.assertEqual(len(at.exception),0)
        self.assertEqual([x.label for x in at.text_input],['Adgang til privat dataarkiv'])

    def test_moved_source_match_id_does_not_create_second_fixture(self):
        fixture=dict(date='2026-10-01',league='PL',home='Home',away='Away',match_id='42',home_team_id='1',away_team_id='2',source='football-data.org',kickoff_utc='2026-10-01T12:00:00Z',status='TIMED')
        at=self.app([], [fixture])
        moved={**self.match,'status':'TIMED','utcDate':'2026-10-02T12:00:00Z','score':{}}
        self.run_import(at,[moved])
        self.assertEqual(at.session_state['fixtures'],[fixture])
        self.assertTrue(any('rescheduling requires review' in w.value for w in at.warning))

    def test_lifecycle_preview_only_reads_saved_cache(self):
        from unittest.mock import Mock
        store=Mock();store.get.side_effect=lambda kind,key: {} if kind=='workspace' else None
        store.log.return_value=[]
        store.audit_snapshot.return_value=dict(inventory=[],versions=[],current={},api=[('synthetic:PL:2026',[{**self.match,'score':{'fullTime':{'home':1,'away':0},'duration':'REGULAR'}}])])
        at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'))
        at.secrets['SIG_DATABASE_URL']='synthetic-dsn';at.secrets['SIG_OWNER_PASSWORD']='synthetic-owner'
        at.session_state['archive_password']='synthetic-owner'
        with patch('persistent_store.Store',return_value=store),patch('urllib.request.urlopen') as network:
            at.run(timeout=20)
            next(b for b in at.button if b.label=='Undersøg PostgreSQL uden downloads').click().run(timeout=20)
            self.assertEqual(len(at.exception),0)
            report,_=at.session_state['_postgres_audit']
            self.assertEqual(report['cache_lifecycle']['summary'],{'new_record_review':1})
            network.assert_not_called();store.save_workspace.assert_not_called();store.reserve.assert_not_called()

    def correction_app(self,fail_save=False):
        import copy
        from unittest.mock import Mock
        from persistent_store import content_key,StorageError
        old=dict(date='2026-05-12',league='ELC',season='2025',home='H',away='A',home_goals=2,away_goals=1,source='football-data.org',match_id='557838',home_team_id='1',away_team_id='2',kickoff_utc='2026-05-12T19:00:00Z',status='FINISHED')
        state=dict(history=[old],fixtures=[],backtest_results=[dict(brier=.2)],backtest_signature=[1],lab_rows=[dict(brier=.3)],lab_signature=[1])
        before=copy.deepcopy(state)
        response=dict(id=557838,utcDate=old['kickoff_utc'],status='FINISHED',homeTeam=dict(id=1,name='H'),awayTeam=dict(id=2,name='A'),score=dict(fullTime=dict(home=2,away=1),regularTime=dict(home=0,away=0),duration='EXTRA_TIME'))
        store=Mock();store.get.side_effect=lambda kind,key:copy.deepcopy(state) if kind=='workspace' else None;store.log.return_value=[]
        store.audit_snapshot.side_effect=lambda:dict(current=copy.deepcopy(state),api=[('hash:ELC:2025',[response])],inventory=[],versions=[])
        def save(updated,expected):
            if fail_save:raise StorageError('concurrent update')
            self.assertEqual(expected,content_key(state))
            state.clear();state.update(copy.deepcopy(updated));return content_key(state)
        store.save_workspace.side_effect=save
        at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'));at.secrets['SIG_DATABASE_URL']='synthetic-dsn';at.secrets['SIG_OWNER_PASSWORD']='synthetic-owner';at.session_state['archive_password']='synthetic-owner'
        return at,store,state,before

    def test_regular_time_correction_commits_then_updates_ui_and_invalidates(self):
        at,store,state,before=self.correction_app()
        with patch('persistent_store.Store',return_value=store),patch('urllib.request.urlopen') as network:
            at.run(timeout=20)
            next(b for b in at.button if b.label=='Undersøg PostgreSQL uden downloads').click().run(timeout=20)
            next(b for b in at.button if b.label=='Gem 0–0 efter 90 minutter med bevaret original').click().run(timeout=20)
            self.assertEqual(len(at.exception),0)
            self.assertEqual(state['history'][0]['home_goals'],0)
            self.assertEqual(state['data_corrections'][0]['before']['home_goals'],2)
            self.assertEqual(state['backtest_results'],before['backtest_results'])
            self.assertEqual(state['backtest_signature'][0],'STALE_AFTER_DATA_CORRECTION')
            self.assertTrue(any('Datakorrektion gemt' in i.value for i in at.info))
            next(b for b in at.button if b.label=='Undersøg PostgreSQL uden downloads').click().run(timeout=20)
            self.assertEqual(at.session_state['_postgres_audit'][0]['cache_lifecycle']['summary'],{'verified_regular_time':1})
            self.assertFalse(any(b.label=='Gem 0–0 efter 90 minutter med bevaret original' for b in at.button))
            network.assert_not_called();store.reserve.assert_not_called()

    def test_failed_correction_never_updates_session_or_test_signatures(self):
        at,store,state,before=self.correction_app(fail_save=True)
        with patch('persistent_store.Store',return_value=store),patch('urllib.request.urlopen') as network:
            at.run(timeout=20)
            next(b for b in at.button if b.label=='Undersøg PostgreSQL uden downloads').click().run(timeout=20)
            next(b for b in at.button if b.label=='Gem 0–0 efter 90 minutter med bevaret original').click().run(timeout=20)
            self.assertEqual(len(at.exception),0);self.assertEqual(state,before)
            self.assertEqual(at.session_state['history'][0]['home_goals'],2)
            self.assertTrue(any('concurrent update' in e.value for e in at.error))
            network.assert_not_called()

    def test_backtest_recompute_replays_previous_snapshot_and_saves_revision(self):
        import copy
        import datetime as dt
        from unittest.mock import Mock
        from persistent_store import content_key
        from sig_model import Engine,load_history
        history=[dict(date=f'2026-10-{day:02}',league='ELC',home='H',away='A',home_goals=1,away_goals=0) for day in range(1,16)]
        asof=dt.date(2026,10,24)
        previous=dict(history=copy.deepcopy(history),backtest_results=load_history(Engine(),history,cutoff=asof,backtest=True),backtest_signature=[len(history),'2026-10-24','test',0.0,[]],source_label='test')
        state=copy.deepcopy(previous);state['history'][9]['home_goals']=0
        state['backtest_signature']=['STALE_AFTER_DATA_CORRECTION','synthetic']
        state['data_corrections']=[dict(match_id='synthetic',previous_workspace_hash=content_key(previous))]
        store=Mock();store.get.side_effect=lambda kind,key:copy.deepcopy(state) if kind=='workspace' else copy.deepcopy(previous) if kind=='workspace_version' else None;store.log.return_value=[]
        def save(updated,expected):
            self.assertEqual(expected,content_key(state));state.clear();state.update(copy.deepcopy(updated));return content_key(state)
        store.save_workspace.side_effect=save
        at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'));at.secrets['SIG_DATABASE_URL']='synthetic-dsn';at.secrets['SIG_OWNER_PASSWORD']='synthetic-owner';at.session_state['archive_password']='synthetic-owner'
        with patch('persistent_store.Store',return_value=store),patch('urllib.request.urlopen') as network:
            at.run(timeout=20)
            next(x for x in at.date_input if x.label=='Analysedato').set_value(asof)
            next(b for b in at.button if b.label=='Kør kronologisk backtest').click().run(timeout=20)
            self.assertEqual(len(at.exception),0)
            revision=state['backtest_revision']
            self.assertTrue(revision['stored_reference_reproduced']);self.assertTrue(revision['same_settings_as_stored']);self.assertTrue(revision['identical_fixture_set'])
            self.assertEqual(len(revision['changed_input_matches']),1)
            self.assertEqual(state['backtest_signature'][0],content_key(state['history']))
            self.assertEqual(previous['backtest_results'][4]['actual'],'1')
            network.assert_not_called();store.reserve.assert_not_called()

    def test_api_version_backfill_uses_database_only_and_preserves_workspace(self):
        from unittest.mock import Mock
        store=Mock();store.get.side_effect=lambda kind,key:{} if kind=='workspace' else None;store.log.return_value=[]
        store.backfill_api_versions.return_value=dict(cache_items_checked=12,versions_added=12,provider_downloads=0,cache_ttl_changed=False)
        at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'));at.secrets['SIG_DATABASE_URL']='synthetic-dsn';at.secrets['SIG_OWNER_PASSWORD']='synthetic-owner';at.session_state['archive_password']='synthetic-owner'
        with patch('persistent_store.Store',return_value=store),patch('urllib.request.urlopen') as network:
            at.run(timeout=20)
            next(b for b in at.button if b.label=='Bevar eksisterende rå API-svar som versioner').click().run(timeout=20)
            self.assertEqual(len(at.exception),0);store.backfill_api_versions.assert_called_once()
            self.assertTrue(any('Rå API-versioner sikret' in s.value for s in at.success))
            network.assert_not_called();store.reserve.assert_not_called();store.save_workspace.assert_not_called();store.save_api_response.assert_not_called()
