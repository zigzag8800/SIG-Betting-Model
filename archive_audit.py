"""Read-only coverage of persisted records. No HTTP, guessed IDs or timestamps."""
import datetime as dt
import base64
import csv
import io
import hashlib
import zipfile
from pathlib import PurePosixPath
from collections import defaultdict, Counter
from match_lifecycle import preview as lifecycle_preview

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
            home_goals=score.get('home'),away_goals=score.get('away'),stage=m.get('stage'),
            provider_updated_at=m.get('lastUpdated'),score_duration=(m.get('score') or {}).get('duration'),
            regular_time_home_goals=((m.get('score') or {}).get('regularTime') or {}).get('home'),
            regular_time_away_goals=((m.get('score') or {}).get('regularTime') or {}).get('away')))
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
        bad_time=0;date_mismatch=0;invalid_date=0
        for r in games:
            try:dt.date.fromisoformat(str(r.get('date') or '')[:10])
            except ValueError:invalid_date+=1
        for r in games:
            try:
                t=dt.datetime.fromisoformat(str(r.get('kickoff_utc') or '').replace('Z','+00:00'))
                if t.tzinfo is None or t.utcoffset()!=dt.timedelta(0):raise ValueError()
                if t.date().isoformat()!=str(r.get('date') or '')[:10]:date_mismatch+=1
            except (ValueError,TypeError):bad_time+=1
        dates=[str(r.get('date'))[:10] for r in games if r.get('date')]
        pairs={(r.get('home'),r.get('away')) for r in games if r.get('home') and r.get('away')}
        result.append(dict(stage_counts=dict(Counter(r.get('stage') or 'unknown' for r in games)),distinct_directed_pairs=len(pairs),scope=scope,competition=code,season=season,rows=len(games),
            finished=len(finished),valid_results=sum(valid_score(r) for r in finished),
            invalid_date=invalid_date,date_kickoff_mismatch=date_mismatch,
            distinct_teams=len({r.get(side) for r in games for side in ('home','away') if r.get(side)}),
            conflicting_natural_keys=sum(len({(str(r.get('home_goals')),str(r.get('away_goals'))) for r in v})>1 for v in keys.values()),
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
    by_identity=defaultdict(set)
    for existing_row in existing:
        identity=(existing_row.get('source'),str(existing_row.get('match_id') or ''))
        if all(identity):by_identity[identity].add(natural(existing_row))
    for row in incoming:
        key=natural(row);old=index.get(key,{})
        identity=(row.get('source'),str(row.get('match_id') or ''))
        if all(identity) and any(stored_key!=key for stored_key in by_identity[identity]):
            raise ValueError('Same source match ID on another date/team key; rescheduling requires review')
        if old.get('status')=='FINISHED' and row.get('status') and row['status']!='FINISHED':
            raise ValueError('A finished result cannot be downgraded by an import')
        for field in FIELDS:
            if field=='status':continue
            if old.get(field) and row.get(field) and str(old[field])!=str(row[field]):
                raise ValueError('Import has conflicting match metadata: '+field)
        if valid_score(old) and valid_score(row) and any(float(old[f])!=float(row[f]) for f in ('home_goals','away_goals')):
            raise ValueError('Import has conflicting final score')
        index[key]={**old,**{k:v for k,v in row.items() if v is not None and v!=''}}
        if all(identity):by_identity[identity].add(key)
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
    for digest,item in snapshot.get('files',[]):
        try:
            raw=base64.b64decode(item['content'],validate=True)
            entry=audit_csv(raw,item['name'],'postgres:source_csv')
            entry['stored_digest_matches']=hashlib.sha256(raw).hexdigest()==digest
        except (ValueError,UnicodeError,csv.Error) as exc:
            entry=dict(name=item.get('name'),error=type(exc).__name__)
        raw_files.append(dict(stored_sha256=digest,**entry))
    bundles=[audit_bundle(item) for _,item in snapshot.get('bundles',[])]
    historical_versions=[]
    for key,data in snapshot.get('old_workspaces',[]):
        historical_versions.append(dict(version=key,coverage=summarize(data.get('history',[])+data.get('fixtures',[]),'postgres:workspace_version'),
            research=summarize(data.get('research_competitions_40',[]),'postgres:workspace_version:research')))
    excluded=[dict(competition=r['league'],season=r['season'],match_id=r['match_id'],status=r['status'],date=r['date'],home=r['home'],away=r['away'])
              for r in cached if r.get('status') not in ('FINISHED','SCHEDULED','TIMED')]
    return dict(cache_lifecycle=lifecycle_preview(current.get('history',[])+current.get('fixtures',[]),cached),provider_bundles=bundles,raw_files=raw_files,historical_versions=historical_versions,cache_exclusions=excluded,generated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        scope='All sig_archive records inventoried in one read-only repeatable-read transaction; current workspace and every API cache audited. Every workspace version and archived source CSV audited separately; versions and sources must not be added as unique matches. Provider ZIP members are audited in memory within explicit size limits; member errors or skipped entries are recorded. Raw CSV row seasons remain unknown unless explicit.',
        inventory=snapshot['inventory'],versions=snapshot['versions'],coverage=summary,
        empty_research_competitions=sorted(set(('CL','EL','UCL','EC','WC','QUFA','FAC','FLC','DFB','CDR'))-{r.get('competition') for r in current.get('research_competitions_40',[])})),cached


DIVISIONS={'E0':'PL','E1':'ELC','SP1':'PD','I1':'SA','D1':'BL1','F1':'FL1'}

def audit_csv(raw,name,scope):
    if len(raw)>5*1024*1024:raise ValueError('CSV exceeds 5 MB audit limit')
    reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    if not {'Date','HomeTeam','AwayTeam','FTHG','FTAG'}.issubset(reader.fieldnames or []):
        raise ValueError('Missing required result columns')
    source_rows=list(reader)
    rows=[]
    for r in source_rows:
        date=''
        for fmt in ('%d/%m/%Y','%d/%m/%y'):
            try:date=dt.datetime.strptime(r.get('Date',''),fmt).date().isoformat();break
            except ValueError:pass
        division=r.get('Div') or PurePosixPath(name).stem.upper()
        rows.append(dict(league=DIVISIONS.get(division,division),date=date,
            home=r.get('HomeTeam'),away=r.get('AwayTeam'),home_goals=r.get('FTHG'),away_goals=r.get('FTAG'),source='football-data.co.uk'))
    invalid=[dict(row_number=i+2,date=r['date'],home=r['home'],away=r['away'],home_goals=r['home_goals'],away_goals=r['away_goals']) for i,r in enumerate(rows) if not valid_score(r)]
    ftr_conflicts=sum(valid_score(r) and original.get('FTR') not in (None,'',('H' if float(r['home_goals'])>float(r['away_goals']) else 'A' if float(r['home_goals'])<float(r['away_goals']) else 'D')) for r,original in zip(rows,source_rows))
    return dict(name=name,sha256=hashlib.sha256(raw).hexdigest(),coverage=summarize(rows,scope),invalid_result_rows=invalid[:100],invalid_result_count=len(invalid),result_code_conflicts=ftr_conflicts,
                status_unverified=True,notes='CSV scores do not establish FINISHED versus AWARDED; Time is not asserted to be UTC.')

def audit_bundle(item):
    """Audit every member without extracting or executing anything."""
    result=dict(name=item.get('name'),members=[],complete=False)
    try:
        raw=base64.b64decode(item['content'],validate=True)
        if len(raw)>20*1024*1024:raise ValueError('ZIP exceeds 20 MB audit limit')
        result['sha256']=hashlib.sha256(raw).hexdigest()
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries=archive.infolist()
            if len(entries)>100 or sum(i.file_size for i in entries)>100*1024*1024:
                raise ValueError('ZIP exceeds member count or 100 MB expansion limit')
            seen=set()
            for info in entries:
                member=dict(name=info.filename,bytes=info.file_size)
                path=PurePosixPath(info.filename)
                if info.filename in seen or path.is_absolute() or '..' in path.parts or '\\' in info.filename or info.flag_bits&1:
                    member['error']='unsafe, encrypted or duplicate member'
                elif info.is_dir():member['directory']=True
                elif path.suffix.lower()!='.csv':member['skipped']='non-CSV member'
                elif info.file_size>5*1024*1024:member['error']='member exceeds 5 MB audit limit'
                else:
                    try:member.update(audit_csv(archive.read(info),info.filename,'postgres:provider_bundle'))
                    except (ValueError,UnicodeError,csv.Error,zipfile.BadZipFile,RuntimeError,NotImplementedError) as exc:
                        member['error']=type(exc).__name__
                seen.add(info.filename);result['members'].append(member)
            result['complete']=all(not m.get('error') and not m.get('skipped') for m in result['members'])
    except (ValueError,KeyError,zipfile.BadZipFile,RuntimeError) as exc:
        result['error']=str(exc)
    return result
