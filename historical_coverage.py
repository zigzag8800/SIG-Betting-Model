"""Safe import and coverage audit for user-supplied Football-Data.co.uk CSV files.

Historical diagnostics only: no unlicensed automatic collection and no changes
to probability estimates. Do not join bookmaker odds to API-team names without
an explicit verified team mapping.
"""
import csv
import io

DIVISIONS={'E0':'Premier League','E1':'Championship','SP1':'La Liga',
           'I1':'Serie A','D1':'Bundesliga','F1':'Ligue 1'}
MEASURES={
    'Skud':('HS','AS'),
    'Skud på mål':('HST','AST'),
    'Hjørnespark':('HC','AC'),
    'Gule kort':('HY','AY'),
    'Røde kort':('HR','AR'),
    'Resultat':('FTHG','FTAG'),
}
ODDS_FIELDS=('B365H','B365D','B365A')
MAX_BYTES=5*1024*1024
MAX_ROWS=20000

def audit_uploaded_files(files):
    reports=[]
    for upload in files:
        name=upload.name
        raw=upload.getvalue()
        if len(raw)>MAX_BYTES:
            reports.append({'Fil':name,'Liga':'Ukendt','Kampe':0,'Fejl':'Fil større end 5 MB'})
            continue
        try:
            payload=raw.decode('utf-8-sig',errors='replace')
            reader=csv.DictReader(io.StringIO(payload))
            columns=set(reader.fieldnames or [])
            if not {'Div','Date','HomeTeam','AwayTeam'}.issubset(columns):
                raise ValueError('Mangler Div, Date, HomeTeam eller AwayTeam')
            buckets={}
            for i,row in enumerate(reader):
                if i>=MAX_ROWS:
                    raise ValueError('Over 20.000 rækker')
                div=(row.get('Div') or '').strip().upper()
                if div not in DIVISIONS or not row.get('Date') or not row.get('HomeTeam') or not row.get('AwayTeam'):
                    continue
                buckets.setdefault(div,[]).append(row)
            for div,rows in sorted(buckets.items()):
                result={'Fil':name,'Liga':DIVISIONS[div],'Kampe':len(rows),'Fejl':''}
                for metric,fields in MEASURES.items():
                    n=sum(all(str(r.get(f,'')).strip() not in ('','nan','None') for f in fields) for r in rows)
                    result[metric+' (%)']=round(100*n/len(rows),1) if rows else 0
                odds=sum(all(str(r.get(f,'')).strip() not in ('','nan','None') for f in ODDS_FIELDS) for r in rows)
                result['Bet365 1X2 (%)']=round(100*odds/len(rows),1) if rows else 0
                reports.append(result)
            if not buckets:
                reports.append({'Fil':name,'Liga':'Ukendt','Kampe':0,'Fejl':'Ingen rækker i de seks understøttede ligaer'})
        except Exception as exc:
            reports.append({'Fil':name,'Liga':'Ukendt','Kampe':0,'Fejl':str(exc)[:160]})
    return reports
