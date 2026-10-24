"""SIG 4.0 research engine: opponent-adjusted, time-decayed attack and defence.

Pure Python; isolated from production Engine. Parameters are estimated only
from completed fixtures supplied to fit(), never from evaluation fixtures.
"""
import datetime as dt
import math
from collections import defaultdict
from sig_model import pois, clip

def parse_day(x):
    return x if isinstance(x,dt.date) else dt.date.fromisoformat(str(x)[:10])

class AttackDefence40:
    def __init__(self,half_life=180,prior_games=8,iterations=30,home_prior_games=300):
        self.half_life=half_life
        self.prior_games=prior_games
        self.iterations=iterations
        self.home_prior_games=home_prior_games
        self.teams={}
        self.leagues={}
        self.cutoff=None

    def fit(self,rows,as_of):
        cutoff=parse_day(as_of)
        clean=[]
        for r in rows:
            day=parse_day(r['date'])
            if day>=cutoff: continue
            hg,ag=int(r['home_goals']),int(r['away_goals'])
            if hg<0 or ag<0: continue
            clean.append((r['league'],r['home'],r['away'],hg,ag,day))
        self.cutoff=cutoff
        self.teams={}
        self.leagues={}
        league_rows=defaultdict(list)
        for r in clean: league_rows[r[0]].append(r)
        for league,matches in league_rows.items():
            sums=defaultdict(float)
            team_weights=defaultdict(float)
            for _,home,away,hg,ag,day in matches:
                w=math.exp(-math.log(2)*(cutoff-day).days/self.half_life)
                sums['home']+=w*hg;sums['away']+=w*ag;sums['weight']+=w
                team_weights[home]+=w;team_weights[away]+=w
            avg_home=(sums['home']+self.prior_games*1.4)/(sums['weight']+self.prior_games)
            avg_away=(sums['away']+self.prior_games*1.1)/(sums['weight']+self.prior_games)
            home_edge=clip(math.log(avg_home/avg_away),-.4,.7)
            # The home effect is applied once through separate venue baselines.
            attack={t:1.0 for t in team_weights}
            defence={t:1.0 for t in team_weights}
            for _ in range(self.iterations):
                next_attack={};next_defence={}
                for team in team_weights:
                    scored=conceded=expected_scored=expected_conceded=0.0
                    for _,home,away,hg,ag,day in matches:
                        if team!=home and team!=away: continue
                        w=math.exp(-math.log(2)*(cutoff-day).days/self.half_life)
                        if team==home:
                            scored+=w*hg;conceded+=w*ag
                            expected_scored+=w*avg_home*defence[away]
                            expected_conceded+=w*avg_away*attack[away]
                        else:
                            scored+=w*ag;conceded+=w*hg
                            expected_scored+=w*avg_away*defence[home]
                            expected_conceded+=w*avg_home*attack[home]
                    next_attack[team]=clip((scored+self.prior_games)/(expected_scored+self.prior_games),.4,2.5)
                    next_defence[team]=clip((conceded+self.prior_games)/(expected_conceded+self.prior_games),.4,2.5)
                # Identifiability: normalize weighted attack and defence around one.
                for current in (next_attack,next_defence):
                    norm=sum(current[t]*team_weights[t] for t in current)/sum(team_weights.values())
                    for team in current: current[team]=clip(current[team]/norm,.4,2.5)
                attack,defence=next_attack,next_defence
            for t in team_weights:self.teams[(league,t)]=(attack[t],defence[t],team_weights[t])
            self.leagues[league]=(avg_home,avg_away,home_edge,len(matches))
        return self

    def expected_goals(self,league,home,away):
        if league not in self.leagues: return (1.4,1.1)
        base_home,base_away,_,_=self.leagues[league]
        ah,dh,_=self.teams.get((league,home),(1,1,0))
        aa,da,_=self.teams.get((league,away),(1,1,0))
        return clip(base_home*ah*da,.15,5),clip(base_away*aa*dh,.15,5)

    def predict(self,league,home,away,rho=-.08):
        lh,la=self.expected_goals(league,home,away)
        p={'1':0.0,'X':0.0,'2':0.0};total=0.0
        for i in range(12):
            for j in range(12):
                x=pois(lh,i)*pois(la,j)
                if i==0 and j==0:x*=1-lh*la*rho
                elif i==0 and j==1:x*=1+lh*rho
                elif i==1 and j==0:x*=1+la*rho
                elif i==1 and j==1:x*=1-rho
                x=max(0,x);total+=x
                p['1' if i>j else 'X' if i==j else '2']+=x
        return {'p':{k:v/total for k,v in p.items()},'home_xg':lh,'away_xg':la}

def backtest_40(rows,train_end,test_end,step_days=30):
    """Rolling-origin evaluations: refit before each time block, score later matches."""
    start,end=parse_day(train_end),parse_day(test_end)
    if start>=end:raise ValueError('First test date must precede test end')
    ordered=sorted(rows,key=lambda r:(r['date'][:10],r['league'],r['home'],r['away']))
    output=[]
    boundary=start
    while boundary<end:
        next_date=min(end,boundary+dt.timedelta(days=step_days))
        engine=AttackDefence40().fit(ordered,boundary)
        for r in ordered:
            day=parse_day(r['date'])
            if not boundary<=day<next_date:continue
            if r['league'] not in engine.leagues:continue
            actual='1' if int(r['home_goals'])>int(r['away_goals']) else 'X' if int(r['home_goals'])==int(r['away_goals']) else '2'
            pred=engine.predict(r['league'],r['home'],r['away'])['p']
            score=sum((pred[k]-(k==actual))**2 for k in ('1','X','2'))/3
            output.append({'date':day.isoformat(),'league':r['league'],'home':r['home'],'away':r['away'],
                           'brier':score,'logloss':-math.log(max(1e-12,pred[actual])),
                           'p1':pred['1'],'px':pred['X'],'p2':pred['2']})
        boundary=next_date
    return output
