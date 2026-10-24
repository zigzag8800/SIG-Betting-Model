"""SIG research-only cross-competition archive, separate from domestic training.

Uses verified football-data.org identifiers, never fuzzy team-name matching.
Does not download provider data or change production forecasts.
"""

RESEARCH_COMPETITIONS=frozenset(('CL','EL','UCL','EC','WC','QUFA','FAC','FLC','DFB','CDR'))

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
        if not str(mid).strip() or not str(hid).strip() or not str(aid).strip():
            continue
        score=(m.get('score') or {}).get('fullTime') or {}
        finished=str(m.get('status') or '').upper()=='FINISHED'
        home_goals=score.get('home') if finished else None
        away_goals=score.get('away') if finished else None
        if finished and (home_goals is None or away_goals is None):
            continue
        if finished:
            try:
                home_goals=int(home_goals);away_goals=int(away_goals)
                if home_goals<0 or away_goals<0:continue
            except (ValueError,TypeError):
                continue
        result.append({
            'match_id':str(mid),'competition':competition,
            'home_team_id':str(hid),'away_team_id':str(aid),
            'home':home.get('name') or '', 'away':away.get('name') or '',
            'kickoff_utc':kickoff,'date':str(kickoff)[:10],
            'status':m.get('status') or '',
            'home_goals':home_goals,'away_goals':away_goals,
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
        identity=('competition','home_team_id','away_team_id','kickoff_utc')
        if any(str(previous.get(f))!=str(row.get(f)) for f in identity):
            conflicts.append({'reason':'conflicting identity','key':key})
            continue
        # A finished match result may legitimately arrive after a scheduled
        # fixture. Never replace a known result with a blank score.
        if str(previous.get('status','')).upper()=='FINISHED' and str(row.get('status','')).upper()=='FINISHED':
            if previous.get('home_goals') is not None and row.get('home_goals') is not None and (previous.get('home_goals'),previous.get('away_goals'))!=(row.get('home_goals'),row.get('away_goals')):
                conflicts.append({'reason':'conflicting result','key':key})
                continue
        # Historical publication timestamps cannot be inferred by an update.
        # Empty fields and unknown historical timestamps must never erase
        # values already documented in the archive.
        updated={**previous,**{k:v for k,v in row.items() if v is not None and v!=''}}
        # Out-of-order cached fixture updates must not downgrade final results.
        if str(previous.get('status','')).upper()=='FINISHED' and str(row.get('status','')).upper()!='FINISHED':
            updated['status']=previous['status']
        index[key]=updated
    return list(index.values()),conflicts

def research_coverage(rows):
    return [{'competition':comp,'matches':sum(x.get('competition')==comp for x in rows),
             'finished':sum(x.get('competition')==comp and str(x.get('status','')).upper()=='FINISHED' for x in rows),
             'finished_with_score':sum(x.get('competition')==comp and str(x.get('status','')).upper()=='FINISHED' and isinstance(x.get('home_goals'),int) and not isinstance(x.get('home_goals'),bool) and isinstance(x.get('away_goals'),int) and not isinstance(x.get('away_goals'),bool) and x['home_goals']>=0 and x['away_goals']>=0 for x in rows),
             'stable_match_ids':sum(x.get('competition')==comp and bool(x.get('match_id')) for x in rows),
             'stable_team_ids':sum(x.get('competition')==comp and bool(x.get('home_team_id')) and bool(x.get('away_team_id')) for x in rows),
             'known_at_available':sum(x.get('competition')==comp and bool(x.get('known_at')) for x in rows)}
            for comp in sorted(RESEARCH_COMPETITIONS)]
