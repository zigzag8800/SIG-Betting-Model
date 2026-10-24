"""As-of leakage and multi-competition schedule regression tests."""
import unittest
from schedule_features_40 import schedule_features, TOP_FIVE

class Schedule40Tests(unittest.TestCase):
    def setUp(self):
        self.matches=[
            {'date':'2026-10-20','league':'UCL','home':'Arsenal','away':'Inter',
             'competition_type':'champions_league','status':'finished','known_at':'2026-09-01'},
            {'date':'2026-10-22','league':'PL','home':'Chelsea','away':'Arsenal',
             'competition_type':'league','status':'finished','known_at':'2026-08-01'},
            {'date':'2026-10-28','league':'CUP','home':'Arsenal','away':'Newcastle',
             'competition_type':'domestic_cup','status':'scheduled','known_at':'2026-10-01'},
            {'date':'2026-10-29','league':'CUP','home':'Arsenal','away':'Brighton',
             'competition_type':'domestic_cup','status':'scheduled','known_at':'2026-10-26'},
        ]

    def test_past_europe_and_known_future(self):
        result=schedule_features(self.matches,'2026-10-24','PL','Arsenal','Everton','2026-10-24')
        self.assertEqual(result['home']['rest_days'],2)
        self.assertEqual(result['home']['europe_last_7d'],1)
        self.assertEqual(result['home']['matches_next_7d'],1)
        self.assertEqual(result['home']['matches_last_7d'],2)

    def test_unannounced_future_not_leaked(self):
        original=schedule_features(self.matches,'2026-10-24','PL','Arsenal','Everton','2026-10-24')
        changed=list(self.matches)+[{'date':'2026-10-27','league':'UCL','home':'Arsenal','away':'PSG',
             'competition_type':'champions_league','status':'scheduled','known_at':'2026-10-25'}]
        new=schedule_features(changed,'2026-10-24','PL','Arsenal','Everton','2026-10-24')
        self.assertEqual(original,new)

    def test_top_five_only(self):
        self.assertEqual(TOP_FIVE,{'PL','PD','SA','BL1','FL1'})
        self.assertNotIn('ELC',TOP_FIVE)

    def test_future_knowledge_forbidden(self):
        with self.assertRaises(ValueError):
            schedule_features(self.matches,'2026-10-25','PL','Arsenal','Everton','2026-10-24')

    def test_international_schedule_never_counts_as_club_match(self):
        games=[{'date':'2026-10-20','league':'international','home':'Arsenal','away':'Denmark',
                'competition_type':'international','status':'finished','known_at':'2026-09-01'}]
        result=schedule_features(games,'2026-10-24','PL','Arsenal','Everton','2026-10-24')
        self.assertIsNone(result['home']['rest_days'])
        self.assertEqual(result['home']['matches_last_7d'],0)
        self.assertFalse(result['home']['fixture_coverage'])

