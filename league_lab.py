"""SIG 3.9: league pooling experiment, fitted exclusively on earlier chronological data.

This is a *parameter pooling* experiment for Elo sensitivity. It does not
claim to implement a full hierarchical attack/defence model yet.
"""
import math
from collections import defaultdict
from itertools import groupby
from model_lab import ExperimentalEngine
from sig_model import date

LEAGUES=('PL','PD','SA','BL1','FL1')
BASE=.12
DEFAULT_HOME_ADV=.16
GRID=(.08,.12,.16,.20,.24)
SHRINK_GAMES=300

class LeagueEngine(ExperimentalEngine):
    def __init__(self, effects):
        super().__init__(form_strength=.16,form_window=10)
        self.effects=effects
    def expected_goals(self,league,home,away,today):
        old_elo,old_home=self.elo_effect,self.home_adv
        setting=self.effects.get(league,{'elo':BASE,'home_adv':DEFAULT_HOME_ADV})
        self.elo_effect,self.home_adv=setting['elo'],setting['home_adv']
        try: return super().expected_goals(league,home,away,today)
        finally:
            self.elo_effect,self.home_adv=old_elo,old_home

def _scores(rows,effect):
    engine=ExperimentalEngine(form_strength=.16,form_window=10,elo_effect=effect)
    scores=defaultdict(list)
    for ds, block in groupby(sorted(rows,key=lambda r:(r['date'][:10],r['league'])),key=lambda r:r['date'][:10]):
        day=date(ds); matches=list(block)
        for r in matches:
            p=engine.predict(r['league'],r['home'],r['away'],day)
            if p['history_min']<5: continue
            actual='1' if int(r['home_goals'])>int(r['away_goals']) else 'X' if int(r['home_goals'])==int(r['away_goals']) else '2'
            scores[r['league']].append(-math.log(max(1e-12,p['p'][actual])))
        for r in matches:
            engine.update(r['league'],r['home'],r['away'],day,int(r['home_goals']),int(r['away_goals']))
    return scores

def fit_effects(train):
    grid_scores={effect:_scores(train,effect) for effect in GRID}
    global_loss={effect:sum(sum(v) for v in grid_scores[effect].values())/
                         max(1,sum(len(v) for v in grid_scores[effect].values())) for effect in GRID}
    common=min(GRID,key=lambda x:global_loss[x])
    goals=defaultdict(lambda:[0,0,0])
    for r in train:
        hg,ag=int(r['home_goals']),int(r['away_goals'])
        if hg<0 or ag<0: continue
        v=goals[r['league']]
        v[0]+=hg
        v[1]+=ag
        v[2]+=1
    sum_h=sum(v[0] for v in goals.values())
    sum_a=sum(v[1] for v in goals.values())
    home_all=max(-.3,min(.6,math.log((sum_h+1)/(sum_a+1))))
    params={'Fælles':{},'Ligaspecifik':{},'Kombineret':{}}
    for lg in LEAGUES:
        scores={e:grid_scores[e].get(lg,[]) for e in GRID}
        best=min(GRID,key=lambda e:sum(scores[e])/len(scores[e])) if scores[common] else common
        n=len(scores[common])
        h,a,m=goals[lg]
        home_raw=max(-.3,min(.6,math.log((h+1)/(a+1)))) if m else home_all
        home_separate=home_all+m/(m+200)*(home_raw-home_all)
        home_mixed=home_all+m/(m+500)*(home_raw-home_all)
        elo_mixed=common+n/(n+300)*(best-common)
        params['Fælles'][lg]={'elo':common,'home_adv':home_all}
        params['Ligaspecifik'][lg]={'elo':best,'home_adv':home_separate}
        params['Kombineret'][lg]={'elo':elo_mixed,'home_adv':home_mixed}
    return params

def test_pooling(rows,train_end,test_end):
    """Fit on dates strictly earlier than train_end, then predict later dates."""
    train=[r for r in rows if r['date'][:10]<train_end.isoformat()]
    if not train: return [],{}
    parameters=fit_effects(train)
    engines={name:LeagueEngine(effect) for name,effect in parameters.items()}
    records=[]
    ordered=sorted((r for r in rows if r['date'][:10]<test_end.isoformat()),key=lambda r:(r['date'][:10],r['league']))
    for ds,block in groupby(ordered,key=lambda r:r['date'][:10]):
        day=date(ds);matches=list(block)
        if day>=train_end:
            for r in matches:
                actual='1' if int(r['home_goals'])>int(r['away_goals']) else 'X' if int(r['home_goals'])==int(r['away_goals']) else '2'
                for label,engine in engines.items():
                    p=engine.predict(r['league'],r['home'],r['away'],day)
                    if p['history_min']<5: continue
                    probs=p['p']
                    brier=sum((probs[k]-(k==actual))**2 for k in ('1','X','2'))/3
                    records.append({'model':label,'league':r['league'],'date':ds,'brier':brier,
                                    'logloss':-math.log(max(1e-12,probs[actual]))})
        for r in matches:
            for engine in engines.values():
                engine.update(r['league'],r['home'],r['away'],day,int(r['home_goals']),int(r['away_goals']))
    return records,parameters



def parameter_search_report(train):
    """Explain why the tuned Elo variants collapse, without altering predictions."""
    scores={effect:_scores(train,effect) for effect in GRID}
    result=[]
    for league in ('ALLE',)+LEAGUES:
        for effect in GRID:
            values=[v for x in scores[effect].values() for v in x] if league=='ALLE' else scores[effect].get(league,[])
            if values:
                result.append({'Liga':league,'Elo-vægt':effect,'Kampe':len(values),
                               'Trænings-log-loss':round(sum(values)/len(values),6)})
    return result

def audit_pooling(records, parameters, tolerance=1e-12):
    """Explicitly report whether fitted models differ in parameters and predictions."""
    variants=tuple(parameters)
    param_distinct=len({tuple((round(parameters[name][lg]['elo'],12),round(parameters[name][lg]['home_adv'],12)) for lg in LEAGUES)
                        for name in variants})
    grouped=defaultdict(dict)
    for r in records:
        key=(r['date'],r['league'])
        grouped[key].setdefault(r['model'],[]).append((r['brier'],r['logloss']))
    # Multiple matches per league/date are compared in their stable iteration order.
    groups=len(grouped)
    diff_count=0
    for values in grouped.values():
        if not all(n in values for n in variants): continue
        sample=[values[n] for n in variants]
        if any(len(seq)!=len(sample[0]) for seq in sample): continue
        if any(abs(a[0]-b[0])>tolerance or abs(a[1]-b[1])>tolerance
               for seq in sample[1:] for a,b in zip(sample[0],seq)):
            diff_count+=1
    return {'distinct_parameter_sets':param_distinct,
            'league_date_groups':groups,
            'groups_with_prediction_difference':diff_count,
            'identical':param_distinct==1 or (groups>0 and diff_count==0)}
