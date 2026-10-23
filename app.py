"""SIG Betting Model: mobile Streamlit UI; no wagers and no bookmaker scraping."""
import csv
import datetime as dt
import io
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import json

import pandas as pd
import streamlit as st
from sig_model import Engine, load_history, value_rows

st.set_page_config(page_title='SIG Betting Model', page_icon='⚽', layout='centered')
st.title('⚽ SIG Betting Model 3.2')
st.caption('Mobilvenlig analyse · Chrome på iPhone · Ingen automatiske væddemål')
st.warning('Eksperimentel model: sandsynlighederne er ikke valideret som profitable. Minimumsodds bygger på en foreløbig usikkerhedsmargin.')

LEAGUES={'Premier League':'PL','Championship':'ELC','La Liga':'PD','Serie A':'SA','Bundesliga':'BL1','Ligue 1':'FL1'}
ALL_LEAGUES={**LEAGUES,'Superliga':'DK1'}
MARKET_LABELS={'1':'Hjemmesejr','X':'Uafgjort','2':'Udesejr','1X':'1X','X2':'X2','12':'12','O1.5':'Over 1,5 mål','O2.5':'Over 2,5 mål','O3.5':'Over 3,5 mål','U2.5':'Under 2,5 mål','U3.5':'Under 3,5 mål','U4.5':'Under 4,5 mål','BTTS_Y':'Begge scorer: ja','BTTS_N':'Begge scorer: nej','H_O0.5':'Hjemmehold scorer','H_O1.5':'Hjemmehold over 1,5 mål','A_O0.5':'Udehold scorer','A_O1.5':'Udehold over 1,5 mål'}
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

# Cache successful responses only. A denied/rate-limited request is never cached.
@st.cache_data(ttl=21600, show_spinner=False)
def api_matches(token, league, season):
    url=f'https://api.football-data.org/v4/competitions/{league}/matches?season={season}'
    req=urllib.request.Request(url,headers={'X-Auth-Token':token,'Accept':'application/json','User-Agent':'SIG-Betting-Model/1.1'})
    try:
        with urllib.request.urlopen(req,timeout=25) as response:
            return json.load(response)['matches']
    except urllib.error.HTTPError as e:
        body=e.read().decode('utf-8','replace')[:180]
        raise ApiError(e.code, body, e.headers.get('Retry-After')) from e
    except Exception as e:
        raise RuntimeError(f'Kunne ikke hente {league}/{season}: {e}') from e

