"""SIG Betting Model: mobile Streamlit UI; no wagers and no bookmaker scraping."""
import csv
import datetime as dt
import io
import os
import time
import urllib.error
import urllib.parse
import urllib.request

import pandas as pd
import streamlit as st
from sig_model import Engine, load_history, value_rows

st.set_page_config(page_title='SIG Betting Model', page_icon='⚽', layout='centered')
st.title('⚽ SIG Betting Model')
st.caption('Mobilvenlig analyse · Chrome på iPhone · Ingen automatiske væddemål')
st.warning('Eksperimentel model: sandsynlighederne er ikke valideret som profitable. Minimumsodds bygger på en foreløbig usikkerhedsmargin.')

LEAGUES={'Premier League':'PL','Championship':'ELC','La Liga':'PD','Serie A':'SA','Bundesliga':'BL1','Ligue 1':'FL1'}
HIST_FIELDS=['date','league','home','away','home_goals','away_goals']
FIX_FIELDS=['date','league','home','away']
ODDS_FIELDS=['date','league','home','away','market','odds','bookmaker','captured_at']

def parse_upload(upload, required):
    if upload is None: return []
    text=upload.getvalue().decode('utf-8-sig')
    reader=csv.DictReader(io.StringIO(text))
    if not set(required).issubset(reader.fieldnames or []):
        raise ValueError('CSV skal indeholde kolonnerne: '+', '.join(required))
    return list(reader)

def to_csv(rows, fields):
    out=io.StringIO(); writer=csv.DictWriter(out, fieldnames=fields, extrasaction='ignore')
    writer.writeheader(); writer.writerows(rows)
    return out.getvalue().encode('utf-8-sig')

@st.cache_data(ttl=3600, show_spinner=False)
def api_matches(token, league, season):
    url=f'https://api.football-data.org/v4/competitions/{league}/matches?season={season}'
    req=urllib.request.Request(url,headers={'X-Auth-Token':token,'Accept':'application/json','User-Agent':'SIG-Betting-Model/1.0'})
    import json
    try:
        with urllib.request.urlopen(req,timeout=25) as response:
            return json.load(response)['matches']
    except urllib.error.HTTPError as e:
        body=e.read().decode('utf-8','replace')[:220]
        raise RuntimeError(f'API HTTP {e.code}: {body}') from e
    except Exception as e:
        raise RuntimeError(f'Kunne ikke hente {league}/{season}: {e}') from e

def convert(matches, league):
    history=[]; fixtures=[]
    for m in matches:
        home=m.get('homeTeam') or {}; away=m.get('awayTeam') or {}
        h=home.get('name'); a=away.get('name'); d=(m.get('utcDate') or '')[:10]
        if not (h and a and d): continue
        base={'date':d,'league':league,'home':h,'away':a}
        score=(m.get('score') or {}).get('fullTime') or {}
        if m.get('status')=='FINISHED' and score.get('home') is not None and score.get('away') is not None:
            history.append({**base,'home_goals':score['home'],'away_goals':score['away']})
        elif m.get('status') in ('SCHEDULED','TIMED'):
            fixtures.append(base)
    return history, fixtures

with st.expander('1 · Datakilde',expanded=True):
    source=st.radio('Hvor kommer kampdata fra?', ['football-data.org API','Upload CSV-filer'],horizontal=False)
    if source=='football-data.org API':
        secret=st.secrets.get('FOOTBALL_DATA_API_KEY','') if hasattr(st,'secrets') else ''
        token=st.text_input('Din API-nøgle (skjult)',value=secret,type='password',help='Sendes kun til football-data.org fra appens server. Gemmes ikke i kode eller downloadfiler.')
        chosen=st.multiselect('Ligaer',list(LEAGUES),default=['Premier League'])
        today=dt.date.today()
        default_season=today.year if today.month>=7 else today.year-1
        seasons=st.multiselect('Sæsonernes startår',list(range(default_season-4,default_season+1)),default=[default_season-1,default_season])
        st.caption('Gratis API kan begrænse antal sæsoner, ligaer og kald. Vælg én liga først. Superligaen kan indlæses via CSV.')
        fetch=st.button('Hent kampdata',type='primary')
        if fetch:
            if not token or not chosen or not seasons:
                st.error('Angiv API-nøgle, mindst én liga og en sæson.')
            else:
                hist=[]; fixtures=[]; errors=[]
                with st.spinner('Henter kampe fra football-data.org…'):
                    for name in chosen:
                        for season in sorted(seasons):
                            try:
                                matches=api_matches(token,LEAGUES[name],season)
                                h,f=convert(matches,LEAGUES[name]); hist+=h; fixtures+=f
                            except Exception as e: errors.append(f'{name} {season}: {e}')
                st.session_state['history']=hist; st.session_state['fixtures']=fixtures
                st.session_state['source_label']='football-data.org'
                if errors: st.warning('\n\n'.join(errors))
                st.success(f'Indlæst: {len(hist)} afsluttede og {len(fixtures)} kommende kampe.')
    else:
        hf=st.file_uploader('Historik: history.csv',type='csv',key='h')
        ff=st.file_uploader('Kommende kampe: fixtures.csv',type='csv',key='f')
        if st.button('Indlæs CSV'):
            try:
                st.session_state['history']=parse_upload(hf,HIST_FIELDS)
                st.session_state['fixtures']=parse_upload(ff,FIX_FIELDS)
                st.session_state['source_label']='CSV'
                st.success('CSV-filer indlæst.')
            except Exception as e: st.error(str(e))

