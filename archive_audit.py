"""Read-only coverage of persisted records. No HTTP, guessed IDs or timestamps."""
import datetime as dt
import base64
import csv
import io
from pathlib import PurePosixPath
from collections import defaultdict

FIELDS=('match_id','home_team_id','away_team_id','kickoff_utc','source','season','status','known_at')

def valid_goal(value):
    if isinstance(value,bool):return False
    try:return float(value)>=0 and float(value).is_integer() and float(value)<float('inf')
    except (ValueError,TypeError,OverflowError):return False

def valid_score(row):
    return valid_goal(row.get('home_goals')) and valid_goal(row.get('away_goals'))

def natural(row):
    return (str(row.get('league') or row.get('competition') or ''),str(row.get('date') or '')[:10],row.get('home'),row.get('away'))

def normalize_cached(matches,code,season):
    rows=[]
    for m in matches:
        h=m.get('homeTeam') or {};a=m.get('awayTeam') or {};score=(m.get('score') or {}).get('fullTime') or {}
        rows.append(dict(date=str(m.get('utcDate') or '')[:10],league=code,season=season,
            home=h.get('name'),away=a.get('name'),match_id=str(m.get('id') or ''),
            home_team_id=str(h.get('id') or ''),away_team_id=str(a.get('id') or ''),
            kickoff_utc=m.get('utcDate'),status=m.get('status'),source='football-data.org',
            home_goals=score.get('home'),away_goals=score.get('away')))
    return rows

def summarize(rows,scope):
    groups=defaultdict(list)
    for row in rows:groups[(row.get('league') or row.get('competition') or 'unknown',str(row.get('season') or 'unknown'))].append(row)
    result=[]
    for (code,season),games in sorted(groups.items()):
        ids=defaultdict(list);keys=defaultdict(list)
        for r in games:
            keys[natural(r)].append(r)
            if r.get('match_id'):ids[(r.get('source'),str(r['match_id']))].append(r)
        finished=[r for r in games if r.get('status')=='FINISHED' or (not r.get('status') and 'home_goals' in r)]
        bad_time=0
        for r in games:
            try:
                t=dt.datetime.fromisoformat(str(r.get('kickoff_utc') or '').replace('Z','+00:00'))
                if t.tzinfo is None or t.utcoffset()!=dt.timedelta(0):raise ValueError()
            except (ValueError,TypeError):bad_time+=1
        dates=[str(r.get('date'))[:10] for r in games if r.get('date')]
        result.append(dict(scope=scope,competition=code,season=season,rows=len(games),
            finished=len(finished),valid_results=sum(valid_score(r) for r in finished),
            missing_match_id=sum(not r.get('match_id') for r in games),
            missing_team_ids=sum(not r.get('home_team_id') or not r.get('away_team_id') for r in games),
            missing_or_invalid_kickoff=bad_time,missing_source=sum(not r.get('source') for r in games),
            missing_known_at=sum(not r.get('known_at') for r in games),
            duplicate_ids=sum(len(v)-1 for v in ids.values()),duplicate_natural_keys=sum(len(v)-1 for v in keys.values()),
            conflicting_ids=sum(len({(natural(r),str(r.get('home_goals')),str(r.get('away_goals'))) for r in v})>1 for v in ids.values()),
            first_date=min(dates) if dates else '',last_date=max(dates) if dates else ''))
    return result

def enrich_from_cache(rows,cached):
    """Fill missing metadata only after unique exact identity AND score agreement.

    Scores, names, dates and existing metadata never change. Ambiguity/conflict
    is counted instead of choosing a convenient candidate.
    """
    index=defaultdict(list)
    for r in cached:index[natural(r)].append(r)
    output=[];updated=conflicts=0
    for r in rows:
        candidates=index[natural(r)];new=dict(r)
        signatures={tuple(str(c.get(f) or '') for f in FIELDS if f!='known_at')+(str(c.get('home_goals')),str(c.get('away_goals'))) for c in candidates}
        if candidates and len(signatures)==1:
            c=candidates[0]
            clash=any(r.get(f) and c.get(f) and str(r[f])!=str(c[f]) for f in FIELDS)
            if 'home_goals' in r:clash=clash or not valid_score(r) or not valid_score(c) or any(float(r[f])!=float(c[f]) for f in ('home_goals','away_goals'))
            if clash:conflicts+=1
            else:
                for f in FIELDS:
                    if not new.get(f) and c.get(f):new[f]=c[f]
                if new!=r:updated+=1
        elif candidates:conflicts+=1
        output.append(new)
    return output,dict(updated=updated,conflicts=conflicts,unmatched=sum(not index[natural(r)] for r in rows))

