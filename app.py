"""SIG Betting Model: mobile Streamlit UI; no wagers and no bookmaker scraping."""
import csv
import base64
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
from model_lab import compare_variants
from bookmaker_lab import parse_historical_csv, compare_to_bookmaker
from historical_coverage import audit_uploaded_files
from types import SimpleNamespace

st.set_page_config(page_title='SIG Betting Model', page_icon='⚽', layout='centered')
st.title('⚽ SIG Betting Model 3.6')
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

def save_backtest_to_github(rows, asof, form_strength):
    """Save the latest completed backtest through a narrowly scoped GitHub token.

    Configure BACKTEST_GITHUB_TOKEN in Streamlit Secrets. No token is placed
    in source code or exported CSV files.
    """
    token=st.secrets.get('BACKTEST_GITHUB_TOKEN','')
    if not token:
        return False, 'Opsæt BACKTEST_GITHUB_TOKEN i Streamlit Secrets for automatisk GitHub-lagring.'
    if not rows:
        return False, 'Ingen testkampe at gemme.'
    path='reports/latest_backtest.csv'
    url='https://api.github.com/repos/zigzag8800/SIG-Betting-Model/contents/'+path
    headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json',
             'X-GitHub-Api-Version':'2022-11-28','User-Agent':'SIG-Betting-Model'}
    sha=None
    try:
        req=urllib.request.Request(url,headers=headers)
        with urllib.request.urlopen(req,timeout=20) as response:
            sha=json.load(response).get('sha')
    except urllib.error.HTTPError as exc:
        if exc.code!=404:
            return False, f'GitHub kunne ikke læse eksisterende fil (HTTP {exc.code}).'
    except Exception as exc:
        return False, f'GitHub-forbindelse fejlede: {exc}'
    payload={'message':f'Update backtest results (as of {asof})',
             'content':base64.b64encode(to_csv(rows,list(rows[0]))).decode('ascii')}
    if sha:
        payload['sha']=sha
    req=urllib.request.Request(url,data=json.dumps(payload).encode('utf-8'),
                               headers={**headers,'Content-Type':'application/json'},method='PUT')
    try:
        with urllib.request.urlopen(req,timeout=30) as response:
            json.load(response)
        return True, 'Backtest gemt i GitHub: reports/latest_backtest.csv'
    except urllib.error.HTTPError as exc:
        return False, f'GitHub afviste lagring (HTTP {exc.code}). Kontrollér token og Contents: Read and write.'
    except Exception as exc:
        return False, f'Kunne ikke gemme backtest: {exc}'


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
        chosen=st.multiselect('Ligaer',list(LEAGUES),default=list(LEAGUES))
        today=dt.date.today()
        default_season=today.year if today.month>=7 else today.year-1
        seasons=st.multiselect('Sæsonernes startår',list(range(default_season-4,default_season+1)),default=[default_season-1,default_season])
        st.caption('Alle seks API-ligaer er forvalgt. Ét tryk henter alle valgte ligaer og sæsoner med automatisk hastighedsbegrænsning. Superliga kræver fortsat CSV.')
        st.caption('Data fra tidligere vellykkede hentninger i denne browsersession bevares. API-cache gælder 6 timer.')
        if st.button('Ryd indlæste kampdata', help='Fjerner kun kampdata i denne browsersession; ikke din API-nøgle.'):
            for key in ('history','fixtures','loaded_combos','api_fetch_report'):
                st.session_state.pop(key, None)
            st.rerun()
        fetch=st.button('Hent kampdata',type='primary')
        if fetch:
            if not token or not chosen or not seasons:
                st.error('Angiv API-nøgle, mindst én liga og en sæson.')
            else:
                hist=[]; fixtures=[]; errors=[]; successful=[]; denied=[]; rate_limited=False
                loaded=st.session_state.setdefault('loaded_combos', {})
                jobs=[(name, season) for name in chosen for season in sorted(seasons) if f'{LEAGUES[name]}:{season}' not in loaded]
                skipped=len(chosen)*len(seasons)-len(jobs)
                # Pace requests below the common 10 requests/minute free-tier limit.
                # An unavailable league is reported; already loaded seasons are skipped.
                progress=st.progress(0, text=f'0 af {len(jobs)} behandlet') if jobs else None
                with st.spinner('Henter alle valgte ligaer og sæsoner…'):
                    for index, (name, season) in enumerate(jobs, start=1):
                        if index>1:
                            time.sleep(7)
                        if progress is not None:
                            progress.progress((index-1)/len(jobs), text=f'Henter {index} af {len(jobs)}: {name} {season}')
                        try:
                            matches=api_matches(token,LEAGUES[name],season)
                            h,f=convert(matches,LEAGUES[name]); hist+=h; fixtures+=f
                            successful.append(f'{name} {season}: {len(h)} afsluttede, {len(f)} kommende')
                            loaded[f'{LEAGUES[name]}:{season}']={'name':name,'season':season,'history':len(h),'fixtures':len(f)}
                        except ApiError as e:
                            if e.status==403:
                                denied.append(f'{name} {season}')
                            elif e.status==429:
                                errors.append(f'API-grænse nået (429). Resterende kald stoppet. Vent mindst {e.retry_after or "60"} sekunder og tryk igen for kun at hente manglende sæsoner.')
                                rate_limited=True
                                break
                            elif e.status==401:
                                errors.append('API-nøglen blev afvist (401). Kontrollér nøglen i Streamlit Secrets.')
                                break
                            else:
                                errors.append(f'{name} {season}: HTTP {e.status}: {e}')
                        except Exception as e:
                            errors.append(f'{name} {season}: {e}')
                        finally:
                            if progress is not None:
                                progress.progress(index/len(jobs), text=f'Behandlet {index} af {len(jobs)}')
                if successful:
                    # Preserve data from prior fetches when a later batch is partial.
                    old_h=st.session_state.get('history',[])
                    old_f=st.session_state.get('fixtures',[])
                    hist=list({(r['date'],r['league'],r['home'],r['away']):r for r in old_h+hist}.values())
                    fixtures=list({(r['date'],r['league'],r['home'],r['away']):r for r in old_f+fixtures}.values())
                    st.session_state['history']=hist
                    st.session_state['fixtures']=fixtures
                    st.session_state['source_label']='football-data.org'
                st.session_state['api_fetch_report']={'successful':successful,'denied':denied,'errors':errors,'skipped':skipped}
                if not jobs:
                    st.info('Alle valgte ligaer/sæsoner er allerede indlæst i denne session.')
        report=st.session_state.get('api_fetch_report')
        if report:
            if report['successful'] or st.session_state.get('loaded_combos'):
                st.success('I hukommelsen: '+str(len(st.session_state.get('loaded_combos',{})))+' liga/sæson-kombinationer. '+str(len(st.session_state.get('history',[])))+' afsluttede og '+str(len(st.session_state.get('fixtures',[])))+' kommende kampe.')
                if report.get('skipped'):
                    st.caption(f'{report["skipped"]} allerede indlæste kombinationer blev sprunget over uden nyt API-kald.')
                with st.expander('Se præcis hvilke sæsoner der lykkedes'):
                    st.write('\n\n'.join(report['successful']) if report['successful'] else 'Ingen nye hentninger i sidste forsøg.')
            if report['denied']:
                st.warning('Ingen adgang (403), sprunget over: '+', '.join(report['denied']))
            if report['errors']:
                st.warning('\n\n'.join(report['errors']))
            st.caption('Et grønt antal betyder kun, at NOGLE data er hentet. Kontrollér dækningen før analyse.')
        if st.session_state.get('loaded_combos'):
            with st.expander('Samlet datadækning (alle hentninger i denne session)', expanded=True):
                coverage=sorted(st.session_state['loaded_combos'].values(), key=lambda x:(x['name'],x['season']))
                st.dataframe(pd.DataFrame(coverage).rename(columns={'name':'Liga','season':'Sæson','history':'Afsluttede','fixtures':'Kommende'}),hide_index=True,use_container_width=True)
                missing=[f'{n} {y}' for n in chosen for y in sorted(seasons) if f'{LEAGUES[n]}:{y}' not in st.session_state['loaded_combos']]
                if missing: st.warning('Mangler blandt aktuelle valg: '+', '.join(missing))
                else: st.success('Alle aktuelt valgte ligaer/sæsoner er indlæst.')
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