with st.expander('2 · Odds (valgfrit)'):
    st.caption('Ingen bookmaker-API er koblet på endnu. Indlæs kun odds, du har lov til at anvende. Uden odds viser appen beregnede minimumspriser.')
    of=st.file_uploader('odds.csv',type='csv',key='o')
    if of is not None:
        try: st.session_state['odds']=parse_upload(of,ODDS_FIELDS[:6]); st.success(f'{len(st.session_state["odds"])} odds indlæst.')
        except Exception as e: st.error(str(e))
    st.download_button('Hent tom oddsskabelon',to_csv([],ODDS_FIELDS),'odds_template.csv','text/csv')

with st.expander('3 · Analyseindstillinger'):
    asof=st.date_input('Analysedato',value=dt.date.today())
    min_games=st.slider('Mindst historiske kampe pr. hold',5,30,12)
    edge=st.slider('Mindste beregnede EV',0,20,4)/100
    margin=st.slider('Tillæg til minimumsodds (%)',0,10,3)/100

hist=st.session_state.get('history',[])
fixtures=st.session_state.get('fixtures',[])
odds=st.session_state.get('odds',[])
if hist:
    try:
        eng=Engine()
        load_history(eng,hist,cutoff=asof)
        candidates=value_rows(eng,fixtures,odds,asof,edge_min=edge,margin=margin)
        # Additional minimum sample filter is a UI safety rule.
        for r in candidates:
            if r['history_min']<min_games and r['status']=='VALUE_TO_REVIEW': r['status']='INSUFFICIENT_HISTORY'
        eligible=[r for r in candidates if r['history_min']>=min_games]
        df=pd.DataFrame(eligible)
        st.subheader('4 · Kandidater')
        st.metric('Historiske kampe',sum(1 for r in hist if r['date']<asof.isoformat()))
        if df.empty:
            st.info('Ingen kandidater endnu. Hent flere historiske sæsoner eller kontrollér kommende kampe.')
        else:
            status_counts=df['status'].value_counts()
            st.metric('Markeder screenet',len(df))
            st.metric('Mulige value-spil til kontrol',int(status_counts.get('VALUE_TO_REVIEW',0)))
            st.caption('⭐ viser de første 10 kandidater efter modellens sortering – ikke verificeret høj sandsynlighed eller garanteret profit.')
            df=df.head(30).copy()
            df.insert(0,'⭐',['⭐' if i<10 else '' for i in range(len(df))])
            display=['⭐','date','league','home','away','market','model_p','fair_odds','min_odds','best_odds','bookmaker','status']
            st.dataframe(df[display],use_container_width=True,hide_index=True)
            st.download_button('Download 30 kandidater (CSV)',to_csv(df.to_dict('records'),list(df.columns)),'sig_kandidater.csv','text/csv')
            if not odds: st.info('Ingen odds indlæst: disse er kandidater med modelberegnede minimumsodds, ikke godkendte væddemål.')
        st.subheader('5 · Historisk test')
        if st.button('Kør kronologisk backtest'):
            test_engine=Engine()
            back=load_history(test_engine,hist,cutoff=asof,backtest=True)
            if back:
                bdf=pd.DataFrame(back)
                st.metric('Testede kampe',len(bdf))
                st.metric('Gennemsnitlig Brier-score',f'{bdf.brier.mean():.4f}')
                st.metric('Gennemsnitlig log-loss',f'{bdf.logloss.mean():.4f}')
                st.download_button('Download backtest (CSV)',to_csv(back,list(back[0])),'sig_backtest.csv','text/csv')
                st.caption('Backtest måler prognosekvalitet, ikke profit. Ingen ROI uden tidskorrekte bookmakerodds.')
            else: st.info('Ikke nok historik til backtest.')
    except Exception as e: st.error(f'Analysefejl: {e}')
else:
    st.info('Start med at hente historiske kampe ovenfor. Intet er simuleret eller opdigtet.')

st.divider()
st.caption('SIG Model · Kun analyse · Ingen automatiske spil · Opta, kort, hjørnespark og live bookmakerodds er endnu ikke integreret.')
