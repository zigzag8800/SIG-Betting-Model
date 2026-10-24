import unittest
from competition_archive_40 import convert_research_matches, merge_research_matches, research_coverage

class CompetitionArchiveTests(unittest.TestCase):
    def fixture(self):
        return {'id':99,'utcDate':'2026-10-24T19:00:00Z',
                'homeTeam':{'id':100,'name':'Club A'},'awayTeam':{'id':200,'name':'Club B'},
                'status':'FINISHED'}

    def test_requires_verified_ids(self):
        valid=convert_research_matches([self.fixture()],'CL')
        self.assertEqual(valid[0]['match_id'],'99')
        self.assertIsNone(valid[0]['known_at'])
        invalid={**self.fixture(),'awayTeam':{'name':'Unknown'}}
        self.assertEqual(convert_research_matches([invalid],'CL'),[])

    def test_documented_european_codes(self):
        for code in ('CL','EL','UCL','EC','WC','QUFA'):
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

    def test_coverage_is_diagnostic(self):
        rows=convert_research_matches([self.fixture()],'CL')
        cl=next(x for x in research_coverage(rows) if x['competition']=='CL')
        self.assertEqual(cl['matches'],1)
        self.assertEqual(cl['known_at_available'],0)

if __name__=='__main__':unittest.main()
