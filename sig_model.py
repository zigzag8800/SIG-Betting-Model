#!/usr/bin/env python3
"""SIG Model 3.0: reproducible, dependency-free football probability engine.
CSV historical matches, Elo + exponentially-weighted goal rates, Dixon-Coles,
chronological backtest, odds comparison and conservative value screen.
No bookmaker scraping, no invented odds, no automatic wagering.
"""
import argparse, csv, datetime as dt, math, pathlib, statistics
from collections import defaultdict
from itertools import groupby

LEAGUES={'PL':'Premier League','ELC':'Championship','PD':'La Liga','SA':'Serie A','BL1':'Bundesliga','FL1':'Ligue 1','DK1':'Superliga'}
MARKETS=['1','X','2','1X','X2','12','O1.5','O2.5','O3.5','U2.5','U3.5','U4.5','BTTS_Y','BTTS_N','H_O0.5','H_O1.5','A_O0.5','A_O1.5']

def read_csv(path, fields):
    with open(path, newline='', encoding='utf-8-sig') as f:
        rows=list(csv.DictReader(f))
    if rows and not set(fields).issubset(rows[0]): raise ValueError(f'{path}: requires columns {fields}')
    return rows

def date(s): return dt.date.fromisoformat(s[:10])
def pois(lam, n): return math.exp(-lam)*lam**n/math.factorial(n)
def clip(x,lo,hi): return max(lo,min(hi,x))

class Engine:
    def __init__(self, half_life=180, home_adv=0.16, elo_k=20, form_strength=0.0, manager_changes=None):
        self.games=defaultdict(list); self.elo=defaultdict(lambda:1500.0)
        self.half_life=half_life; self.home_adv=home_adv; self.elo_k=elo_k
        self.form_strength=clip(float(form_strength),0.0,0.25)
        self.manager_changes={}
        for row in (manager_changes or []):
            key=(row["league"],row["team"])
            d=date(row["start_date"])
            self.manager_changes.setdefault(key,[]).append(d)
        for changes in self.manager_changes.values(): changes.sort()
    def _key(self, league, team): return (league,team)
    def _weighted(self, league, team, today, at_home):
        games=self.games[self._key(league,team)]
        weights=[]; gf=[]; ga=[]
        for g in games:
            age=(today-g['date']).days
            if age<=0: continue
            # Home/away matching gets more weight, but does not discard opposite venue.
            w=math.exp(-math.log(2)*age/self.half_life)*(1.0 if g['home']==at_home else 0.55)
            weights.append(w); gf.append(g['gf']*w); ga.append(g['ga']*w)
        if not weights: return 1.35,1.35,0
        return sum(gf)/sum(weights),sum(ga)/sum(weights),len(weights)
    def form_profile(self, league, team, today, last_n=5):
        """Opponent-adjusted goal difference in last N prior matches.

        This is a conservative proxy from final scores, NOT measured xG or tactics.
        Elo opponent strength is captured before each historical match is played.
        """
        previous=[g for g in self.games[self._key(league,team)] if g['date'] < today]
        changes=[d for d in self.manager_changes.get((league,team),[]) if d <= today]
        if changes:
            previous=[g for g in previous if g['date'] >= changes[-1]]
        recent=sorted(previous,key=lambda g:g['date'],reverse=True)[:last_n]
        if not recent:
            return {'games':0,'form':0.0,'goal_diff':0.0,'manager_reset':bool(changes)}
        # Expected goal difference proxy: opponent Elo advantage / 500.
        # Keep weighting mild to avoid overreacting to a handful of results.
        values=[clip(g['gf']-g['ga']-(g.get('elo_for',1500)-g.get('elo_against',1500))/500,-4,4) for g in recent]
        avg=sum(values)/len(values)
        reliability=len(values)/(len(values)+7)
        return {'games':len(recent),'form':clip(avg*reliability,-1.0,1.0),
                'goal_diff':sum(g['gf']-g['ga'] for g in recent)/len(recent),
                'manager_reset':bool(changes)}

    def expected_goals(self,league,home,away,today):
        hgf,hga,nh=self._weighted(league,home,today,True)
        agf,aga,na=self._weighted(league,away,today,False)
        # shrink early-season estimates towards neutral baseline
        sh=nh/(nh+10); sa=na/(na+10)
        hgf=sh*hgf+(1-sh)*1.48; hga=sh*hga+(1-sh)*1.20
        agf=sa*agf+(1-sa)*1.22; aga=sa*aga+(1-sa)*1.48
        er=(self.elo[self._key(league,home)]-self.elo[self._key(league,away)])/400
        # modest Elo adjustment; avoids double-counting results too strongly
        lh=clip(math.sqrt(max(0.05,hgf*aga))*math.exp(self.home_adv/2+0.12*er),0.25,3.7)
        la=clip(math.sqrt(max(0.05,agf*hga))*math.exp(-self.home_adv/2-0.12*er),0.20,3.5)
        if self.form_strength:
            fh=self.form_profile(league,home,today)
            fa=self.form_profile(league,away,today)
            # No arbitrary unbounded probability shocks: capped, symmetric log-goal shift.
            change=clip(self.form_strength*(fh['form']-fa['form'])/2,-0.20,0.20)
            lh=clip(lh*math.exp(change),0.25,3.7)
            la=clip(la*math.exp(-change),0.20,3.5)
        return lh,la,min(nh,na)
    def predict(self,league,home,away,today,rho=-0.08):
        lh,la,n=self.expected_goals(league,home,away,today)
        probs=defaultdict(float); total=0.0
        for i in range(12):
            for j in range(12):
                p=pois(lh,i)*pois(la,j)
                if i==0 and j==0: p*=1-lh*la*rho
                elif i==0 and j==1: p*=1+lh*rho
                elif i==1 and j==0: p*=1+la*rho
                elif i==1 and j==1: p*=1-rho
                p=max(0,p); total+=p
                if i>j: probs['1']+=p
                elif i==j: probs['X']+=p
                else: probs['2']+=p
                for k in (1.5,2.5,3.5):
                    if i+j>k: probs[f'O{k}']+=p
                for k in (2.5,3.5,4.5):
                    if i+j<k: probs[f'U{k}']+=p
                if i>0 and j>0: probs['BTTS_Y']+=p
                else: probs['BTTS_N']+=p
                if i>0: probs['H_O0.5']+=p
                if i>1: probs['H_O1.5']+=p
                if j>0: probs['A_O0.5']+=p
                if j>1: probs['A_O1.5']+=p
        probs={k:v/total for k,v in probs.items()}
        probs['1X']=probs['1']+probs['X']; probs['X2']=probs['X']+probs['2']; probs['12']=probs['1']+probs['2']
        return {'home_xg':lh,'away_xg':la,'history_min':n,'p':probs}
    def update(self,league,home,away,today,hg,ag):
        eh=self.elo[self._key(league,home)]; ea=self.elo[self._key(league,away)]
        expectation=1/(1+10**(-(eh-ea+75)/400))
        actual=1 if hg>ag else 0.5 if hg==ag else 0
        delta=self.elo_k*(actual-expectation)
        self.elo[self._key(league,home)]+=delta
        self.elo[self._key(league,away)]-=delta
        self.games[self._key(league,home)].append({'date':today,'home':True,'gf':hg,'ga':ag,'elo_for':eh,'elo_against':ea})
        self.games[self._key(league,away)].append({'date':today,'home':False,'gf':ag,'ga':hg,'elo_for':ea,'elo_against':eh})

