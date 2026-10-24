"""SIG research-only cross-competition archive, separate from domestic training.

Uses verified football-data.org identifiers, never fuzzy team-name matching.
Does not download provider data or change production forecasts.
"""
from collections import defaultdict

RESEARCH_COMPETITIONS=frozenset(('CL','EL','UCL','EC','WC','QUFA'))

def convert_research_matches(matches, competition):
    """Normalize supported provider response fields without inventing known_at."""
    if competition not in RESEARCH_COMPETITIONS:
        raise ValueError('Turneringen er ikke godkendt til forskningsarkivet')
    result=[]
    for m in matches:
        home=m.get('homeTeam') or {}
        away=m.get('awayTeam') or {}
        mid=m.get('id')
        hid=home.get('id');aid=away.get('id')
        kickoff=m.get('utcDate')
        if mid is None or hid is None or aid is None or not kickoff:
            continue
        result.append({
            'match_id':str(mid),'competition':competition,
            'home_team_id':str(hid),'away_team_id':str(aid),
            'home':home.get('name') or '', 'away':away.get('name') or '',
            'kickoff_utc':kickoff,'date':str(kickoff)[:10],
            'status':m.get('status') or '',
            'source':'football-data.org',
            'known_at':None
        })
    return result

def merge_research_matches(existing,incoming):
    """Merge by source + match id, retaining independent competitions.

    Preserve the old row for conflicting identity records and report conflicts.
    """
    index={}
    conflicts=[]
    for row in list(existing)+list(incoming):
        key=(row.get('source'),str(row.get('match_id') or ''))
        if not all(key):
            conflicts.append({'reason':'missing identity','row':row})
            continue
        previous=index.get(key)
        if previous is None:
            index[key]=dict(row)
            continue
        identity=('competition','home_team_id','away_team_id')
        if any(str(previous.get(f))!=str(row.get(f)) for f in identity):
            conflicts.append({'reason':'conflicting identity','key':key})
            continue
        # Historical publication timestamps cannot be inferred by an update.
        updated={**previous,**{k:v for k,v in row.items() if v is not None}}
        index[key]=updated
    return list(index.values()),conflicts

def research_coverage(rows):
    return [{'competition':comp,'matches':sum(x.get('competition')==comp for x in rows),
             'stable_match_ids':sum(x.get('competition')==comp and bool(x.get('match_id')) for x in rows),
             'known_at_available':sum(x.get('competition')==comp and bool(x.get('known_at')) for x in rows)}
            for comp in sorted(RESEARCH_COMPETITIONS)]