with st.expander('1b · Historiske statistikdata – datadækning',expanded=False):
    st.caption('Undersøg dine lokalt hentede CSV-filer fra Football-Data.co.uk. Understøtter E0, E1, SP1, I1, D1 og F1. Automatisk hentning er midlertidigt deaktiveret af hensyn til kildens begrænsninger. Ingen ændring af modelberegninger.')
    st.markdown('[Åbn Football-Data.co.uk sæsonfiler](https://www.football-data.co.uk/downloadm.php)')
    st.caption('Kildens fair-use-regler: kun personlig/akademisk brug og højst to lette automatiske hentninger om ugen. Brug ikke knappen hyppigere, heller ikke efter genstart.')
    st.warning('Automatisk hentning er midlertidigt slået fra. Streamlit-sessioner overlever ikke nødvendigvis genstart, og vi kan derfor endnu ikke håndhæve kildens ugentlige begrænsning sikkert. Tidligere hentninger kan ikke rekonstrueres.')
    st.caption('Brug filer, der allerede er hentet, indtil der er opsat et varigt, serveruafhængigt downloadregister og filarkiv.')
    historical_years=st.multiselect('Sæsoner til historiske statistikker (kun til visning)', [2024,2025,2026], default=[2025,2026], key='stats_seasons')
    st.button('Automatisk hentning afventer sikker lagring',disabled=True,key='fetch_six_stat_leagues')
    if st.session_state.get('auto_stat_coverage'):
        st.markdown('**Historiske data fra den aktuelle session**')
        summary=st.session_state['auto_stat_coverage']
        st.dataframe(pd.DataFrame(summary),hide_index=True,use_container_width=True)
        st.metric('Kampe i allerede indlæste CSV-filer',sum(r.get('Kampe',0) for r in summary if not r.get('Fejl')))
        st.caption('Seneste hentning i denne session: '+st.session_state.get('auto_stat_time','ukendt'))
        st.download_button('Download dækningsrapport (CSV)',to_csv(summary,list(dict.fromkeys(k for row in summary for k in row))),file_name='sig_statistik_daekning.csv',mime='text/csv')
    if st.session_state.get('auto_stat_errors'):
        st.warning('Tidligere hentefejl: '+'; '.join(st.session_state['auto_stat_errors']))

    audits=st.file_uploader('Vælg en eller flere historiske CSV-filer',type='csv',accept_multiple_files=True,key='audit_csv')
    if audits:
        table=audit_uploaded_files(audits)
        st.dataframe(pd.DataFrame(table),hide_index=True,use_container_width=True)
        good=[r for r in table if not r.get('Fejl') and r.get('Kampe',0)>0]
        st.metric('Kampe med læsbar ligakode',sum(r['Kampe'] for r in good))
        st.caption('Procenterne angiver udfyldte felter – ikke valideret datakvalitet. Bet365-kolonner vises kun som tilgængelighed; deres værdier bruges endnu ikke til anbefalinger.')
        if len({r['Liga'] for r in good})<6:
            st.warning('Ikke alle seks ligaer er repræsenteret i de uploadede filer.')
    else:
        st.info('Upload CSV-filer fra leverandøren for at få en reel dækningsrapport. Vi antager ikke, at manglende kolonner indeholder data.')

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
    st.markdown('**Aktuel form (forsøg)**')
    st.caption('Modstanderstyrkejusteret målforskel i de seneste fem kampe. Ingen xG, trænerstil eller opdigtede taktiske data. Standard er FRA, indtil uafhængig test dokumenterer en forbedring.')
    use_form=st.checkbox('Aktivér forsigtig formjustering (eksperimentel)',value=False)
    form_strength=0.16 if use_form else 0.0
    st.caption('Managerskift registreres kun, hvis du uploader dokumenterede datoer. Ingen automatisk managerdata.')
    manager_csv=st.file_uploader('Managerskift (valgfrit CSV: league,team,start_date)',type='csv',key='manager_csv')
    manager_changes=[]
    if manager_csv is not None:
        try:
            manager_changes=parse_upload(manager_csv,['league','team','start_date'])
            for x in manager_changes: dt.date.fromisoformat(x['start_date'][:10])
            st.caption(f'{len(manager_changes)} managerskift indlæst. Holdnavne skal matche kampdata nøjagtigt.')
        except Exception as exc:
            st.error(f'Ugyldigt managerskift-CSV: {exc}')
            manager_changes=[]
    st.download_button('Download managerskift-skabelon',to_csv([],['league','team','start_date']),'manager_changes_template.csv','text/csv')