def load_history(engine, rows, cutoff=None, backtest=False):
    """Walk chronologically, withholding *all* same-date results until predictions finish.

    Matches on the same UTC date have no guaranteed kickoff ordering in imported
    CSV data. A day-level block avoids accidental same-day information leakage.
    Baseline: smoothed league-wide W/D/L prior from strictly earlier dates.
    """
    records = []
    league_counts = defaultdict(lambda: {'1': 0, 'X': 0, '2': 0})
    rows = sorted(rows, key=lambda r: (r['date'][:10], r['league'], r['home']))
    for day_str, grouped in groupby(rows, key=lambda r: r['date'][:10]):
        day = date(day_str)
        if cutoff and day >= cutoff:
            break
        matches = list(grouped)
        if backtest:
            for r in matches:
                lg, h, a = r['league'], r['home'], r['away']
                hg, ag = int(r['home_goals']), int(r['away_goals'])
                prediction = engine.predict(lg, h, a, day)
                if prediction['history_min'] < 5:
                    continue
                actual = '1' if hg > ag else 'X' if hg == ag else '2'
                # Laplace smoothing; no result from the current day is included.
                counts = league_counts[lg]
                n = sum(counts.values())
                baseline = {o: (counts[o] + 1) / (n + 3) for o in ('1', 'X', '2')}
                model = prediction['p']
                brier = lambda p: sum((p[o] - int(o == actual)) ** 2 for o in ('1', 'X', '2')) / 3
                records.append({
                    'date': day.isoformat(), 'league': lg, 'home': h, 'away': a,
                    'actual': actual, 'p1': model['1'], 'px': model['X'], 'p2': model['2'],
                    'brier': brier(model), 'logloss': -math.log(max(1e-9, model[actual])),
                    'baseline_p1': baseline['1'], 'baseline_px': baseline['X'],
                    'baseline_p2': baseline['2'], 'baseline_brier': brier(baseline),
                    'baseline_logloss': -math.log(max(1e-9, baseline[actual])),
                })
        # Only after every game on this date has been predicted, learn results.
        for r in matches:
            lg, h, a = r['league'], r['home'], r['away']
            hg, ag = int(r['home_goals']), int(r['away_goals'])
            engine.update(lg, h, a, day, hg, ag)
            outcome = '1' if hg > ag else 'X' if hg == ag else '2'
            league_counts[lg][outcome] += 1
    return records

