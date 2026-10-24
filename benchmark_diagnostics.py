"""Paired bookmaker-vs-SIG diagnostic summaries from existing benchmark rows.

Every comparison is per fixture; no cross-model unpaired aggregates.
"""
from collections import defaultdict

def diagnostic_tables(rows):
    focus={'A · Nuværende 3.6':'SIG 3.6', 'E · Form 10 + Elo':'SIG E'}
    groups=defaultdict(list)
    for row in rows:
        label=focus.get(row.get('variant'))
        if not label: continue
        market_home=float(row['market_p1'])
        favorite=max(float(row[k]) for k in ('market_p1','market_px','market_p2'))
        if favorite<.40: band='Under 40 %'
        elif favorite<.50: band='40–50 %'
        elif favorite<.60: band='50–60 %'
        elif favorite<.70: band='60–70 %'
        else: band='70 %+'
        diff=float(row['brier'])-float(row['market_brier'])
        entry={'model':label,'league':row['league'],'band':band,
               'home_band': 'Topfavorit hjemme' if market_home>=.65 else
                            'Underdog hjemme' if market_home<=.25 else 'Øvrige',
               'date':row['date'],'home':row['home'],'away':row['away'],
               'difference':diff,'sig_brier':float(row['brier']),
               'book_brier':float(row['market_brier']),
               'sig_logloss':float(row['logloss']),
               'book_logloss':float(row['market_logloss'])}
        groups[(label,'Liga',row['league'])].append(entry)
        groups[(label,'Favoritstyrke',band)].append(entry)
        groups[(label,'Hjemmeprofil',entry['home_band'])].append(entry)
        groups[(label,'Alle','Samlet')].append(entry)
    summary=[]
    for (model,category,group),rr in sorted(groups.items()):
        n=len(rr)
        summary.append({'Model':model,'Opdeling':category,'Gruppe':group,'Kampe':n,
          'SIG Brier':round(sum(r['sig_brier'] for r in rr)/n,4),
          'Bookmaker Brier':round(sum(r['book_brier'] for r in rr)/n,4),
          'Forskel (SIG − bookmaker)':round(sum(r['difference'] for r in rr)/n,4),
          'SIG log-loss':round(sum(r['sig_logloss'] for r in rr)/n,4),
          'Bookmaker log-loss':round(sum(r['book_logloss'] for r in rr)/n,4)})
    # Unique fixture per model, sorted by paired Brier disadvantage.
    biggest=sorted((r for key,rr in groups.items() if key[1]=='Alle' for r in rr),
                   key=lambda r:r['difference'],reverse=True)[:20]
    examples=[{'Model':r['model'],'Dato':r['date'],'Liga':r['league'],
              'Hjemme':r['home'],'Ude':r['away'],
              'SIG − bookmaker Brier':round(r['difference'],4)} for r in biggest]
    return summary,examples