class ApiError(Exception):
    def __init__(self, status, message, retry_after=None):
        super().__init__(message)
        self.status=status
        self.retry_after=retry_after


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
        st.caption('Vælg helst 1–2 sæsoner ad gangen. Kun succesfulde API-svar caches i 6 timer. Superliga kræver CSV. Manglende adgang vises tydeligt.')
        fetch=st.button('Hent kampdata',type='primary')
        if fetch:
            if not token or not chosen or not seasons:
                st.error('Angiv API-nøgle, mindst én liga og en sæson.')
            else:
                hist=[]; fixtures=[]; errors=[]; successful=[]; denied=[]; rate_limited=False
                jobs=[(name, season) for name in chosen for season in sorted(seasons)]
                # Free football-data.org plans commonly allow 10 requests/minute.
                # Limit this click to 8 requests to leave room for other clients.
                max_requests=8
                attempted=0
                with st.spinner('Henter kampe – højst 8 API-kald ad gangen…'):
                    for name, season in jobs:
                        if attempted>=max_requests:
                            errors.append(f'Ikke hentet: resten af liga/sæson-valgene. Vælg færre ligaer/sæsoner, og hent igen senere.')
                            break
                        attempted+=1
                        try:
                            matches=api_matches(token,LEAGUES[name],season)
                            h,f=convert(matches,LEAGUES[name]); hist+=h; fixtures+=f
                            successful.append(f'{name} {season}: {len(h)} afsluttede, {len(f)} kommende')
                        except ApiError as e:
                            if e.status==403:
                                denied.append(f'{name} {season}')
                            elif e.status==429:
                                errors.append(f'API-grænse nået (429). Stopper yderligere kald. Vent mindst {e.retry_after or "60"} sekunder før næste forsøg.')
                                rate_limited=True
                                break
                            elif e.status==401:
                                errors.append('API-nøglen blev afvist (401). Kontrollér nøglen i Streamlit Secrets.')
                                break
                            else:
                                errors.append(f'{name} {season}: HTTP {e.status}: {e}')
                        except Exception as e:
                            errors.append(f'{name} {season}: {e}')
                if successful:
                    # Preserve data from prior fetches when a later batch is partial.
                    old_h=st.session_state.get('history',[])
                    old_f=st.session_state.get('fixtures',[])
                    hist=list({(r['date'],r['league'],r['home'],r['away']):r for r in old_h+hist}.values())
                    fixtures=list({(r['date'],r['league'],r['home'],r['away']):r for r in old_f+fixtures}.values())
                    st.session_state['history']=hist
                    st.session_state['fixtures']=fixtures
                    st.session_state['source_label']='football-data.org'
                st.session_state['api_fetch_report']={'successful':successful,'denied':denied,'errors':errors}
        report=st.session_state.get('api_fetch_report')
        if report:
            if report['successful']:
                st.success('Hentet: '+str(len(report['successful']))+' liga/sæson-kombinationer. '+str(len(st.session_state.get('history',[])))+' afsluttede og '+str(len(st.session_state.get('fixtures',[])))+' kommende kampe i hukommelsen.')
                with st.expander('Se præcis hvilke sæsoner der lykkedes'):
                    st.write('\n\n'.join(report['successful']))
            if report['denied']:
                st.warning('Ingen adgang (403), sprunget over: '+', '.join(report['denied']))
            if report['errors']:
                st.warning('\n\n'.join(report['errors']))
            st.caption('Et grønt antal betyder kun, at NOGLE data er hentet. Kontrollér listen over lykkede ligaer og sæsoner, før du stoler på kandidaterne.')
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
    st.divider()
    st.caption('Tilføj eventuelt Superligaen eller ekstra historik som CSV til eksisterende API-data. Holdnavne og ligakoder skal være konsekvente.')
    extra_h=st.file_uploader('Ekstra historik (valgfri CSV)',type='csv',key='extra_h')
    extra_f=st.file_uploader('Ekstra kampprogram (valgfri CSV)',type='csv',key='extra_f')
    if st.button('Tilføj CSV-data'):
        try:
            eh=parse_upload(extra_h,HIST_FIELDS); ef=parse_upload(extra_f,FIX_FIELDS)
            st.session_state['history']=list({(r['date'],r['league'],r['home'],r['away']):r for r in st.session_state.get('history',[])+eh}.values())
            st.session_state['fixtures']=list({(r['date'],r['league'],r['home'],r['away']):r for r in st.session_state.get('fixtures',[])+ef}.values())
            st.success(f'Tilføjet {len(eh)} historiske og {len(ef)} kommende kampe (dubletter fjernet).')
        except Exception as e: st.error(str(e))
    with st.expander('CSV-skabeloner'):
        st.download_button('Historik-skabelon',to_csv([],HIST_FIELDS),'history_template.csv','text/csv')
        st.download_button('Kampprogram-skabelon',to_csv([],FIX_FIELDS),'fixtures_template.csv','text/csv')

with st.expander('2 · Odds (valgfrit)'):
    st.caption('Ingen bookmaker-API er koblet på endnu. Indlæs kun odds, du har lov til at anvende. Uden odds viser appen beregnede minimumspriser.')
    of=st.file_uploader('odds.csv',type='csv',key='o')
    if of is not None:
        try: st.session_state['odds']=parse_upload(of,ODDS_FIELDS[:6]); st.success(f'{len(st.session_state["odds"])} odds indlæst.')
        except Exception as e: st.error(str(e))
    st.download_button('Hent tom oddsskabelon',to_csv([],ODDS_FIELDS),'odds_template.csv','text/csv')