def value_rows(engine,fixtures,odds,asof,edge_min=.04,margin=.025,until=None,markets=None):
    odds_index=defaultdict(list)
    for o in odds:
        if not o.get('odds'): continue
        try: price=float(o['odds'])
        except ValueError: continue
        if price<=1: continue
        key=(o['date'],o['league'],o['home'],o['away'],o['market'])
        odds_index[key].append((price,o.get('bookmaker','unknown'),o.get('captured_at','')))
    out=[]
    for f in fixtures:
        day=date(f['date']); lg=f['league']; h=f['home']; a=f['away']
        if day<asof or (until is not None and day>until): continue
        pred=engine.predict(lg,h,a,asof)
        for market,p in pred['p'].items():
            if markets is not None and market not in markets: continue
            # Confidence floor is deliberately conservative and NOT empirically calibrated.
            # It is a heuristic until proper uncertainty calibration is completed.
            uncertainty=clip(0.09/math.sqrt(max(1,pred['history_min'])/10),.035,.13)
            conservative=max(.01,p-uncertainty)
            fair=1/p; min_odds=1/conservative*(1+margin)
            prices=odds_index.get((f['date'],lg,h,a,market),[])
            best=max(prices,default=(None,'',''),key=lambda x:x[0] if x[0] else -1)
            offered=best[0]
            ev=p*offered-1 if offered else None
            # No 'recommended' status without verified odds and sufficient history.
            status='VALUE_TO_REVIEW' if offered and offered>=min_odds and ev>=edge_min and pred['history_min']>=12 else 'NO_PRICE' if not offered else 'INSUFFICIENT_HISTORY' if pred['history_min']<12 else 'BELOW_THRESHOLD'
            out.append({'date':f['date'],'league':lg,'home':h,'away':a,'market':market,'model_p':round(p,4),'conservative_p':round(conservative,4),'fair_odds':round(fair,3),'min_odds':round(min_odds,3),'best_odds':offered or '', 'bookmaker':best[1],'odds_captured_at':best[2],'ev':round(ev,4) if ev is not None else '', 'history_min':pred['history_min'],'expected_home_goals':round(pred['home_xg'],3),'expected_away_goals':round(pred['away_xg'],3),'status':status})
    # candidate ranking does not imply statistically proven edge
    out.sort(key=lambda r:(r['status']!='VALUE_TO_REVIEW',-(r['ev'] if isinstance(r['ev'],float) else -99),-r['model_p']))
    return out

def write_csv(path,rows,fields=None):
    fields=fields or (list(rows[0]) if rows else [])
    with open(path,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def main():
    ap=argparse.ArgumentParser(description='SIG Betting Model 3.0')
    ap.add_argument('--history',required=True);ap.add_argument('--fixtures');ap.add_argument('--odds');ap.add_argument('--asof',required=True,help='YYYY-MM-DD; use only information available before this date')
    ap.add_argument('--output',default='output');ap.add_argument('--backtest',action='store_true')
    args=ap.parse_args(); asof=date(args.asof); pathlib.Path(args.output).mkdir(parents=True,exist_ok=True)
    history=read_csv(args.history,['date','league','home','away','home_goals','away_goals'])
    eng=Engine(); back=load_history(eng,history,asof,backtest=args.backtest)
    if args.backtest:
        write_csv(pathlib.Path(args.output)/'backtest.csv',back,['date','league','home','away','actual','p1','px','p2','brier','logloss','baseline_p1','baseline_px','baseline_p2','baseline_brier','baseline_logloss'])
        if back: print(f'Chronological backtest: {len(back)} games | mean Brier={statistics.mean(r["brier"] for r in back):.4f} | mean logloss={statistics.mean(r["logloss"] for r in back):.4f}')
        else: print('No eligible historical games for backtest')
    if args.fixtures:
        fixtures=read_csv(args.fixtures,['date','league','home','away'])
        odds=read_csv(args.odds,['date','league','home','away','market','odds']) if args.odds else []
        rows=value_rows(eng,fixtures,odds,asof)
        write_csv(pathlib.Path(args.output)/'candidates.csv',rows,['date','league','home','away','market','model_p','conservative_p','fair_odds','min_odds','best_odds','bookmaker','odds_captured_at','ev','history_min','expected_home_goals','expected_away_goals','status'])
        print(f'{len(rows)} candidate markets | {sum(r["status"]=="VALUE_TO_REVIEW" for r in rows)} pass initial screen | output: {args.output}/candidates.csv')
if __name__=='__main__': main()
