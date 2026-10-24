# Faktisk SIG-datadækning og rettelser – 24. oktober 2026

**Efterfølgende fund:** [kontrollen af målvarighed](match_lifecycle_2026-10-24.md) identificerede én Championship-kamp med ekstra tid. Gyldige måltal nedenfor betyder numerisk gyldige, ikke at alle er dokumenteret som 90-minutters resultater.

## Konklusion og afgrænsning

PostgreSQL indeholder et brugbart, men begrænset ligaarkiv. Den aktive historik
har 2.792 afsluttede kampe med gyldige målresultater og 1.819 kommende kampe.
Top 5 står for 2.102 af de afsluttede kampe. Kun startårene 2025 og 2026 er
verificeret i den normaliserede liga-/API-historik.

Den oprindelige dækningsrapport viste kun sessionsdata. Den nye undersøgelse
læser `sig_archive` i én read-only repeatable-read-transaktion. Aktuelt workspace,
API-cache, rå CSV'er, den gemte ZIP og alle workspaceversioner opgøres separat.
Dette er en audit af projektets `sig_archive`, ikke en påstand om kontrol af enhver
relation, backup eller ekstern konto i PostgreSQL. Versioner og kildekopier må ikke
lægges sammen som ekstra unikke kampe.

Den eksporterede liveundersøgelse er vedlagt uændret i indhold som
[JSON](postgres_audit_2026-10-24.json), med
[dækning pr. scope/liga/sæson som CSV](postgres_coverage_2026-10-24.csv) og
[alle ZIP-medlemmer som CSV](archive_members_2026-10-24.csv).
`generated_at` i JSON er selve databaseobservationens UTC-tidspunkt.

## 1. Kodeversion, tests og livekontrol

- HEAD før arbejdsblokken: `c9da543` (principper og forudsætninger).
- Kodeændring `db1e104`: alle gemte ZIP-divisioner auditeres; atomisk import;
  Streamlit-regressionstests og installation af testafhængigheder i CI.
