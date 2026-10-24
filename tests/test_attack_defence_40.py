"""Contract tests for isolated SIG 4.0 research model."""
import datetime as dt
import math
import unittest
from attack_defence_40 import AttackDefence40, backtest_40

def rows():
    result=[]
    for league in ('PL','SA'):
        for i in range(85):
            day=dt.date(2023,1,1)+dt.timedelta(days=7*i)
            home='A' if i%2==0 else 'B'
            away='C' if i%2==0 else 'D'
            result.append({'date':day.isoformat(),'league':league,'home':home,'away':away,
                           'home_goals': 3 if league=='PL' else 1,
                           'away_goals':0 if league=='PL' else 2})
    return result

class ResearchModelTests(unittest.TestCase):
    def test_probabilities(self):
        m=AttackDefence40().fit(rows(),dt.date(2024,1,1))
        for lg in ('PL','SA'):
            result=m.predict(lg,'A','C')
            self.assertAlmostEqual(sum(result['p'].values()),1,places=9)
            self.assertTrue(all(0<=p<=1 for p in result['p'].values()))
            self.assertTrue(result['home_xg']>0)

    def test_future_invariance(self):
        base=rows()
        boundary=dt.date(2024,1,1)
        first=AttackDefence40().fit(base,boundary).predict('PL','A','C')
        mutated=[dict(r) for r in base]
        for r in mutated:
            if r['date']>=boundary.isoformat():
                r['home_goals'],r['away_goals']=0,9
        second=AttackDefence40().fit(mutated,boundary).predict('PL','A','C')
        self.assertEqual(first,second)

    def test_league_strengths_vary(self):
        m=AttackDefence40().fit(rows(),dt.date(2024,1,1))
        self.assertNotEqual(m.leagues['PL'][:2],m.leagues['SA'][:2])

    def test_rolling_backtest(self):
        scored=backtest_40(rows(),dt.date(2024,1,1),dt.date(2024,6,1),step_days=30)
        self.assertTrue(scored)
        self.assertTrue(all(x['date']>= '2024-01-01' for x in scored))
        self.assertTrue(all(math.isfinite(x['logloss']) for x in scored))

if __name__=='__main__':unittest.main()
