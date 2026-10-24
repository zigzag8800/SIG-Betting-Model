import copy
import unittest
from match_lifecycle import classify,preview
from archive_audit import merge_metadata

class MatchLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.old=dict(source='football-data.org',match_id='1',home_team_id='10',away_team_id='20',league='PL',season='2026',home='H',away='A',date='2026-10-01',kickoff_utc='2026-10-01T12:00:00Z',status='TIMED',provider_updated_at='2026-09-01T12:00:00Z')
    def changed(self,**fields):return {**self.old,'provider_updated_at':'2026-09-02T12:00:00Z',**fields}
    def action(self,old,new):return classify(old,new)['action']
    def final(self,**fields):return self.changed(status='FINISHED',home_goals=1,away_goals=0,score_duration='REGULAR',**fields)
    def test_repeat_is_idempotent(self):
        self.assertEqual(self.action(self.old,self.old),'unchanged')
    def test_source_namespaces_do_not_join(self):
        self.assertEqual(self.action(self.old,self.changed(source='other')),'identity_review')
    def test_reschedule_same_id_is_proposal_not_new_match(self):
        new=self.changed(date='2026-10-02',kickoff_utc='2026-10-02T12:00:00Z')
        report=preview([self.old],[new]);self.assertEqual(report['summary'],{'reschedule_review':1})
        self.assertFalse(report['applies_changes'])
        with self.assertRaises(ValueError):merge_metadata([self.old],[new])
    def test_stale_version_rejected(self):
        new=self.changed(status='POSTPONED',provider_updated_at='2026-08-01T12:00:00Z')
        self.assertEqual(self.action(self.old,new),'stale_observation')
    def test_equal_version_different_content_is_conflict(self):
        self.assertEqual(self.action(self.old,{**self.old,'status':'POSTPONED'}),'version_conflict')
    def test_missing_provider_version_never_uses_arrival_as_order(self):
        self.assertEqual(self.action({k:v for k,v in self.old.items() if k!='provider_updated_at'},self.changed(status='POSTPONED')),'version_unknown_review')
    def test_final_score_correction_is_never_silently_applied(self):
        old=self.final();new={**old,'home_goals':2,'provider_updated_at':'2026-09-03T12:00:00Z'}
        self.assertEqual(self.action(old,new),'result_correction_review')
    def test_final_never_downgraded_by_newer_scheduled(self):
        old=self.final();new=self.changed(provider_updated_at='2026-09-03T12:00:00Z')
        self.assertEqual(self.action(old,new),'terminal_status_review')
        with self.assertRaises(ValueError):merge_metadata([old],[new])
    def test_administrative_and_played_results_are_distinct(self):
        for state in ('AWARDED','CANCELLED'):
            self.assertEqual(self.action(None,self.changed(status=state)),'administrative_record')
            self.assertEqual(self.action(self.old,self.changed(status=state)),'administrative_review')
    def test_postponed_and_resumed_are_reviewed(self):
        postponed=self.changed(status='POSTPONED')
        self.assertEqual(self.action(self.old,postponed),'status_update_review')
        self.assertEqual(self.action(postponed,{**self.old,'provider_updated_at':'2026-09-03T12:00:00Z'}),'status_update_review')
    def test_extra_time_penalties_and_unknown_duration_not_90_minutes(self):
        for duration in ('EXTRA_TIME','PENALTY_SHOOTOUT',None):
            self.assertEqual(self.action(self.old,{**self.final(),'score_duration':duration}),'score_scope_review')
    def test_finished_requires_integer_scores(self):
        for bad in (None,-1,True,1.5,'NaN'):
            self.assertEqual(self.action(self.old,{**self.final(),'home_goals':bad}),'invalid_observation')
    def test_new_final_result_requires_review(self):
        self.assertEqual(self.action(self.old,self.final()),'result_available_review')
    def test_different_teams_same_id_is_conflict(self):
        self.assertEqual(self.action(self.old,self.changed(home_team_id='999')),'identity_review')
    def test_duplicate_versions_never_arbitrarily_choose_latest(self):
        report=preview([self.old],[self.old,self.changed(status='POSTPONED')])
        self.assertEqual(report['summary'],{'duplicate_identity_review':1})
    def test_identical_duplicate_observations_collapse(self):
        self.assertEqual(preview([self.old],[self.old,self.old])['summary'],{'unchanged':1})
    def test_omitted_match_is_not_deletion(self):
        report=preview([self.old],[]);self.assertEqual(report['coverage_issues'][0]['issue'],'not_in_cached_response')
    def test_no_inputs_are_mutated(self):
        old=[copy.deepcopy(self.old)];new=[self.changed(status='POSTPONED')];saved=copy.deepcopy((old,new))
        report=preview(old,new);self.assertEqual((old,new),saved)
        self.assertTrue(all(not d['applies_changes'] for d in report['decisions']))
    def test_kickoff_format_does_not_create_false_reschedule(self):
        self.assertEqual(self.action(self.old,{**self.old,'kickoff_utc':'2026-10-01T12:00:00+00:00'}),'unchanged')
    def test_no_fuzzy_match_when_identity_missing(self):
        new={**self.old,'match_id':''}
        self.assertEqual(preview([self.old],[new])['summary'],{'identity_review':1})

    def test_review_preserves_separate_regular_time_score(self):
        result=classify(self.old,{**self.final(),'score_duration':'EXTRA_TIME','regular_time_home_goals':0,'regular_time_away_goals':0})
        self.assertEqual(result['regular_time_score'],(0,0));self.assertEqual(result['incoming_score'],[1,0])
        self.assertFalse(result['applies_changes'])
