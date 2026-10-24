"""Tests for SIG 4.0 data contracts (no provider downloads)."""
import unittest
from data_quality_40 import coverage_report,coverage_risks,validate_identity_data,player_load

class DataQualityTests(unittest.TestCase):
    def test_coverage_and_duplicates(self):
        r={'date':'2026-10-01','league':'PL','home':'A','away':'B','home_goals':1,'away_goals':0}
        output=coverage_report([r,dict(r)],[],[],[],[],[])
        pl=next(x for x in output if x['Liga']=='PL')
        self.assertEqual(pl['Afsluttede kampe'],2)
        self.assertEqual(pl['Dublerede afsluttede kampe'],1)
        self.assertEqual(len(output),5)

    def test_membership_and_international_load(self):
        players=[{'player_id':'p1'}]
        memberships=[{'player_id':'p1','club_id':'c1','from_date':'2026-01-01','to_date':''}]
        appearances=[{'player_id':'p1','match_id':'m1','date':'2026-10-20','known_at':'2026-10-21',
                      'competition_type':'international','minutes':'85'},
                     {'player_id':'p1','match_id':'m2','date':'2026-10-22','known_at':'2026-10-23',
                      'competition_type':'league','minutes':'72'}]
        self.assertTrue(validate_identity_data(players,memberships,appearances))
        load=player_load(appearances,memberships,'p1','c1','2026-10-24')
        self.assertEqual(load['minutes'],157)
        self.assertEqual(load['international_minutes'],85)

    def test_future_information_is_not_used(self):
        m=[{'player_id':'p1','club_id':'c1','from_date':'2026-01-01','to_date':''}]
        a=[{'player_id':'p1','match_id':'m1','date':'2026-10-20','known_at':'2026-10-25',
             'competition_type':'international','minutes':90}]
        self.assertEqual(player_load(a,m,'p1','c1','2026-10-24')['minutes'],0)

    def test_conflicting_club_memberships_rejected(self):
        p=[{'player_id':'p1'}]
        m=[{'player_id':'p1','club_id':'A','from_date':'2026-01-01','to_date':'2026-08-01'},
           {'player_id':'p1','club_id':'B','from_date':'2026-07-01','to_date':''}]
        with self.assertRaises(ValueError):
            validate_identity_data(p,m,[])
    def test_duplicate_player_match_rejected(self):
        p=[{'player_id':'p1'}]
        m=[{'player_id':'p1','club_id':'A','from_date':'2026-01-01','to_date':''}]
        a={'player_id':'p1','match_id':'m1','date':'2026-10-20','known_at':'2026-10-21',
           'competition_type':'international','minutes':90}
        with self.assertRaises(ValueError):
            validate_identity_data(p,m,[a,dict(a)])

    def test_minutes_known_before_match_rejected(self):
        p=[{'player_id':'p1'}]
        m=[{'player_id':'p1','club_id':'A','from_date':'2026-01-01','to_date':''}]
        a=[{'player_id':'p1','match_id':'m1','date':'2026-10-20','known_at':'2026-10-19',
            'competition_type':'international','minutes':90}]
        with self.assertRaises(ValueError):
            validate_identity_data(p,m,a)

    def test_data_provenance_gaps(self):
        row={'date':'2026-10-01','league':'PL','home':'A','away':'B','home_goals':1,'away_goals':0}
        result=coverage_risks([row],[])
        pl=next(item for item in result if item['Liga']=='PL')
        self.assertEqual(pl['Mangler kamp-ID'],1)
        self.assertEqual(pl['Mangler kickoff UTC'],1)
        self.assertEqual(pl['Mangler datakilde'],1)
        self.assertEqual(pl['Mangler tilgængelighedstid'],1)

if __name__=='__main__':unittest.main()
