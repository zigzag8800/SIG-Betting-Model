"""SIG 4.0 data contracts and coverage audit; independent of prediction engines.

No name-based joins. Historical memberships must be dated and explicit.
"""
import datetime as dt
from collections import Counter,defaultdict
from schedule_features_40 import TOP_FIVE

def day(value):
    return dt.date.fromisoformat(str(value)[:10])

def coverage_report(history,fixtures,schedule=None,players=None,appearances=None,memberships=None):
    schedule=schedule or [];players=players or [];appearances=appearances or [];memberships=memberships or []
    report=[]
    for league in sorted(TOP_FIVE):
        subset=[x for x in history if x.get('league')==league]
        future=[x for x in fixtures if x.get('league')==league]
        keys=[(x.get('date'),x.get('home'),x.get('away')) for x in subset]
        valid=sum(bool(x.get('date') and x.get('home') and x.get('away') and
                       x.get('home_goals') is not None and x.get('away_goals') is not None) for x in subset)
        report.append({'Liga':league,'Afsluttede kampe':len(subset),'Kommende kampe':len(future),
                       'Gyldige resultatrækker':valid,'Dublerede afsluttede kampe':len(keys)-len(set(keys)),
                       'Afsluttede kampe med kamp-ID':sum(bool(x.get('match_id')) for x in subset),
                       'Afsluttede kampe med kickoff UTC':sum(bool(x.get('kickoff_utc')) for x in subset),
                       'Tværturneringskampe i skema':sum(x.get('league')==league for x in schedule),
                       'Spillerposter i alt':len(players),
                       'Spillerkampe i alt':len(appearances),
                       'Historiske klubtilhørsforhold':len(memberships)})
    return report

def coverage_risks(history,fixtures):
    """A diagnostic, not a claim of coverage from a source provider."""
    result=[]
    for league in sorted(TOP_FIVE):
        rows=[r for r in history if r.get('league')==league]
        match_ids=[str(r['match_id']) for r in rows if r.get('match_id')]
        bad_score=0
        for r in rows:
            try:
                h,a=int(r['home_goals']),int(r['away_goals'])
                if h<0 or a<0:bad_score+=1
            except (ValueError,KeyError,TypeError):
                bad_score+=1
        result.append({'Liga':league,'Resultater':len(rows),
                       'Ugyldige målresultater':bad_score,
                       'Dublerede kamp-ID':len(match_ids)-len(set(match_ids)),
                       'Mangler kamp-ID':len(rows)-len(match_ids),
                       'Mangler kickoff UTC':sum(not r.get('kickoff_utc') for r in rows),
                       'Mangler datakilde':sum(not r.get('source') for r in rows),
                       'Mangler tilgængelighedstid':sum(not r.get('known_at') for r in rows)})
    return result

def validate_identity_data(players,memberships,appearances):
    """Require stable IDs; reject overlapping historical club memberships."""
    pids=[x['player_id'] for x in players]
    if len(pids)!=len(set(pids)):raise ValueError('Dubleret player_id')
    known=set(pids)
    timeline=defaultdict(list)
    for item in memberships:
        pid=item['player_id']
        if pid not in known:raise ValueError('Ukendt spiller i klubhistorik: '+str(pid))
        if not item.get('club_id'):raise ValueError('Mangler club_id')
        start=day(item['from_date'])
        finish=day(item['to_date']) if item.get('to_date') else dt.date.max
        if finish<=start:raise ValueError('Ugyldigt klubinterval')
        timeline[pid].append((start,finish,item['club_id']))
    for pid, intervals in timeline.items():
        intervals.sort()
        for prev,cur in zip(intervals,intervals[1:]):
            if cur[0]<prev[1] and cur[2]!=prev[2]:
                raise ValueError('Overlappende klubtilhørsforhold: '+str(pid))
    seen_appearances=set()
    for appearance in appearances:
        pid=appearance['player_id']
        if pid not in known:raise ValueError('Ukendt spiller i spillerkamp')
        match_id=appearance.get('match_id')
        if not match_id:raise ValueError('Mangler match_id')
        key=(pid,match_id)
        if key in seen_appearances:raise ValueError('Dubleret spillerkamp: '+str(key))
        seen_appearances.add(key)
        if not appearance.get('date') or not appearance.get('known_at'):
            raise ValueError('Spillerkamp mangler dato eller kendt-tidspunkt')
        played=day(appearance['date']);known_at=day(appearance['known_at'])
        if known_at<played:raise ValueError('Spilleres spilleminutter kan ikke være kendt før kampdatoen')
        minute=int(appearance['minutes'])
        if minute<0 or minute>150:raise ValueError('Ugyldigt antal minutter')
    return True

def player_load(appearances,memberships,player_id,club_id,as_of,window_days=14):
    """Only appearances known before as_of and with matching club membership count."""
    cutoff=day(as_of);floor=cutoff-dt.timedelta(days=window_days)
    eligible=any(x['player_id']==player_id and x['club_id']==club_id and
                 day(x['from_date'])<=cutoff and (not x.get('to_date') or cutoff<day(x['to_date']))
                 for x in memberships)
    if not eligible:return {'eligible':False,'minutes':None,'international_minutes':None,'games':None}
    relevant=[r for r in appearances if r['player_id']==player_id and
              floor<=day(r['date'])<cutoff and r.get('known_at') and day(r['known_at'])<=cutoff]
    return {'eligible':True,'minutes':sum(int(r['minutes']) for r in relevant),
            'international_minutes':sum(int(r['minutes']) for r in relevant if r.get('competition_type')=='international'),
            'games':len(relevant)}
