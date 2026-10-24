"""Bookmaker benchmark using the SAME historical CSV rows for both models and odds.

This intentionally does not join differently spelled team names from distinct providers.
Closing prices are used only when all three explicitly closing-price fields exist.
"""
import csv
import datetime as dt
import io
import math
import zipfile
from pathlib import PurePosixPath
from types import SimpleNamespace
from historical_coverage import DIVISIONS
from model_lab import compare_variants

CLOSING_SETS=(('B365CH','B365CD','B365CA'),('PSCH','PSCD','PSCA'),
              ('AvgCH','AvgCD','AvgCA'))
OPENING_SETS=(('B365H','B365D','B365A'),)
MAX_BYTES=5*1024*1024

def parse_date(value):
    v=(value or '').strip()
    for fmt in ('%d/%m/%Y','%d/%m/%y','%Y-%m-%d'):
        try:
            return dt.datetime.strptime(v,fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError('Ukendt datoformat: '+v[:24])

PROVIDERS={'B365':(('B365CH','B365CD','B365CA'),('B365H','B365D','B365A')),
           'Avg':(('AvgCH','AvgCD','AvgCA'),None),
           'PS':(('PSCH','PSCD','PSCA'),None)}
PINNACLE_WARNING_FROM='2025-07-23'

def expand_historical_files(files):
    '''Read only the six target divisions; never extract ZIP paths to disk.'''
    output=[]
    total=0
    for item in files:
        raw=item.getvalue()
        if item.name.lower().endswith('.zip'):
            if len(raw)>20*1024*1024:
                raise ValueError('ZIP større end 20 MB')
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                if len(archive.infolist())>100:
                    raise ValueError('ZIP indeholder for mange filer')
                for entry in archive.infolist():
                    path=PurePosixPath(entry.filename)
                    if path.is_absolute() or '..' in path.parts or entry.flag_bits & 1:
                        raise ValueError('Usikker eller krypteret ZIP-post')
                    if path.suffix.lower()!='.csv' or path.stem.upper() not in DIVISIONS:
                        continue
                    if entry.file_size>MAX_BYTES:
                        raise ValueError('CSV i ZIP større end 5 MB')
                    total+=entry.file_size
                    if total>30*1024*1024:
                        raise ValueError('De valgte CSV-filer fylder over 30 MB')
                    payload=archive.read(entry)
                    output.append(SimpleNamespace(name=item.name+'/'+path.name,getvalue=lambda data=payload:data))
        else:
            if len(raw)>MAX_BYTES:
                raise ValueError('CSV større end 5 MB')
            total+=len(raw)
            if total>30*1024*1024:
                raise ValueError('CSV-filer fylder over 30 MB')
            output.append(item)
    if files and not output:
        raise ValueError('Ingen CSV-filer for E0, SP1, I1, D1 eller F1 fundet')
    return output


def parse_historical_csv(files, provider='B365'):
    if provider not in PROVIDERS:
        raise ValueError('Ukendt oddsreference')
    closing_fields,opening_fields=PROVIDERS[provider]
    price_sets=[closing_fields]+([opening_fields] if opening_fields else [])
    matches={}
    rejected=0
    for item in expand_historical_files(files):
        raw=item.getvalue()
        if len(raw)>MAX_BYTES:
            raise ValueError(item.name+': CSV større end 5 MB')
        reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig',errors='replace')))
        if not {'Div','Date','HomeTeam','AwayTeam','FTHG','FTAG'}.issubset(reader.fieldnames or []):
            raise ValueError(item.name+': mangler nødvendige kampkolonner')
        for row in reader:
            div=(row.get('Div') or '').strip().upper()
            if div not in DIVISIONS: continue
            try:
                d=parse_date(row['Date'])
                h=row['HomeTeam'].strip()
                a=row['AwayTeam'].strip()
                hg=int(row['FTHG']); ag=int(row['FTAG'])
                if not h or not a or hg<0 or ag<0: raise ValueError('ugyldigt hold/resultat')
            except (ValueError,TypeError,AttributeError):
                rejected+=1; continue
            code={'E0':'PL','SP1':'PD','I1':'SA','D1':'BL1','F1':'FL1'}[div]
            key=(d,code,h,a)
            odds=None; odds_provider=None; odds_type=None
            for fields in price_sets:
                if provider=='PS' and d>=PINNACLE_WARNING_FROM:
                    continue
                try:
                    prices=[float(row.get(x,'')) for x in fields]
                    if all(math.isfinite(p) and p>1.0 for p in prices):
                        odds=prices;odds_provider=provider
                        odds_type='closing' if fields==closing_fields else 'opening'
                        break
                except (ValueError,TypeError):
                    continue
            # Only accept a duplicate if it carries better price coverage.
            candidate={'date':d,'league':code,'home':h,'away':a,
                       'home_goals':hg,'away_goals':ag,
                       '_odds':odds,'_odds_type':odds_type,'_provider':odds_provider}
            if key not in matches or (matches[key]['_odds_type']!='closing' and odds_type=='closing') or (not matches[key]['_odds'] and odds):
                matches[key]=candidate
    return list(matches.values()),rejected

def compare_to_bookmaker(matches,test_start,cutoff,closing_only=True):
    history=[{k:r[k] for k in ('date','league','home','away','home_goals','away_goals')} for r in matches]
    records=compare_variants(history,cutoff,test_start)
    lookup={(r['date'],r['league'],r['home'],r['away']):r for r in matches}
    output=[]
    excluded={'no_odds':0,'opening_only':0}
    for r in records:
        # Both models receive the SAME eligible fixtures, including price coverage.
        if r['variant'] not in ('A · Nuværende 3.6','E · Form 10 + Elo'):
            continue
        src=lookup[(r['date'],r['league'],r['home'],r['away'])]
        odds=src['_odds']
        if not odds:
            excluded['no_odds']+=1;continue
        if closing_only and src['_odds_type']!='closing':
            excluded['opening_only']+=1;continue
        implied=[1/p for p in odds]
        normalizer=sum(implied)
        market=[x/normalizer for x in implied]
        actual=r['actual']; outcome={'1':0,'X':1,'2':2}[actual]
        market_brier=sum((x-int(i==outcome))**2 for i,x in enumerate(market))/3
        output.append({**r,'odds_type':src['_odds_type'],'odds_provider':src['_provider'],
                       'market_p1':market[0],'market_px':market[1],'market_p2':market[2],
                       'market_brier':market_brier,'market_logloss':-math.log(market[outcome]),
                       'market_overround':normalizer-1})
    return output,excluded
