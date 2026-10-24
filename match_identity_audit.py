"""Provider-neutral, non-destructive match data quality gate.

Only audits; never adds guessed IDs or past availability timestamps.
"""
import datetime as dt
from archive_audit import valid_score
from collections import defaultdict

TOP_FIVE=frozenset(('PL','PD','SA','BL1','FL1'))

def audit_match_identity(rows):
    result=[]
    for league in sorted(TOP_FIVE):
        games=[r for r in rows if r.get('league')==league]
        ids=defaultdict(list); natural=defaultdict(list)
        invalid=missing_id=missing_teams=missing_kickoff=0
        inconsistent_date=conflicting_id=0
        for r in games:
            mid=str(r.get('match_id') or '').strip()
            if mid: ids[(str(r.get('source') or ''),mid)].append(r)
            else:missing_id+=1
            natural[(str(r.get('date') or '')[:10],str(r.get('home') or ''),str(r.get('away') or ''))].append(r)
            if not r.get('home_team_id') or not r.get('away_team_id'):missing_teams+=1
            timestamp=r.get('kickoff_utc') or ''
            try:
                parsed=dt.datetime.fromisoformat(str(timestamp).replace('Z','+00:00'))
                if parsed.tzinfo is None or parsed.utcoffset()!=dt.timedelta(0):raise ValueError('not UTC')
                if parsed.date().isoformat()!=str(r.get('date') or '')[:10]:inconsistent_date+=1
            except (ValueError,TypeError,OverflowError):missing_kickoff+=1
            if not valid_score(r):invalid+=1
        # The same source match ID must not describe different teams, scores or dates.
        for same_id in ids.values():
            signatures={(str(x.get('date')),str(x.get('home_team_id') or x.get('home')),
                         str(x.get('away_team_id') or x.get('away')),
                         str(x.get('home_goals')),str(x.get('away_goals'))) for x in same_id}
            if len(signatures)>1:conflicting_id+=1
        result.append({'Liga':league,'Kampe':len(games),'Mangler kamp-ID':missing_id,
                       'Mangler hold-ID':missing_teams,'Ugyldigt/manglende UTC-kickoff':missing_kickoff,
                       'Ugyldigt resultat':invalid,
                       'Dato afviger fra UTC-kickoff':inconsistent_date,
                       'Modstridende kilde-kamp-ID':conflicting_id,
                       'Dublerede kilde-kamp-ID':sum(len(v)-1 for v in ids.values()),
                       'Mulige dubletter på dato/hold':sum(len(v)-1 for v in natural.values())})
    return result
