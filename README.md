# SIG Betting Model – Chrome på iPhone

Projektets fælles arbejdsregler findes i [PRINCIPLES.md](PRINCIPLES.md).
Se [den genberegnede historiske test](reports/backtest_recomputed_2026-10-24.md).
Se [den gennemførte 90-minutterskorrektion](reports/regular_time_correction_2026-10-24.md).
Se [kampstatusregler og fund om målvarighed](reports/match_lifecycle_2026-10-24.md).
Se [den faktiske datadækning og rettelser](reports/data_quality_2026-10-24.md).
Se også [researchloggen](RESEARCH_LOG.md) og [seneste vurdering af forudsætninger](reports/readiness_2026-10-24.md).

Denne pakke indeholder en mobilvenlig Streamlit-webapp og den eksisterende beregningsmotor (`sig_model.py`). Den kørende app findes på https://sig-betting-model.streamlit.app/ . Der kræves ikke installation på iPhone, men appen skal hostes på en server.

## Gratis opsætning via Streamlit Community Cloud

1. Opret eller brug en GitHub-konto på https://github.com/ .
2. Opret et **privat repository** og upload `app.py`, `sig_model.py` og `requirements.txt` i roden. Del ikke din API-nøgle i repository eller kode.
3. Gå til https://share.streamlit.io/ og log ind med GitHub. Vælg **Create app** og repository samt `app.py` som entry point. Kontrollér Streamlits aktuelle gratisplan og regler for private repositories.
4. Åbn appens HTTPS-adresse i **Chrome på iPhone**.
5. I appen kan du indtaste football-data.org API-nøglen i passwordfeltet. Den behandles af appens server i den aktuelle session og sendes til football-data.org; den bliver ikke skrevet til kildekode eller CSV-filer. For bedre drift kan nøglen gemmes i Streamlit-appens **Secrets** med navnet `FOOTBALL_DATA_API_KEY` (aldrig i GitHub). Vær opmærksom på, at den som driver hostingplatformen, har teknisk adgang til appens servermiljø.
6. Vælg **Premier League** og en eller to sæsoner. Tryk **Hent kampdata**. API'et kan begrænse adgang til ældre sæsoner eller bestemte ligaer. Tilføj flere ligaer senere.
7. Upload valgfrit `odds.csv` med kolonnerne `date,league,home,away,market,odds,bookmaker,captured_at` for odds du lovligt har indsamlet. Holdnavne og kampdato skal matche API-data præcist.
8. Brug kandidatlisten og backtest. Ingen spil bliver placeret.

## Begrænsninger

- Gratis API-data giver normalt kampresultater, ikke Opta/xG, hjørnespark, kort eller dommerhistorik.
- Superligaen skal indlæses via CSV, indtil der er etableret en tilladt datakilde.
- Der er **ingen automatisk forbindelse til Bet365, Unibet eller Betfair**. Ingen Betfair-installation er nødvendig.
- `sig_model.py` er en eksperimentel Elo/målmodel med Dixon-Coles-korrektion. Minimumsodds bruger en **heuristisk** usikkerhedsmargin, ikke validerede konfidensintervaller. Profitabilitet er ikke dokumenteret.
- API-kald kan blive begrænset på gratisplanen; begynd med én liga.
- Gratis hosting kan sove eller have ressourcebegrænsninger.
- Det permanente PostgreSQL-arkiv kræver adgangskontrol via `SIG_OWNER_PASSWORD`; gem adgangsoplysninger i Streamlit Secrets.

## Lokalt test (valgfrit, ikke på iPhone)

```bash
pip install -r requirements.txt
streamlit run app.py
```
