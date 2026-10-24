import unittest
from match_identity_audit import audit_match_identity

class IdentityAuditTests(unittest.TestCase):
    def test_missing_provenance_is_reported_not_invented(self):
        row={'league':'PL','date':'2026-10-01','home':'A','away':'B','home_goals':1,'away_goals':0}
        pl=next(r for r in audit_match_identity([row]) if r['Liga']=='PL')
        self.assertEqual(pl['Mangler kamp-ID'],1)
        self.assertEqual(pl['Mangler hold-ID'],1)
        self.assertEqual(pl['Ugyldigt/manglende UTC-kickoff'],1)

    def test_duplicate_ids_and_score_detection(self):
        row={'league':'SA','source':'provider','match_id':'123','date':'2026-10-01',
             'home':'A','away':'B','home_goals':-1,'away_goals':0,
             'home_team_id':'1','away_team_id':'2','kickoff_utc':'2026-10-01T18:00:00Z'}
        sa=next(r for r in audit_match_identity([row,dict(row)]) if r['Liga']=='SA')
        self.assertEqual(sa['Dublerede kilde-kamp-ID'],1)
        self.assertEqual(sa['Ugyldigt resultat'],2)
        self.assertEqual(sa['Ugyldigt/manglende UTC-kickoff'],0)

    def test_conflicting_provider_id_is_flagged(self):
        row={'league':'PL','source':'football-data.org','match_id':'9',
             'date':'2026-10-24','home':'Home','away':'Away',
             'home_team_id':'1','away_team_id':'2','kickoff_utc':'2026-10-24T12:00:00Z',
             'home_goals':1,'away_goals':0}
        other={**row,'away_team_id':'3','away':'Other'}
        summary=next(x for x in audit_match_identity([row,other]) if x['Liga']=='PL')
        self.assertEqual(summary['Modstridende kilde-kamp-ID'],1)

    def test_utc_date_disagreement_is_flagged(self):
        row={'league':'PD','date':'2026-10-24','home':'A','away':'B',
             'home_goals':0,'away_goals':0,'kickoff_utc':'2026-10-25T00:30:00Z'}
        summary=next(x for x in audit_match_identity([row]) if x['Liga']=='PD')
        self.assertEqual(summary['Dato afviger fra UTC-kickoff'],1)

if __name__=='__main__':unittest.main()