def merge_metadata(existing,incoming):
    """Prevent sparse CSV/API updates from erasing documented identity metadata."""
    index={natural(r):dict(r) for r in existing}
    for row in incoming:
        key=natural(row);old=index.get(key,{})
        for field in FIELDS:
            if field=='status':continue
            if old.get(field) and row.get(field) and str(old[field])!=str(row[field]):
                raise ValueError('Import has conflicting match metadata: '+field)
        if valid_score(old) and valid_score(row) and any(float(old[f])!=float(row[f]) for f in ('home_goals','away_goals')):
            raise ValueError('Import has conflicting final score')
        index[key]={**old,**{k:v for k,v in row.items() if v is not None and v!=''}}
    return list(index.values())

def build_report(snapshot,session):
    summary=[];cached=[]
    for key,payload in snapshot['api']:
        parts=key.rsplit(':',2)
        if len(parts)!=3:continue
        _,code,season=parts
        rows=normalize_cached(payload,code,season);cached.extend(rows)
        summary.extend(summarize(rows,'postgres:api_cache'))
    current=snapshot['current'] or {}
    for label,data in [('session',session),('postgres:workspace/current',current)]:
        summary.extend(summarize(data.get('history',[])+data.get('fixtures',[]),label))
        summary.extend(summarize(data.get('research_competitions_40',[]),label+':research'))
    raw_files=[]
    mapping={'E0':'PL','E1':'ELC','SP1':'PD','I1':'SA','D1':'BL1','F1':'FL1'}
    for digest,item in snapshot.get('files',[]):
        raw=base64.b64decode(item['content']).decode('utf-8-sig')
        source_rows=list(csv.DictReader(io.StringIO(raw)))
        rows=[]
        for r in source_rows:
            try:date=dt.datetime.strptime(r.get('Date',''),'%d/%m/%Y').date().isoformat()
            except ValueError:
                try:date=dt.datetime.strptime(r.get('Date',''),'%d/%m/%y').date().isoformat()
                except ValueError:date=''
            rows.append(dict(league=mapping.get(r.get('Div') or PurePosixPath(item['name']).stem.upper(),'unknown'),date=date,
                home=r.get('HomeTeam'),away=r.get('AwayTeam'),home_goals=r.get('FTHG'),away_goals=r.get('FTAG'),source='football-data.co.uk'))
        raw_files.append(dict(name=item['name'],sha256=digest,coverage=summarize(rows,'postgres:source_csv')))
    historical_versions=[]
    for key,data in snapshot.get('old_workspaces',[]):
        historical_versions.append(dict(version=key,coverage=summarize(data.get('history',[])+data.get('fixtures',[]),'postgres:workspace_version'),
            research=summarize(data.get('research_competitions_40',[]),'postgres:workspace_version:research')))
    excluded=[dict(competition=r['league'],season=r['season'],match_id=r['match_id'],status=r['status'],date=r['date'],home=r['home'],away=r['away'])
              for r in cached if r.get('status') not in ('FINISHED','SCHEDULED','TIMED')]
    return dict(raw_files=raw_files,historical_versions=historical_versions,cache_exclusions=excluded,generated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        scope='All sig_archive records inventoried in one read-only repeatable-read transaction; current workspace and every API cache audited. Every workspace version and archived source CSV audited separately; versions and sources must not be added as unique matches. The provider ZIP is inventoried but its unselected files are not expanded. Raw CSV seasons remain unknown unless explicit.',
        inventory=snapshot['inventory'],versions=snapshot['versions'],coverage=summary,
        empty_research_competitions=sorted(set(('CL','EL','UCL','EC','WC','QUFA','FAC','FLC','DFB','CDR'))-{r.get('competition') for r in current.get('research_competitions_40',[])})),cached
