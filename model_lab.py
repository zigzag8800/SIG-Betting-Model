"""Isolated walk-forward model comparisons; production predictions remain unchanged."""
import datetime as dt
from collections import defaultdict
from itertools import groupby
from sig_model import Engine, date, clip

class ExperimentalEngine(Engine):
    def __init__(self, form_window=5, elo_effect=0.12, **kwargs):
        super().__init__(**kwargs)
        self.form_window=form_window
        self.elo_effect=elo_effect

    def form_profile(self, league, team, today, last_n=None):
        return super().form_profile(league, team, today, self.form_window if last_n is None else last_n)

    def expected_goals(self, league, home, away, today):
        # Preserve existing goal and venue model; vary Elo contribution explicitly.
        # Superclass includes 0.12*er. Apply difference to log-goal rates.
        import math
        lh,la,n=super().expected_goals(league,home,away,today)
        er=(self.elo[(league,home)]-self.elo[(league,away)])/400
        delta=(self.elo_effect-0.12)*er
        return clip(lh*math.exp(delta),0.25,3.7),clip(la*math.exp(-delta),0.20,3.5),n

VARIANTS={
    'A · Nuværende 3.6':dict(form_strength=0),
    'B · Stærkere Elo':dict(form_strength=0,elo_effect=0.20),
    'C · Form 5':dict(form_strength=0.16,form_window=5),
    'D · Form 10':dict(form_strength=0.16,form_window=10),
    'E · Form 10 + Elo':dict(form_strength=0.16,form_window=10,elo_effect=0.20),
    'F · Form 10 + kortere hukommelse':dict(form_strength=0.16,form_window=10,half_life=90),
}

def compare_variants(rows, cutoff, test_start):
    """Chronological predictions. Same-day matches withheld. Shared test fixtures."""
    engines={name:ExperimentalEngine(**options) for name,options in VARIANTS.items()}
    rows=sorted(rows,key=lambda r:(r['date'][:10],r['league'],r['home']))
    records=[]
    for daystr, batch in groupby(rows,key=lambda r:r['date'][:10]):
        day=date(daystr)
        if day>=cutoff: break
        matches=list(batch)
        for match in matches:
            lg,h,a=match['league'],match['home'],match['away']
            hg,ag=int(match['home_goals']),int(match['away_goals'])
            actual='1' if hg>ag else 'X' if hg==ag else '2'
            if day<test_start: continue
            # Require every variant to have sufficient prior matches.
            predictions={name:engine.predict(lg,h,a,day) for name,engine in engines.items()}
            if any(p['history_min']<5 for p in predictions.values()):
                continue
            for name,pred in predictions.items():
                p=pred['p']
                brier=sum((p[outcome]-int(outcome==actual))**2 for outcome in ('1','X','2'))/3
                import math
                records.append({'variant':name,'date':daystr,'league':lg,'home':h,'away':a,
                                'actual':actual,'p1':p['1'],'px':p['X'],'p2':p['2'],
                                'brier':brier,'logloss':-math.log(max(p[actual],1e-12))})
        for r in matches:
            for engine in engines.values():
                engine.update(r['league'],r['home'],r['away'],day,int(r['home_goals']),int(r['away_goals']))
    return records
