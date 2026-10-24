import unittest
from competition_archive_40 import convert_research_matches, merge_research_matches, research_coverage

class CompetitionArchiveTests(unittest.TestCase):
    def fixture(self):
        return {'id':99,'utcDate':'2026-10-24T19:00:00Z',
                'homeTeam':{'id':100,'name':'Club A'},'awayTeam':{'id':200,'name':'Club B'},
                'status':'FINISHED','score':{'fullTime':{'home':2,'away':1}}}

    def test_requires_verified_ids(self):
        valid=convert_research_matches([self.fixture()],'CL')
        self.assertEqual(valid[0]['match_id'],'99')
        self.assertIsNone(valid[0]['known_at'])
        invalid={**self.fixture(),'awayTeam':{'name':'Unknown'}}
        self.assertEqual(convert_research_matches([invalid],'CL'),[])

    def test_documented_european_codes(self):
        for code in ('CL','EL','UCL','EC','WC','QUFA','FAC','FLC','DFB','CDR'):
            with self.subTest(code=code):
                self.assertEqual(convert_research_matches([self.fixture()],code)[0]['competition'],code)
        with self.assertRaises(ValueError):
            convert_research_matches([self.fixture()],'ECL')

    def test_reject_unknown_competition(self):
        with self.assertRaises(ValueError):
            convert_research_matches([self.fixture()],'PL')

    def test_idempotent_merge(self):
        records=convert_research_matches([self.fixture()],'CL')
        merged,problems=merge_research_matches(records,records)
        self.assertEqual(len(merged),1)
        self.assertFalse(problems)

    def test_conflicting_team_id_preserves_first(self):
        old=convert_research_matches([self.fixture()],'CL')
        new=[{**old[0],'home_team_id':'999'}]
        merged,problems=merge_research_matches(old,new)
        self.assertEqual(merged[0]['home_team_id'],'100')
        self.assertEqual(len(problems),1)

    def test_conflicting_kickoff_does_not_overwrite(self):
        old=convert_research_matches([self.fixture()],'CL')
        changed=[{**old[0],'kickoff_utc':'2026-10-25T19:00:00Z'}]
        merged,issues=merge_research_matches(old,changed)
        self.assertEqual(merged[0]['kickoff_utc'],old[0]['kickoff_utc'])
        self.assertEqual(len(issues),1)

    def test_blank_source_fields_do_not_erase_existing(self):
        old=convert_research_matches([self.fixture()],'CL')
        incoming=[{**old[0],'home':'','known_at':None}]
        merged,issues=merge_research_matches(old,incoming)
        self.assertFalse(issues)
        self.assertEqual(merged[0]['home'],'Club A')

    def test_finished_result_requires_valid_scores(self):
        match=self.fixture()
        self.assertEqual(convert_research_matches([match],'CL')[0]['home_goals'],2)
        missing={**match,'score':{'fullTime':{'home':None,'away':1}}}
        self.assertEqual(convert_research_matches([missing],'CL'),[])

    def test_conflicting_final_score_is_reported(self):
        old=convert_research_matches([self.fixture()],'CL')
        changed=[{**old[0],'home_goals':4}]
        merged,issues=merge_research_matches(old,changed)
        self.assertEqual(merged[0]['home_goals'],2)
        self.assertEqual(len(issues),1)

    def test_scheduled_game_gains_finished_score(self):
        scheduled={**self.fixture(),'status':'SCHEDULED','score':{}}
        early=convert_research_matches([scheduled],'CL')
        late=convert_research_matches([self.fixture()],'CL')
        merged,issues=merge_research_matches(early,late)
        self.assertFalse(issues)
        self.assertEqual(merged[0]['home_goals'],2)
        self.assertEqual(merged[0]['status'],'FINISHED')

    def test_stale_scheduled_record_cannot_downgrade_result(self):
        finished=convert_research_matches([self.fixture()],'CL')
        scheduled={**self.fixture(),'status':'SCHEDULED','score':{}}
        stale=convert_research_matches([scheduled],'CL')
        merged,issues=merge_research_matches(finished,stale)
        self.assertFalse(issues)
        self.assertEqual(merged[0]['status'],'FINISHED')
        self.assertEqual(merged[0]['home_goals'],2)

    def test_finished_without_score_not_counted_as_valid_result(self):
        row=convert_research_matches([self.fixture()],'CL')[0]
        corrupt={**row,'home_goals':None}
        coverage=next(x for x in research_coverage([corrupt]) if x['competition']=='CL')
        self.assertEqual(coverage['finished'],1)
        self.assertEqual(coverage['finished_with_score'],0)

    def test_coverage_is_diagnostic(self):
        rows=convert_research_matches([self.fixture()],'CL')
        cl=next(x for x in research_coverage(rows) if x['competition']=='CL')
        self.assertEqual(cl['matches'],1)
        self.assertEqual(cl['finished'],1)
        self.assertEqual(cl['finished_with_score'],1)
        self.assertEqual(cl['stable_team_ids'],1)
        self.assertEqual(cl['known_at_available'],0)

if __name__=='__main__':unittest.main()

class InvalidResearchScores(unittest.TestCase):
    def test_fractional_boolean_and_negative_scores_not_truncated(self):
        from competition_archive_40 import convert_research_matches
        for bad in (True,-1,1.5,'NaN'):
            match=dict(id=1,utcDate='2026-01-01T12:00:00Z',homeTeam=dict(id=1,name='H'),awayTeam=dict(id=2,name='A'),status='FINISHED',score=dict(fullTime=dict(home=bad,away=0)))
            self.assertEqual(convert_research_matches([match],'CL'),[])