- Seneste kodecommit: `44691173112adac3c16d6168d7171bb59be966b8`.
- [SIG regression checks #59](https://github.com/zigzag8800/SIG-Betting-Model/actions/runs/40088311246)
  er afsluttet med success på præcis denne commit. Jobloggen viser **82 tests, OK**,
  herunder fire Streamlit AppTest-tests; ingen tests blev sprunget over.
- Lokalt: compileall, 82 unit-/AppTest-tests og git diff --check består.
  Testmiljø: Python 3.12, Streamlit 1.66.1, pandas 2.3.3, psycopg 3.3.6.
  CI bruger Python 3.11 og installerer projektets krav før suitekørslen.
- Live: den adgangsbeskyttede Streamlit-app kørte den nye PostgreSQL/ZIP-kontrol,
  viste 22 medlemmer, alle behandlet, og eksporterede rapporten med de nye felter.
  Databaseobservationen bekræftede de tidligere genskabte metadata fra en separat
  læsetransaktion. Ingen nye leverandørdata blev hentet.
- Produktionsmotoren `sig_model.py`, SIG E og angreb/forsvar-modellens
  sandsynlighedsberegninger er ikke ændret.

## 2. Faktisk normaliseret dækning

Alle afsluttede tal nedenfor har gyldige heltallige, ikke-negative målresultater.
Kampposter inkluderer kommende kampe; de er ikke ekstra historiske observationer.

| Liga | Sæson | Aktive afsluttede | Aktive kommende | Aktive poster | Poster i API-cache |
|---|---|---:|---:|---:|---:|
| Premier League | 2025/26 | 380 | 0 | 380 | 380 |
| Premier League | 2026/27 | 71 | 309 | 380 | 380 |
| La Liga | 2025/26 | 380 | 0 | 380 | 380 |
| La Liga | 2026/27 | 90 | 289 | 379 | 380 |
| Serie A | 2025/26 | 380 | 0 | 380 | 380 |
| Serie A | 2026/27 | 71 | 309 | 380 | 380 |
| Bundesliga | 2025/26 | 306 | 0 | 306 | 306 |
| Bundesliga | 2026/27 | 55 | 251 | 306 | 306 |
| Ligue 1 | 2025/26 | 305 | 0 | 305 | 306 |
| Ligue 1 | 2026/27 | 64 | 242 | 306 | 306 |
| Championship, bevaret | 2025/26 | 557 | 0 | 557 | 557 |
| Championship, bevaret | 2026/27 | 133 | 419 | 552 | 552 |
| **I alt** | | **2.792** | **1.819** | **4.611** | **4.613** |

Championship 2025/26 er i API-svaret eksplicit opdelt i **552 REGULAR_SEASON** og
**5 PLAYOFFS**. Forskellen til rå CSV'ens 552 er derfor dokumenteret i dataenes
stage-felt, ikke udledt alene af datoer eller forventninger.

### Forventede kamptal og faktiske mangler

For Top 5 indeholder den gemte 2025/26-CSV 20 hold og 380 forskellige hjemme/ude-par
for PL/PD/SA, og 18 hold og 306 forskellige par for BL1/FL1. Det svarer præcist til
n(n−1) pladser i et dobbelt alle-mod-alle-program. Der er ingen gentagne dato/hold-nøgler
eller modstridende mål i de fem råfiler. Dette beviser den kombinatoriske dækning,
ikke at hver sportslig hændelse eller administrativ afgørelse er korrekt.

Top 5-referenceomfanget er **1.752 poster pr. sæson**. Den aktive 2025/26-historik
har 1.751 afsluttede kampe; API-cachen indeholder også den ene AWARDED-post.
For 2026/27 er 351 Top 5-kampe afsluttet og 1.400 kommende. Den sidste referencepost
er CANCELLED i cachen. Kommende kampe er ikke manglende historiske resultater.
Ingen procentvis historikdækning for endnu ikke spillede kampe påstås.

De to særstatusser er:

| Kilde | Kamp-ID | Dato | Kamp | Status | Håndtering |
|---|---|---|---|---|---|
| football-data.org, FL1 2025 | 542704 | 2026-05-17 | FC Nantes – Toulouse FC | AWARDED | Bevaret i cache; ikke gjort til spillet træningskamp |
| football-data.org, PD 2026 | 564698 | 2026-10-10 | Rayo Vallecano de Madrid – Athletic Club | CANCELLED | Bevaret i cache; ikke aktiv kommende kamp |

Dette er verificerede statusser i det gemte leverandørsvar. Den sportslige årsag
og en korrekt træningspolitik for administrative afgørelser er ikke uafhængigt
undersøgt. Kildernes forskellige resultatrepræsentationer er ikke automatisk sammenlagt.

## 3. ID'er, tider, dubletter og sporbarhed

Efter den tidligere metadatarekonstruktion og ved den aktuelle kontrol:

| Kontrol, aktivt workspace | Antal problemrækker/-grupper |
|---|---:|
| Manglende kamp-ID | 0 |
| Manglende hjemme-/udehold-ID | 0 |
| Manglende eller ugyldigt UTC-kickoff | 0 |
| Ugyldig dato / dato afviger fra UTC-kickoff | 0 / 0 |
| Manglende datakilde | 0 |
| Dubleret kilde-kamp-ID inden for liga/sæson | 0 |
| Dubleret dato/hold-nøgle inden for liga/sæson | 0 |
| Modstridende ID-/dato/hold-resultater inden for liga/sæson | 0 |
| Manglende historisk known_at | **4.611** |

Kontrollerne er grupperet pr. scope, liga og sæson. De er ikke en global
entity-resolution eller dokumentation for navnesammenfald mellem forskellige
leverandører. Rå CSV'er har ingen verificerede fælles kamp-/hold-ID'er eller
UTC-konvertering i denne audit. Deres `Time` må ikke ukritisk kaldes UTC.

2.792 historiske og 1.819 kommende rækker fik tidligere metadata genoprettet fra
allerede arkiverede API-svar med entydig liga/dato/hold-kobling og ens mål for
historiske kampe. Ingen resultater, holdnavne eller datoer blev ændret.
Ældre workspaceversioner blev ikke skrevet om; de dokumenterer den gamle tilstand.

**Begrænsning:** `known_at` kan ikke genskabes fra kickoff, lastUpdated eller vores
indlæsningstid. En kronologisk replay er derfor ikke i sig selv en dokumenteret
historisk point-in-time-reproduktion af alle oplysninger.

## 4. Hvad der faktisk ligger i PostgreSQL

Observeret i `sig_archive`:

| Kategori | Arkivposter | Fortolkning |
|---|---:|---|
| api_matches | 12 | Seks ligaer × to startår |
| workspace | 1 | Aktuel aktiv tilstand |
| workspace_version | 9 | Historiske versioner, ikke ni nye datasæt |
| source_csv | 6 | Udvalgte divisioner, hver med korrekt SHA-256-kontrol |
| provider_bundle | 1 | Original samlet 2025/26-ZIP |
| imported_backtest | 1 | Tidligere testresultater, ikke rå træningskampe |
| diagnostic | 2 | Kontrolposter |

Den oprindelige ZIP har **22 CSV-medlemmer, 7.647 rækker, 7.646 gyldige målresultater**.
Alle medlemmer er gennemlæst i hukommelsen, uden udpakning til filsystem og uden
nye leverandørkald. Ingen medlemmer blev sprunget over eller fejlede teknisk audit.
At en fil er behandlet betyder ikke, at alle dens rækker er modelklare.

| ZIP-fil | Division | Rækker | Gyldige mål |
|---|---|---:|---:|
| E0 | Premier League | 380 | 380 |
| E1 | Championship | 552 | 552 |
| E2 | England, League One | 552 | 552 |
| E3 | England, League Two | 552 | 552 |
| EC | England, National League | 552 | 552 |
| D1 | Bundesliga | 306 | 306 |
| D2 | 2. Bundesliga | 306 | 306 |
| F1 | Ligue 1 | 306 | 306 |
| F2 | Ligue 2 | 306 | **305** |
| I1 | Serie A | 380 | 380 |
| I2 | Serie B | 380 | 380 |
| SP1 | La Liga | 380 | 380 |
| SP2 | Segunda División | 462 | 462 |
| N1 | Nederlandene | 306 | 306 |
| P1 | Portugal | 306 | 306 |
| T1 | Tyrkiet | 306 | 306 |
| B1 | Belgien | 311 | 311 |
| G1 | Grækenland | 236 | 236 |
| SC0 | Skotland, øverste division | 228 | 228 |
| SC1 | Skotland, Championship | 180 | 180 |
| SC2 | Skotland, League One | 180 | 180 |
| SC3 | Skotland, League Two | 180 | 180 |

Fejlrækken er **F2.csv, linje 137: Bastia – Red Star, 2025-12-05**. Begge mål er
blanke. Rækken og originalfilen er bevaret. Filen er ikke blandt de seks udvalgte
modelfiler, så den ugyldige række er ikke føjet til modellen. Der er ingen
modsætninger mellem gyldige FTHG/FTAG-resultater og udfyldte FTR-koder i ZIP-auditten.

De seks udvalgte råfiler har 2.304 rækker, hvoraf Top 5 udgør 1.752. ZIP'ens 16
øvrige divisioner har 5.343 rækker. De er allerede gemt, men er ikke automatisk
indlæst, identitetsknyttet eller valideret til SIG 4.0. De udgør ikke ekstra sæsoner.
Råfilnavnet angiver 2025/26; audit gætter ikke en sæsonværdi i de enkelte CSV-rækker.

## 5. Europæiske turneringer, pokaler, landskampe og spillere

CL, EL, UCL, FAC, FLC, DFB, CDR, EC, WC og QUFA har **nul poster** i det aktuelle
forskningsarkiv, i de ni historiske workspaceversioner og i de 12 API-cacheposter.
Ingen af de 22 ZIP-filer er disse ekstra turneringer. ZIP-divisionen `EC` er den
engelske National League, mens research-koden `EC` betyder EM. Koder må derfor
altid fortolkes sammen med datakilde og turneringsnavn, aldrig slås sammen blindt.

Der er ikke grundlag for en procent af forventet dækning for ekstra turneringer,
fordi relevante sæsoner, kvalifikationsrunder og forventet kampliste endnu ikke er
fastlagt. Nul indlæste rækker må ikke forveksles med nul faktisk belastning.
Der er heller ikke verificeret spiller-/minut-/klubhistorik til belastningsmodellering.

## 6. Gennemførte fejlrettelser

1. Tidligere rettelse genoprettede tabte metadata fra cache og bevarer immutable
   snapshots. Den oprindelige årsag var normalisering uden identitetsfelter samt
   importer, der kunne erstatte hele rækker med sparsomme poster.
2. API-konvertering bevarer nu sæson fra selve matchobjektet eller det konkrete
   importjob; det er ikke et gæt fra kampens kalenderår.
3. Historik, fixtures og loaded_combos opdateres samlet efter konfliktfri merge.
   Ved score- eller metadatakonflikt forbliver de eksisterende kamplister urørte,
   og konflikten vises. API-råsvaret er fortsat arkiveret til senere vurdering.
4. Ekstra CSV-merges beregnes begge før sessionstilstanden opdateres.
5. API- og forskningsimport afviser boolske, negative og ikke-heltallige mål før
   int-konvertering. Eksempel: 1,5 mål må ikke lydløst blive til 1 mål.
6. Audit dækker nu alle ZIP-medlemmer, kildechecksums, ugyldige resultatlinjer,
   FTR-konflikter, dato/kickoff-konsistens og dokumenterede turneringsstadier.
7. CI installerer afhængigheder, så AppTest faktisk køres frem for at blive skippet.

Konservative metadatakonflikter, fx et ændret kickoff på en allerede kendt kamp,
kræver stadig særskilt gennemgang. Automatisk politik for rescheduling, rettede
slutresultater og historiske versionsintervaller er ikke løst af denne rettelse.
Ingen data er slettet eller nulstillet. Ingen ny model eller tidlig-oddsfunktion er bygget.

## 7. Kilder og næste beslutning

Primærkilder for felt-/statusfortolkning og teknisk metode:

- [football-data.org v4 Match](https://docs.football-data.org/general/v4/match.html).
- [Football-Data.co.uk arkivbeskrivelse](https://football-data.co.uk/downloadm.php).
- [PostgreSQL SET TRANSACTION](https://www.postgresql.org/docs/current/sql-set-transaction.html).
- [Python 3.11 zipfile](https://docs.python.org/3.11/library/zipfile.html).

Forumspor og metodekilder med deres faktiske gennemgang og begrænsninger står i
[RESEARCH_LOG.md](../RESEARCH_LOG.md). De forklarer risici og undersøgelsesspørgsmål;
de bruges ikke som bevis for vores konkrete databasetal. Den direkte notes.txt-
reference returnerede HTTP 429 under research; ingen genforsøg blev foretaget.

**Næste arbejdsblok:** definér en fælles kampidentitet med kildenavnerum,
statushistorik og eksplicit konflikt-/rescheduling-politik. Test den på syntetiske
og allerede gemte data. Fastlæg dernæst et afgrænset datakrav og en kvotebevidst
plan for ekstra turneringer, før der bedes om nye downloads. Uafhængig modeltest
kræver en på forhånd fastlagt og endnu ikke brugt testperiode.
