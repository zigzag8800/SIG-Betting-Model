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

if __name__=='__main__':unittest.main()
