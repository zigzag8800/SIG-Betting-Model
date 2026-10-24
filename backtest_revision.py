"""Controlled replay before/after a stored data correction; no provider IO."""
import datetime as dt
import hashlib
import math
from pathlib import Path
from statistics import fmean
from persistent_store import content_key
from sig_model import Engine,load_history

METRICS=('brier','logloss','baseline_brier','baseline_logloss')
PROBABILITIES=('p1','px','p2')

def indexed(rows):
    result={}
    for r in rows:
        key=tuple(r[f] for f in ('date','league','home','away'))
        if key in result:raise ValueError('Duplicate test fixture; paired comparison is ambiguous')
        result[key]=r
    return result

def summary(rows):
    return dict(matches=len(rows),**{f:fmean(float(r[f]) for r in rows) if rows else None for f in METRICS})

def equivalent(left,right):
    a=indexed(left);b=indexed(right)
    return set(a)==set(b) and all(a[k]['actual']==b[k]['actual'] and all(math.isclose(float(a[k][f]),float(b[k][f]),rel_tol=0,abs_tol=1e-12) for f in (*METRICS,*PROBABILITIES)) for k in a)

def signature_settings(signature):
    if not isinstance(signature,(tuple,list)) or len(signature)!=5:return None
    return dict(asof=signature[1],source_label=signature[2],form_strength=signature[3],manager_changes=[list(x) for x in signature[4]])

def revision_report(old_history,new_history,old_rows,new_rows,stored_rows,settings,stored_signature):
    old=indexed(old_rows);new=indexed(new_rows)
    common=sorted(set(old)&set(new));changes=[]
    for k in common:
        a=old[k];b=new[k]
        probabilities_changed=any(abs(float(a[f])-float(b[f]))>1e-12 for f in PROBABILITIES)
        actual_changed=a['actual']!=b['actual']
        score_changed=any(abs(float(a[f])-float(b[f]))>1e-12 for f in METRICS)
        if probabilities_changed or actual_changed or score_changed:
            changes.append(dict(date=k[0],league=k[1],home=k[2],away=k[3],actual_before=a['actual'],actual_after=b['actual'],predictions_changed=probabilities_changed,
                brier_before=a['brier'],brier_after=b['brier'],logloss_before=a['logloss'],logloss_after=b['logloss']))
    old_inputs=indexed(old_history);new_inputs=indexed(new_history)
    changed_inputs=[dict(date=k[0],league=k[1],home=k[2],away=k[3],before=[old_inputs[k]['home_goals'],old_inputs[k]['away_goals']],after=[new_inputs[k]['home_goals'],new_inputs[k]['away_goals']])
        for k in sorted(set(old_inputs)&set(new_inputs)) if tuple(float(old_inputs[k][f]) for f in ('home_goals','away_goals'))!=tuple(float(new_inputs[k][f]) for f in ('home_goals','away_goals'))]
    leagues=sorted({r['league'] for r in old_rows+new_rows})
    old_summary=summary(old_rows);new_summary=summary(new_rows)
    return dict(generated_at=dt.datetime.now(dt.timezone.utc).isoformat(),settings=settings,
        engine_sha256=hashlib.sha256(Path(__file__).with_name('sig_model.py').read_bytes()).hexdigest(),
        old_history_hash=content_key(old_history),new_history_hash=content_key(new_history),
        original_stored_settings=signature_settings(stored_signature),same_settings_as_stored=signature_settings(stored_signature)==settings,
        stored_reference_present=bool(stored_rows),stored_reference_reproduced=equivalent(stored_rows,old_rows) if stored_rows else False,
        before=old_summary,after=new_summary,delta_after_minus_before={f:new_summary[f]-old_summary[f] if old_rows and new_rows else None for f in METRICS},
        identical_fixture_set=set(old)==set(new),paired_matches=len(common),added_test_matches=len(set(new)-set(old)),removed_test_matches=len(set(old)-set(new)),
        added_history_matches=len(set(new_inputs)-set(old_inputs)),removed_history_matches=len(set(old_inputs)-set(new_inputs)),changed_input_matches=changed_inputs,
        changed_prediction_matches=sum(r['predictions_changed'] for r in changes),changed_actual_matches=sum(r['actual_before']!=r['actual_after'] for r in changes),changed_test_rows=len(changes),changes=changes,
        per_league=[dict(league=league,before=summary([r for r in old_rows if r['league']==league]),after=summary([r for r in new_rows if r['league']==league])) for league in leagues],
        interpretation='Controlled internal replay with identical model settings; not a new independent validation or bookmaker comparison.')

def recompute(history,asof,form_strength,manager_changes,source_label,previous_snapshot=None):
    settings=dict(asof=asof.isoformat(),source_label=source_label,form_strength=form_strength,
        manager_changes=[[r['league'],r['team'],r['start_date']] for r in manager_changes])
    new_rows=load_history(Engine(form_strength=form_strength,manager_changes=manager_changes),history,cutoff=asof,backtest=True)
    if previous_snapshot is None:return new_rows,None
    old_history=previous_snapshot.get('history',[])
    old_rows=load_history(Engine(form_strength=form_strength,manager_changes=manager_changes),old_history,cutoff=asof,backtest=True)
    report=revision_report(old_history,history,old_rows,new_rows,previous_snapshot.get('backtest_results',[]),settings,previous_snapshot.get('backtest_signature'))
    report['previous_workspace_hash']=content_key(previous_snapshot)
    return new_rows,report