hist=st.session_state.get('history',[])
fixtures=st.session_state.get('fixtures',[])
odds=st.session_state.get('odds',[])
if hist:
    try:
        eng=Engine(form_strength=form_strength,manager_changes=manager_changes)
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
        st.caption('Trænerstil og matchup-profiler er IKKE implementeret; kort, hjørnespark, Opta/xG og automatisk bookmakerintegration er IKKE implementeret i 3.6. Seks ligaer via API; Superliga via CSV.')
        st.subheader('5 · Historisk test')
        st.warning('Formjusteringen er IKKE valideret. Sammenlign på et uafhængigt tidsinterval, før den bruges til væddemål. Managerdata er kun brugerleverede.')
        st.caption('Kronologisk test: Modellen forudsiger hver kamp ud fra tidligere resultater, før den lærer kampens resultat. Brier og log-loss måler sandsynligheder, ikke gevinst.')
        st.caption('Lavere score er bedre. Sammenligningen er mod en simpel historisk liga-baseline, ikke mod bookmakerodds.')
        if st.button('Kør kronologisk backtest', key='run_backtest'):
            with st.spinner('Tester afsluttede kampe i datoorden…'):
                test_engine=Engine(form_strength=form_strength,manager_changes=manager_changes)
                back=load_history(test_engine,hist,cutoff=asof,backtest=True)
                st.session_state['backtest_results']=back
                saved,message=save_backtest_to_github(back,asof.isoformat(),form_strength)
                st.session_state['backtest_save_message']=(saved,message)
                st.session_state['backtest_signature']=(len(hist),asof.isoformat(),st.session_state.get('source_label',''),form_strength,tuple((r['league'],r['team'],r['start_date']) for r in manager_changes))
        back=st.session_state.get('backtest_results',[])
        if 'backtest_save_message' in st.session_state:
            saved,message=st.session_state['backtest_save_message']
            if saved:
                st.success(message)
                st.link_button('Se seneste backtest på GitHub','https://github.com/zigzag8800/SIG-Betting-Model/blob/main/reports/latest_backtest.csv')
            else:
                st.info(message)
        signature=(len(hist),asof.isoformat(),st.session_state.get('source_label',''),form_strength,tuple((r['league'],r['team'],r['start_date']) for r in manager_changes))
        if back and st.session_state.get('backtest_signature')!=signature:
            st.warning('Kampdata eller analysedato er ændret siden sidste test. Kør backtest igen for aktuelle resultater.')
        elif back:
            bdf=pd.DataFrame(back)
            st.metric('Historisk testede kampe',len(bdf))
            st.metric('Gennemsnitlig Brier-score',f'{bdf.brier.mean():.4f}')
            st.metric('Gennemsnitlig log-loss',f'{bdf.logloss.mean():.4f}')
            st.markdown('**Sammenligning med simpel liga-baseline**')
            comparison=pd.DataFrame([
                {'Metode':'SIG Model 3.6','Brier':bdf.brier.mean(),'Log-loss':bdf.logloss.mean()},
                {'Metode':'Historisk ligafordeling','Brier':bdf.baseline_brier.mean(),'Log-loss':bdf.baseline_logloss.mean()},
            ])
            st.dataframe(comparison.round(4),hide_index=True,use_container_width=True)
            brier_diff=bdf.baseline_brier.mean()-bdf.brier.mean()
            if brier_diff>0:
                st.success(f'Modellen har {brier_diff:.4f} lavere Brier-score end baseline på disse testkampe.')
            elif brier_diff<0:
                st.warning(f'Modellen har {-brier_diff:.4f} højere (dårligere) Brier-score end baseline på disse testkampe.')
            else:
                st.info('Modellen og baseline har samme gennemsnitlige Brier-score.')
            st.caption('Kun kampe hvor begge hold har mindst 5 tidligere registrerede kampe medregnes. Resultater fra samme kalenderdato holdes ude indtil dagens forudsigelser er lavet. Baseline bruger kun tidligere ligakampe. Ingen odds eller ROI.')
            per_league=(bdf.groupby('league',as_index=False)
                       .agg(kampe=('brier','size'),brier=('brier','mean'),logloss=('logloss','mean'),baseline_brier=('baseline_brier','mean'),baseline_logloss=('baseline_logloss','mean'))
                       .sort_values('league'))
            per_league['brier']=per_league['brier'].round(4)
            per_league['logloss']=per_league['logloss'].round(4)
            per_league['baseline_brier']=per_league['baseline_brier'].round(4)
            per_league['baseline_logloss']=per_league['baseline_logloss'].round(4)
            st.markdown('**Resultater fordelt på liga**')
            st.dataframe(per_league,hide_index=True,use_container_width=True)
            st.markdown('**Kalibrering af hjemmesejre**')
            st.caption('Hvis modellen siger 60–70 % hjemmesejr, bør omtrent 60–70 % af kampene i den gruppe faktisk ende med hjemmesejr. Små grupper er usikre.')
            bins=[0,.1,.2,.3,.4,.5,.6,.7,.8,.9,1.000001]
            calib=bdf.copy()
            calib['interval']=pd.cut(calib['p1'],bins=bins,labels=[f'{int(bins[i]*100)}–{int(bins[i+1]*100)} %' for i in range(10)],include_lowest=True,right=False)
            calib['hjemmesejr']=(calib['actual']=='1').astype(int)
            cal=(calib.groupby('interval',observed=True)
                 .agg(kampe=('hjemmesejr','size'),forudsagt=('p1','mean'),observeret=('hjemmesejr','mean'))
                 .reset_index())
            cal['forudsagt']=(cal['forudsagt']*100).round(1)
            cal['observeret']=(cal['observeret']*100).round(1)
            cal=cal.rename(columns={'interval':'Sandsynlighed','kampe':'Kampe','forudsagt':'Forudsagt %','observeret':'Faktisk %'})
            st.dataframe(cal,hide_index=True,use_container_width=True)
            st.download_button('Download historisk test (CSV)',to_csv(back,list(back[0])),'sig_backtest.csv','text/csv',key='download_backtest')
            st.warning('Vigtigt: Dette er intern historisk test på det samme datamiljø, som bruges til udvikling. Det er ikke en uafhængig fremadrettet validering eller dokumentation for profitable spil.')
        else:
            st.info('Tryk på knappen for at teste historikken. Flere afsluttede kampe giver et mere pålideligt grundlag.')
    except Exception as e: st.error(f'Analysefejl: {e}')
