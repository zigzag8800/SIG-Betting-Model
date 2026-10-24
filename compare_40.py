"""Fair, time-ordered SIG E versus SIG 4.0 research benchmark.

No automatic external data retrieval and no production model updates.
"""
import datetime as dt
import math
from collections import defaultdict
from sig_model import date
from model_lab import ExperimentalEngine
from attack_defence_40 import AttackDefence40

def compare_sig_e_40(rows,first_test_date,last_test_date,refit_days=30,min_prior_games=5):
    start=date(str(first_test_date));end=date(str(last_test_date))
    if not start<end:raise ValueError('Test period must have positive duration')
    if refit_days<1:raise ValueError('refit_days must be positive')
    ordered=sorted((r for r in rows if date(r['date'])<end),
                   key=lambda r:(r['date'][:10],r['league'],r['home'],r['away']))
    e=ExperimentalEngine(form_strength=.16,form_window=10,elo_effect=.20)
    history=defaultdict(int)
    all_results=[]
    next_fit=start
    fit_end=None
    four=None
    ix=0
    while ix<len(ordered):
        day=date(ordered[ix]['date'])
        batch=[]
        while ix<len(ordered) and date(ordered[ix]['date'])==day:
            batch.append(ordered[ix]);ix+=1
        if day>=start:
            if four is None or day>=fit_end:
                four=AttackDefence40().fit(ordered,day)
                fit_end=day+dt.timedelta(days=refit_days)
            for r in batch:
                league,h,a=r['league'],r['home'],r['away']
                if min(history[(league,h)],history[(league,a)])<min_prior_games:
                    continue
                if league not in four.leagues:continue
                pe=e.predict(league,h,a,day)['p']
                p4=four.predict(league,h,a)['p']
                hg,ag=int(r['home_goals']),int(r['away_goals'])
                actual='1' if hg>ag else 'X' if hg==ag else '2'
                for model,p in [('SIG E',pe),('SIG 4.0',p4)]:
                    all_results.append({
                        'date':day.isoformat(),'league':league,'home':h,'away':a,
                        'model':model,'actual':actual,'p1':p['1'],'px':p['X'],'p2':p['2'],
                        'brier':sum((p[k]-(k==actual))**2 for k in ('1','X','2'))/3,
                        'logloss':-math.log(max(p[actual],1e-12))
                    })
        # Withhold today's results until every fixture has been forecast.
        for r in batch:
            league,h,a=r['league'],r['home'],r['away']
            e.update(league,h,a,day,int(r['home_goals']),int(r['away_goals']))
            history[(league,h)]+=1;history[(league,a)]+=1
    return all_results

def validate_pairs(records):
    by_match=defaultdict(set)
    for r in records:
        match=(r['date'],r['league'],r['home'],r['away'])
        if r['model'] in by_match[match]:
            raise ValueError('Duplicate model/match record: '+str(match))
        by_match[match].add(r['model'])
        probabilities=(r['p1'],r['px'],r['p2'])
        if abs(sum(probabilities)-1)>1e-8 or not all(0<=p<=1 for p in probabilities):
            raise ValueError('Invalid model probabilities')
    if any(models!={'SIG E','SIG 4.0'} for models in by_match.values()):
        raise ValueError('Models evaluated on different fixture sets')
    return len(by_match)

def summarize_pairs(records):
    n=validate_pairs(records)
    result=[]
    for name in ('SIG E','SIG 4.0'):
        values=[r for r in records if r['model']==name]
        if not values:continue
        for league in ['ALLE']+sorted({r['league'] for r in values}):
            subset=values if league=='ALLE' else [r for r in values if r['league']==league]
            result.append({'model':name,'league':league,'matches':len(subset),
                           'brier':sum(r['brier'] for r in subset)/len(subset),
                           'logloss':sum(r['logloss'] for r in subset)/len(subset)})
    return result
