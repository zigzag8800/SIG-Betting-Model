"""Read-only, source-namespaced match change review. Never applies proposals."""
import datetime as dt
from collections import Counter, defaultdict

STATES=frozenset(('SCHEDULED','TIMED','IN_PLAY','PAUSED','EXTRA_TIME','PENALTY_SHOOTOUT','FINISHED','POSTPONED','SUSPENDED','CANCELLED','AWARDED'))
ADMIN=frozenset(('CANCELLED','AWARDED'))
IDENTITY=('home_team_id','away_team_id')


def key(row):
    source=str(row.get('source') or '').strip();mid=str(row.get('match_id') or '').strip()
    return (source,mid) if source and mid else None


def utc(value):
    try:
        timestamp=dt.datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return timestamp if timestamp.tzinfo is not None and timestamp.utcoffset()==dt.timedelta(0) else None
    except (ValueError,TypeError):return None


def score(row):
    values=[]
    for name in ('home_goals','away_goals'):
        value=row.get(name)
        if isinstance(value,bool):return None
        try:
            number=float(value)
            if number<0 or not number.is_integer() or number==float('inf'):return None
            values.append(int(number))
        except (ValueError,TypeError,OverflowError):return None
    return tuple(values)


def signature(row):
    # Availability/ingest timestamps do not define the match outcome.
    return tuple(str(row.get(f) or '') for f in ('source','match_id','home_team_id','away_team_id','league','competition','season','date','status','home','away'))+(str(utc(row.get('kickoff_utc')) or ''),score(row),)


def classify(previous,incoming):
    """Classify only; all proposals require a separate application workflow."""
    def decision(action,reason):
        return dict(action=action,reason=reason,source=incoming.get('source'),match_id=str(incoming.get('match_id') or ''),
                    previous_status=previous.get('status') if previous else None,incoming_status=incoming.get('status'),
                    previous_kickoff=previous.get('kickoff_utc') if previous else None,incoming_kickoff=incoming.get('kickoff_utc'),
                    previous_score=list(score(previous)) if previous and score(previous) is not None else None,
                    incoming_score=list(score(incoming)) if score(incoming) is not None else None,
                    applies_changes=False)
    if not key(incoming) or (previous is not None and key(previous)!=key(incoming)):
        return decision('identity_review','Missing or different source + match ID')
    if not all(str(incoming.get(f) or '').strip() for f in IDENTITY):
        return decision('identity_review','Missing stable team IDs')
    status=incoming.get('status')
    if status not in STATES:return decision('invalid_observation','Unknown match status')
    timestamp=utc(incoming.get('kickoff_utc'))
    if not timestamp or timestamp.date().isoformat()!=str(incoming.get('date') or '')[:10]:
        return decision('invalid_observation','Kickoff must be UTC and agree with match date')
    if status=='FINISHED' and score(incoming) is None:
        return decision('invalid_observation','FINISHED requires non-negative integer scores')
    if status=='FINISHED' and incoming.get('score_duration')!='REGULAR':
        return decision('score_scope_review','Full-time score may include extra time or penalties; do not use as 90-minute result')
    if previous is None:
        return decision('administrative_record' if status in ADMIN else 'new_record_review',
                        'Retain administrative status outside played training history' if status in ADMIN else 'New source ID; no automatic insert')
    if not all(str(previous.get(f) or '').strip() for f in IDENTITY):
        return decision('identity_review','Stored match lacks verified team IDs')
    for field in (*IDENTITY,'league','competition','season'):
        if previous.get(field) and incoming.get(field) and str(previous[field])!=str(incoming[field]):
            return decision('identity_review','Conflicting '+field)
    if signature(previous)==signature(incoming):return decision('unchanged','Same football state; idempotent replay')
    old_time=utc(previous.get('provider_updated_at'));new_time=utc(incoming.get('provider_updated_at'))
    if old_time and new_time and new_time<old_time:return decision('stale_observation','Provider version predates stored version')
    if old_time and new_time and new_time==old_time:return decision('version_conflict','Different content with identical provider timestamp')
    if previous.get('status')=='FINISHED':
        if status!='FINISHED':return decision('terminal_status_review','Never downgrade or erase a final result automatically')
        if score(previous)!=score(incoming):return decision('result_correction_review','Keep original result and review correction separately')
        return decision('finished_metadata_review','Historical date/name/kickoff change requires review')
    if status in ADMIN:return decision('administrative_review','Keep raw record; exclude from played training and active fixture candidates')
    if not old_time or not new_time:return decision('version_unknown_review','No proven order of provider versions; arrival order is insufficient')
    if status=='FINISHED':return decision('result_available_review','Newer final result; validate score scope before materializing')
    if previous.get('kickoff_utc')!=incoming.get('kickoff_utc'):
        return decision('reschedule_review','Same source ID with newer kickoff; replace active projection only after review, never add a second match')
    return decision('status_update_review','Newer status; POSTPONED/SUSPENDED stay outside active fixture candidates')


def preview(existing,incoming):
    """Do not choose an arbitrary winner among duplicate or competing versions."""
    old=defaultdict(list);new=defaultdict(list);issues=[]
    for row in existing:old[key(row)].append(row)
    for row in incoming:new[key(row)].append(row)
    actions=[]
    for identity,rows in sorted(new.items(),key=lambda item:str(item[0])):
        if identity is None:
            actions.extend(classify(None,r) for r in rows);continue
        # Repeated identical observations collapse; differing versions need review.
        signatures={signature(r)+(str(r.get('provider_updated_at') or ''),str(r.get('score_duration') or '')) for r in rows}
        if len(old[identity])>1 or len(signatures)>1:
            actions.append(dict(source=identity[0],match_id=identity[1],action='duplicate_identity_review',reason='Multiple stored rows or competing incoming versions; no winner selected',applies_changes=False));continue
        actions.append(classify(old[identity][0] if old[identity] else None,rows[0]))
    for identity,rows in old.items():
        if identity is None:issues.append(dict(issue='stored_missing_identity',rows=len(rows)))
        elif identity not in new:issues.append(dict(issue='not_in_cached_response',source=identity[0],match_id=identity[1],rows=len(rows)))
    return dict(summary=dict(Counter(a['action'] for a in actions)),input_existing=len(existing),input_observations=len(incoming),
                decisions=actions,coverage_issues=issues,applies_changes=False,
                scope='Read-only comparison of active workspace against already saved API cache. Absence is not deletion and lastUpdated is not known_at.')