else:
    st.info('Start med at hente historiske kampe ovenfor. Intet er simuleret eller opdigtet.')

with st.expander('6 · Model-laboratorium 3.7 (eksperiment)',expanded=False):
    st.caption('Dette er en separat walk-forward-test: samtlige modeller forudsiger de samme kampe uden at kende samme dags resultater. Din normale model og top-30-liste ændres ikke.')
    lab_history=st.session_state.get('history',[])
    lab_cutoff=dt.date.today()
    if lab_history:
        first_day=min(dt.date.fromisoformat(r['date'][:10]) for r in lab_history)
        suggested=max(first_day+dt.timedelta(days=180),lab_cutoff-dt.timedelta(days=365))
        lab_start=st.date_input('Start på testperiode (tidligere kampe bruges kun som træning)',value=min(suggested,lab_cutoff-dt.timedelta(days=1)),min_value=first_day,max_value=lab_cutoff-dt.timedelta(days=1),key='lab_start')
        if st.button('Sammenlign seks modelvarianter',key='run_lab'):
            with st.spinner('Beregner sammenlignelige kronologiske prognoser…'):
                lab_rows=compare_variants(lab_history,lab_cutoff,lab_start)
                st.session_state['lab_rows']=lab_rows
                st.session_state['lab_signature']=(len(lab_history),lab_start.isoformat(),lab_cutoff.isoformat())
        lab_rows=st.session_state.get('lab_rows',[])
        if lab_rows:
            if st.session_state.get('lab_signature')!=(len(lab_history),lab_start.isoformat(),lab_cutoff.isoformat()):
                st.warning('Historik eller testperiode er ændret. Kør testen igen.')
            else:
                lab_df=pd.DataFrame(lab_rows)
                lab_summary=(lab_df.groupby('variant',as_index=False)
                             .agg(kampe=('brier','size'),brier=('brier','mean'),logloss=('logloss','mean'))
                             .sort_values('brier'))
                st.dataframe(lab_summary.round(4),hide_index=True,use_container_width=True)
                st.caption('Lavere Brier og log-loss er bedre. Dette er eksperimenter på en valgt periode, ikke en uafhængig fremtidig test. Justering efter testresultaterne kræver en ny urørt periode.')
                st.download_button('Download model-sammenligning',to_csv(lab_rows,list(lab_rows[0])),'sig_model_lab.csv','text/csv',key='lab_csv')
        else:
            st.info('Start testen for at se, om 5 eller 10 kampe og ændret Elo-vægt hjælper. Version 3.6 forbliver uændret.')
    else:
        st.info('Hent historiske kampresultater ovenfor, før du starter modeltesten.')

