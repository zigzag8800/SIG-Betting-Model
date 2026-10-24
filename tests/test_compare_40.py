"""Independent paired-comparison correctness checks."""
import datetime as dt
import unittest
from compare_40 import compare_sig_e_40,validate_pairs,summarize_pairs

def synthetic():
    out=[]
    teams=['A','B','C','D']
    for i in range(84):
        day=(dt.date(2023,1,1)+dt.timedelta(days=i*7)).isoformat()
        for league in ('PL','SA'):
            h=teams[i%4];a=teams[(i+1)%4]
            out.append({'date':day,'league':league,'home':h,'away':a,
                        'home_goals':2 if league=='PL' else 1,
                        'away_goals':0 if league=='PL' else i%3})
    return out

class ComparisonTests(unittest.TestCase):
    def test_pairs_and_period(self):
        rows=compare_sig_e_40(synthetic(),'2024-01-01','2024-06-01')
        n=validate_pairs(rows)
        self.assertGreater(n,0)
        self.assertEqual(len(rows),2*n)
        self.assertEqual(len([r for r in summarize_pairs(rows) if r['league']=='ALLE']),2)
        self.assertTrue(all('2024-01-01'<=r['date']<'2024-06-01' for r in rows))

    def test_future_invariance_of_first_day_probabilities(self):
        base=synthetic();a=compare_sig_e_40(base,'2024-01-01','2024-06-01')
        changed=[dict(r) for r in base]
        for r in changed:
            if r['date']>='2024-01-01':r['home_goals'],r['away_goals']=0,8
        b=compare_sig_e_40(changed,'2024-01-01','2024-06-01')
        first=min(r['date'] for r in a)
        extract=lambda rows:{(r['league'],r['home'],r['away'],r['model']):(r['p1'],r['px'],r['p2']) for r in rows if r['date']==first}
        self.assertEqual(extract(a),extract(b))

    def test_reject_mismatched_results(self):
        records=compare_sig_e_40(synthetic(),'2024-01-01','2024-06-01')
        with self.assertRaises(ValueError):
            validate_pairs(records[:-1])
if __name__=='__main__':unittest.main()
