"""Explicit, reversible correction from an archived provider regularTime field."""
import copy
import datetime as dt
from persistent_store import StorageError, content_key
from match_lifecycle import key, score, utc

INVALIDATED=('backtest_signature','lab_signature')

def prepare_correction(snapshot,observations,source,match_id,corrected_at=None):
    identity=(source,str(match_id))
    history=snapshot.get('history',[])
    positions=[i for i,r in enumerate(history) if key(r)==identity]
    incoming=[r for r in observations if key(r)==identity]
    if len(positions)!=1 or len(incoming)!=1:raise ValueError('Correction requires one stored row and one archived observation')
    old=history[positions[0]];raw=incoming[0]
    for field in ('home_team_id','away_team_id','league','season','date','home','away'):
        if not old.get(field) or str(old[field])!=str(raw.get(field) or ''):raise ValueError('Correction identity mismatch: '+field)
    if not utc(raw.get('kickoff_utc')) or utc(old.get('kickoff_utc'))!=utc(raw.get('kickoff_utc')):
        raise ValueError('Correction kickoff mismatch')
    if old.get('status')!='FINISHED' or raw.get('status')!='FINISHED':raise ValueError('Correction requires FINISHED')
    if raw.get('score_duration') not in ('EXTRA_TIME','PENALTY_SHOOTOUT'):raise ValueError('Explicit extra-time/penalty evidence required')
    regular=score(dict(home_goals=raw.get('regular_time_home_goals'),away_goals=raw.get('regular_time_away_goals')))
    full=score(raw)
    if regular is None or full is None:raise ValueError('Valid regularTime and fullTime scores required')
    digest=content_key(raw)
    if old.get('result_scope')=='REGULAR_TIME' and old.get('regular_time_source_hash')==digest and score(old)==regular:
        return copy.deepcopy(snapshot),None
    if score(old)!=full:raise ValueError('Stored score no longer matches archived fullTime; review required')
    updated=copy.deepcopy(snapshot);row=updated['history'][positions[0]]
    row.update(home_goals=regular[0],away_goals=regular[1],
        provider_full_time_home_goals=full[0],provider_full_time_away_goals=full[1],
        regular_time_home_goals=regular[0],regular_time_away_goals=regular[1],
        score_duration=raw['score_duration'],result_scope='REGULAR_TIME',regular_time_source_hash=digest)
    record=dict(id=content_key(dict(identity=identity,before=old,evidence=digest)),source=source,match_id=str(match_id),
        reason='90-minute 1X2 result from archived provider regularTime; extra time excluded',
        corrected_at=corrected_at or dt.datetime.now(dt.timezone.utc).isoformat(),
        before=copy.deepcopy(old),after=copy.deepcopy(row),evidence=copy.deepcopy(raw),
        previous_workspace_hash=content_key(snapshot),invalidated_analyses=['backtest_results','lab_rows'])
    updated.setdefault('data_corrections',[]).append(record)
    for field in INVALIDATED:
        if field in updated:updated[field]=['STALE_AFTER_DATA_CORRECTION',record['id']]
    # Old result arrays remain archived, but the UI must not display them as current.
    return updated,record


def commit_correction(store,expected,source,match_id):
    from archive_audit import normalize_cached
    fresh=store.audit_snapshot();snapshot=fresh.get('current')
    if snapshot is None or content_key(snapshot)!=expected:
        raise StorageError('Arkivet er ændret siden visningen. Genindlæs før rettelsen.')
    cached=[]
    for cache_key,matches in fresh['api']:
        parts=cache_key.rsplit(':',2)
        if len(parts)==3:cached.extend(normalize_cached(matches,parts[1],parts[2]))
    updated,record=prepare_correction(snapshot,cached,source,match_id)
    if record is None:return updated,expected,None
    # The original row and provider evidence are in this new snapshot; an old
    # whole-workspace version is additionally retained by the existing archive.
    fingerprint=store.save_workspace(updated,expected)
    return updated,fingerprint,record


def provider_final_fields(provider_score):
    """Keep fullTime evidence while using regularTime for extra-time matches."""
    full=provider_score.get('fullTime') or {};duration=provider_score.get('duration')
    if duration not in (None,'REGULAR','EXTRA_TIME','PENALTY_SHOOTOUT'):return None
    target=(provider_score.get('regularTime') or {}) if duration in ('EXTRA_TIME','PENALTY_SHOOTOUT') else full
    result=score(dict(home_goals=target.get('home'),away_goals=target.get('away')))
    if result is None:return None
    fields=dict(home_goals=result[0],away_goals=result[1])
    if duration:
        fields.update(score_duration=duration,result_scope='REGULAR_TIME')
        if score(dict(home_goals=full.get('home'),away_goals=full.get('away'))) is not None:
            fields.update(provider_full_time_home_goals=full['home'],provider_full_time_away_goals=full['away'])
        if duration in ('EXTRA_TIME','PENALTY_SHOOTOUT'):
            fields.update(regular_time_home_goals=result[0],regular_time_away_goals=result[1])
    return fields
