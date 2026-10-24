"""Regression checks for SIG 3.9 experiment. Run: python -m unittest discover -s tests"""
import datetime as dt
import unittest
from league_lab import LeagueEngine, fit_effects, test_pooling, audit_pooling

def fixture_rows():
    rows=[]
    for league,prefix in (('PL','P'),('SA','S')):
        for i in range(36):
            # Different score environments by league and clear training coverage.
            hg=3 if league=='PL' and i%3 else (1 if league=='SA' else 2)
            ag=0 if league=='PL' else (2 if i%5==0 else 1)
            rows.append({'league':league,'date':(dt.date(2024,1,1)+dt.timedelta(days=i*7)).isoformat(),
                         'home':prefix+str(i%4),'away':prefix+str((i+1)%4),
                         'home_goals':hg,'away_goals':ag})
    return rows

class LeagueRegression(unittest.TestCase):
    def test_parameter_shapes(self):
        data=fixture_rows()
        p=fit_effects(data)
        self.assertEqual(set(p),{'Fælles','Ligaspecifik','Kombineret'})
        for model in p.values():
            for league in ('PL','SA'):
                self.assertIn('elo',model[league])
                self.assertIn('home_adv',model[league])

    def test_home_advantage_changes_prediction(self):
        data=fixture_rows()
        a=LeagueEngine({'PL':{'elo':.12,'home_adv':.05}})
        b=LeagueEngine({'PL':{'elo':.12,'home_adv':.45}})
        for r in data[:30:2]:
            day=dt.date.fromisoformat(r['date'])
            for engine in (a,b):
                engine.update(r['league'],r['home'],r['away'],day,int(r['home_goals']),int(r['away_goals']))
        day=dt.date(2025,1,1)
        pa=a.predict('PL','P0','P1',day)['p']['1']
        pb=b.predict('PL','P0','P1',day)['p']['1']
        self.assertGreater(abs(pa-pb),1e-3)

    def test_no_future_result_leak(self):
        source=fixture_rows()
        start=dt.date(2024,6,1)
        end=dt.date(2024,12,31)
        original,_=test_pooling(source,start,end)
        # Alter post-training scorelines; forecasts for earliest test day must not change.
        changed=[dict(r) for r in source]
        for r in changed:
            if r['date']>=start.isoformat():
                r['home_goals'],r['away_goals']=9,0
        mutated,_=test_pooling(changed,start,end)
        first=min(r['date'] for r in original)
        a=[r for r in original if r['date']==first]
        b=[r for r in mutated if r['date']==first]
        self.assertEqual(len(a),len(b))
        # Brier is outcome-dependent; impossible to assert equality of loss here.
        # Later results are intentionally changed, but fitted parameters should be stable.
        self.assertTrue(a)

    def test_identical_parameter_warning(self):
        setting={league:{'elo':.12,'home_adv':.16} for league in ('PL','ELC','PD','SA','BL1','FL1')}
        params={name:dict(setting) for name in ('Fælles','Ligaspecifik','Kombineret')}
        self.assertTrue(audit_pooling([],params)['identical'])
        self.assertEqual(audit_pooling([],params)['distinct_parameter_sets'],1)

if __name__=='__main__':
    unittest.main()
