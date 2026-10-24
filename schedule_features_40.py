"""As-of-safe match-load features from verified cross-competition fixtures.

Fixtures are separate from the domestic training results. No fatigue adjustment
is applied until independently validated. Missing schedule coverage is explicit.
"""
import datetime as dt
from collections import defaultdict

TOP_FIVE=frozenset(('PL','PD','SA','BL1','FL1'))
COMPETITIONS=frozenset(('league','champions_league','europa_league',
                        'conference_league','domestic_cup','international','other'))
def day(value):
    return value if isinstance(value,dt.date) else dt.date.fromisoformat(str(value)[:10])

def schedule_features(schedule,as_of,league,home,away,fixture_date):
    """Only games known by as_of count; future scheduled matches need known_at."""
    target=day(fixture_date);knowledge=day(as_of)
    if knowledge>target:raise ValueError('Knowledge date cannot follow fixture date')
    indexed=defaultdict(list)
    for r in schedule:
        comp=r.get('competition_type')
        if comp not in COMPETITIONS:continue
        if not r.get('home') or not r.get('away') or not r.get('date'):continue
        known=r.get('known_at')
        if not known or day(known)>knowledge:continue
        event=day(r['date'])
        if event==target and r.get('league')==league and r.get('home')==home and r.get('away')==away:
            continue
        played=str(r.get('status','')).lower() in ('finished','completed')
        # A finished match cannot be used if its result was not yet known.
        if event<knowledge and not played:continue
        for team in (r['home'],r['away']):
            indexed[team].append((event,comp,played))
    def one(team):
        events=indexed[team]
        past=[e for e in events if e[0]<target and e[2] and e[0]<knowledge]
        future=[e for e in events if target<e[0]<=target+dt.timedelta(days=7)]
        recent=lambda n:sum(target-d<dt.timedelta(days=n+1) for d,_,_ in past)
        return {'rest_days':(target-max(d for d,_,_ in past)).days if past else None,
                'matches_last_7d':recent(7),'matches_last_14d':recent(14),
                'europe_last_7d':sum(target-d<=dt.timedelta(days=7) and c in ('champions_league','europa_league','conference_league') for d,c,_ in past),
                'matches_next_7d':len(future),'fixture_coverage':bool(events)}
    return {'home':one(home),'away':one(away)}