with st.expander('7 · Bookmaker-laboratorium 3.8', expanded=False):
    st.caption('Sammenligner SIG A og E med marginjusterede 1X2-odds på præcis de samme afsluttede kampe. Kampresultater og odds kommer fra samme CSV-kilde – ikke fra et usikkert holdnavne-match.')
    stored=st.session_state.get('historical_bookmaker_files',[])
    st.caption('Genbruger allerede hentede historiske statistikfiler fra sektion 1b. Du kan også uploade filer her. Undgå ekstra automatiske downloads af hensyn til kildens begrænsninger.')
    uploaded=st.file_uploader('Alternativt: CSV-filer med historiske odds',type='csv',accept_multiple_files=True,key='benchmark_files')
    selected=list(uploaded) if uploaded else stored
    closing_only=st.checkbox('Kun dokumenterede closing odds',value=True,key='benchmark_closing')
    if selected:
        st.success(f'{len(selected)} historiske filer klar til test.')
        if st.button('Sammenlign med bookmakerne',key='run_bookmaker_lab'):
            try:
                benchmark_matches,rejected=parse_historical_csv(selected)
                if not benchmark_matches:
                    st.error('Ingen færdigspillede kampe fundet i filerne.')
                else:
                    first=min(dt.date.fromisoformat(r['date']) for r in benchmark_matches)
                    last=max(dt.date.fromisoformat(r['date']) for r in benchmark_matches)
                    # Historical seasons can start with cold teams, so warm up at least 120 days.
                    test_start=first+dt.timedelta(days=120)
                    with st.spinner('Beregner sammenlignelige prognoser og fjerner bookmakerens margin…'):
                        results,excluded=compare_to_bookmaker(benchmark_matches,test_start,last+dt.timedelta(days=1),closing_only)
                    st.session_state['benchmark_result']=(results,excluded,rejected,len(benchmark_matches),test_start.isoformat(),closing_only)
            except Exception as exc:
                st.error(f'Bookmaker-testfejl: {exc}')
    else:
        st.info('Hent først historiske statistikker under sektion 1b. Så kan de bruges direkte her.')
    result=st.session_state.get('benchmark_result')
    if result:
        rows,excluded,rejected,total,start_date,was_closing=result
        st.caption(f'Datagrunlag: {total} historiske kampe, test fra {start_date}; {"kun closing" if was_closing else "closing eller opening"}. {rejected} ufuldstændige rækker frasorteret.')
        if not rows:
            st.warning('Ingen testkampe med gyldige odds og mindst fem forudgående kampe pr. hold. Prøv flere sæsoner, eller fravælg closing-only med tydeligt angivet lavere datakvalitet.')
        else:
            bdf=pd.DataFrame(rows)
            st.metric('Kamp-sammenligninger',int(len(bdf)/2))
            tab=(bdf.groupby('variant',as_index=False).agg(kampe=('brier','size'),brier=('brier','mean'),logloss=('logloss','mean'),bookmaker_brier=('market_brier','mean'),bookmaker_logloss=('market_logloss','mean')).round(4))
            st.dataframe(tab,hide_index=True,use_container_width=True)
            league=(bdf.groupby(['variant','league'],as_index=False).agg(kampe=('brier','size'),brier=('brier','mean'),bookmaker_brier=('market_brier','mean')).round(4))
            st.markdown('**Fordelt på liga**')
            st.dataframe(league,hide_index=True,use_container_width=True)
            st.download_button('Download sammenligningen (CSV)',to_csv(rows,list(rows[0])),'sig_vs_bookmakers.csv','text/csv',key='export_benchmark')
            st.caption('En bedre historisk Brier-score er ikke dokumentation for profit. Udvælgelse af model E efter tidligere test er ikke uafhængig validering. Odds fra forskellige udbydere sammenblandes ikke på den enkelte kamp.')
        if excluded['no_odds'] or excluded['opening_only']:
            st.caption(f'Sprunget over: {excluded["no_odds"]//2} kampe uden gyldige odds og {excluded["opening_only"]//2} kun med opening odds.')

st.divider()
st.caption('SIG Model · Kun analyse · Ingen automatiske spil · Opta, kort, hjørnespark og live bookmakerodds er endnu ikke integreret.')