with st.expander('3 · Analyseindstillinger'):
    asof=st.date_input('Analysedato',value=dt.date.today())
    weekend=st.checkbox('Kun kommende weekend (lørdag og søndag)',value=True)
    if weekend:
        days_to_sat=(5-asof.weekday())%7
        start=asof+dt.timedelta(days=days_to_sat)
        end=start+dt.timedelta(days=1)
        st.caption(f'Weekend: {start.isoformat()} – {end.isoformat()}')
    else:
        start=st.date_input('Fra dato',value=asof,min_value=asof)
        end=st.date_input('Til dato',value=asof+dt.timedelta(days=7),min_value=start)
    markets=st.multiselect('Markeder',list(MARKET_LABELS),default=list(MARKET_LABELS),format_func=lambda m:MARKET_LABELS[m])
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
        candidates=value_rows(eng,fixtures,odds,asof,edge_min=edge,margin=margin,until=end,markets=markets)
        candidates=[r for r in candidates if r['date']>=start.isoformat()]
        # Additional minimum sample filter is a UI safety rule.
        for r in candidates:
            if r['history_min']<min_games and r['status']=='VALUE_TO_REVIEW': r['status']='INSUFFICIENT_HISTORY'
        eligible=[r for r in candidates if r['history_min']>=min_games]
        # Value-first ranking when odds exist; otherwise probability-first with one
        # candidate per match, avoiding repeated ultra-short correlated markets.
        value=[r for r in eligible if r['status']=='VALUE_TO_REVIEW']
        no_price=[r for r in eligible if r['status']=='NO_PRICE']
        others=[r for r in eligible if r['status'] not in ('VALUE_TO_REVIEW','NO_PRICE')]
        value.sort(key=lambda r:(-r['model_p'],-r['ev']))
        no_price.sort(key=lambda r:-r['model_p'])
        others.sort(key=lambda r:-r['model_p'])
        ordered=value+no_price+others
        chosen=[]; match_count={}
        for r in ordered:
            key=(r['date'],r['league'],r['home'],r['away'])
            # No more than two markets per fixture, and one without real odds.
            limit=2 if r['status']=='VALUE_TO_REVIEW' else 1
            if match_count.get(key,0)>=limit: continue
            match_count[key]=match_count.get(key,0)+1
            chosen.append(r)
            if len(chosen)>=30: break
        df=pd.DataFrame(chosen)
        st.subheader('4 · Kandidater')
        st.metric('Historiske kampe',sum(1 for r in hist if r['date']<asof.isoformat()))
        if df.empty:
            st.info('Ingen kandidater endnu. Hent flere historiske sæsoner eller kontrollér kommende kampe.')
        else:
            status_counts=pd.DataFrame(eligible)['status'].value_counts() if eligible else {}
            st.metric('Markeder screenet',len(candidates))
            st.metric('Kandidater i valgt periode',len(df))
            st.metric('Mulige value-spil til kontrol',int(status_counts.get('VALUE_TO_REVIEW',0)))
            st.caption('⭐ markerer op til 10 øverste kandidater, ikke dokumenteret sikre spil. Uden odds er der ingen bekræftet værdi. Der vælges højst 1 marked pr. kamp uden odds.')
            df=df.head(30).copy()
            df.insert(0,'⭐',['⭐' if i<10 else '' for i in range(len(df))])
            df['marked_navn']=df['market'].map(MARKET_LABELS)
            display=['⭐','date','league','home','away','marked_navn','model_p','fair_odds','min_odds','best_odds','bookmaker','status']
            st.dataframe(df[display],use_container_width=True,hide_index=True)
            st.download_button('Download 30 kandidater (CSV)',to_csv(df.to_dict('records'),list(df.columns)),'sig_kandidater.csv','text/csv')
            if not odds: st.info('Ingen odds indlæst: disse er kandidater med modelberegnede minimumsodds, ikke godkendte væddemål.')
        st.caption('Kort, hjørnespark, Opta/xG og automatisk bookmakerintegration er IKKE implementeret i 3.1. Seks ligaer via API; Superliga via CSV.')
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
