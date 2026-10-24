# Genberegnet historisk test efter 90-minutters rettelse

## Resultat

Den historiske SIG 3.6-test er genberegnet på de rettede data og gemt i PostgreSQL.
Begge versioner omfatter præcis **2.398 identiske testkampe**. Den tidligere
arkiverede test blev reproduceret med samme indstillinger før sammenligningen.
Der er ikke hentet nye leverandørdata eller ændret modelalgoritme.

| Måling, lavere er bedre | Før rettelse | Efter rettelse | Efter minus før |
|---|---:|---:|---:|
| SIG Brier | 0,2065501293 | 0,2066035893 | +0,0000534601 |
| SIG log-loss | 1,0319549637 | 1,0321791123 | +0,0002241486 |
| Simpel liga-baseline Brier | 0,2183068505 | 0,2183481265 | +0,0000412760 |
| Simpel liga-baseline log-loss | 1,0817055697 | 1,0818924163 | +0,0001868465 |

Rettelsen giver en lille forværring i den målte score. Resultater er rapporteret
uanset retningen. Der er ikke optimeret parametre på den ændrede test, og der
fremsættes ingen påstand om statistisk signifikant forskel eller profit.
Dette er en korrigeret **intern test**, ikke ny uafhængig validering eller et nyt
bookmakerbenchmark. Den simple liga-baseline er ikke bookmakerodds.

## Kontrolleret sammenligning

Appen gennemfører nu genberegningen således:

1. Læs den bevarede workspaceversion fra før datakorrektionen.
2. Kør gammel og rettet historik med den samme uændrede SIG-motor og samme indstillinger.
3. Kontrollér, om den gamle genkørsel matcher den oprindeligt gemte test.
4. Sammenlign kamp for kamp og gem ny test og sammenligningsrapport i workspace.

Ved den faktiske kørsel var alle følgende kontroller opfyldt:

- Samme indstillinger som den tidligere test: **ja**.
- Tidligere test reproduceret: **ja**, samme kampnøgler/udfald; sandsynligheder og
  scoremål stemmer inden for 1e-12.
- Samme sæt testkampe: **ja**, 2.398 par, ingen tilføjede/fjernede testkampe.
- Samme sæt inputkampe: **ja**, ingen tilføjede/fjernede inputkampe.
- Ændret inputresultat: **én kamp**, Southampton–Middlesbrough den 12. maj 2026,
  2–1 efter ekstra tid erstattet af 0–0 efter 90 minutter i modelinputtet.
- Prognoser for selve den rettede kamp: uændrede. Kun udfaldet skifter fra 1 til X.
  Resultatet anvendes først efter dagens prognoser, i overensstemmelse med den
  eksisterende kronologiske motor.
- **96 senere kampes modelprognoser ændres**, alle i Championship.
- **108 testrækker ændres**, når udfald, modelscore og liga-baseline medregnes.
  De ekstra 11 rækker har alene ændret baseline; deres modelprognoser er uændrede.
- Top 5-ligaernes testresultater er uændrede.

Modellen lærer af tidligere mål og resultater. En rettet kamp kan derfor ændre
senere Championship-prognoser via holdhistorik og Elo. Liga-baselinens fordeling
ændres også. Dette forklarer, hvorfor mere end én testrække påvirkes af én datakorrektion.

## Indstillinger og reproducerbarhed

- Analysedato: **24. oktober 2026**. Kun kampe før denne dato anvendes.
- Formjustering: **fra**, form_strength=0.0.
- Managerskift: **ingen**.
- Datakildelabel: football-data.org.
- Produktionsmotorens standardparametre er uændrede. Testen kræver mindst fem
  tidligere registrerede kampe pr. hold og lærer først efter alle prognoser på samme dato.
  Kandidatlistens bruger-slider er ikke backtestens min. historikgrænse.
- Brier er gennemsnittet af de tre kvadrerede sandsynlighedsfejl, dvs. summen divideret
  med tre. Log-loss anvender naturlig logaritme.
- SIG-motorens SHA-256: `5fd1a735801a2330d6d704862da1fab6788c4f5ecdf3387b6591e52213fcd915`.
- Historikkernes hashes, præcise tal, ændrede kampe og ligaopdeling er gemt i JSON-rapporten.

## Resultater pr. liga

| Liga | Kampe | Brier før | Brier efter | Log-loss før | Log-loss efter |
|---|---:|---:|---:|---:|---:|
| Bundesliga | 302 | 0,197617 | 0,197617 | 0,996322 | 0,996322 |
| Championship | 603 | 0,213297 | 0,213510 | 1,059725 | 1,060617 |
| Ligue 1 | 314 | 0,207942 | 0,207942 | 1,037025 | 1,037025 |
| La Liga | 405 | 0,200399 | 0,200399 | 1,006970 | 1,006970 |
| Premier League | 387 | 0,209755 | 0,209755 | 1,045107 | 1,045107 |
| Serie A | 387 | 0,205111 | 0,205111 | 1,025373 | 1,025373 |

## Faktisk verifikation

- Udgangspunkt i GitHub: `9151b737fc58437c7cf953f9687ba02b6c1ac34f`.
- Ny kodecommit: **e00b077028f1d134b832554e5b9d6f5141d75ca2**.
- Lokalt: compileall, **123 tests** og diff-kontrol bestået. Ingen ændring i sig_model.py.
- [GitHub Actions #64](https://github.com/zigzag8800/SIG-Betting-Model/actions/runs/40096120270)
  er grøn på præcis denne kodecommit. Jobloggen viser **123 tests, OK**.
- Testene omfatter identisk replay, ét ændret input, uændrede øvrige ligaer og
  tidligere datoer, forskellige indstillinger, fejlagtig gammel test, dubletafvisning
  og AppTest af genberegning/læsning/gemning uden leverandør-HTTP.
- Live: Kør kronologisk backtest blev anvendt med ovenstående indstillinger.
  Rapport og CSV blev downloadet fra appen.
- PostgreSQL blev derefter læst i en ny read-only transaktion. Den gemte
  backtest_revision er identisk med rapporten eksporteret fra UI.
- Databasen har nu **11 workspaceversioner**, tidligere 10. Backtesten er gemt;
  førversioner og 2–1-originalen er fortsat bevaret og kontrolleret.
- Korrektionens tre arkivchecks er fortsat true: gammel workspace findes,
  originalrækken er bevaret, og den aktive 0–0-række matcher korrektionsjournalen.

Dokumentation:

- [Fuld før/efter-rapport med ændrede kampe](backtest_revision_2026-10-24.json).
- [Ny backtest, 2.398 rækker som CSV](backtest_corrected_2026-10-24.csv).
- [Bevis for separat læsning af permanent lagring](backtest_persistence_2026-10-24.json).
- [Den gennemførte datakorrektion](regular_time_correction_2026-10-24.md).

## Begrænsning og næste skridt

Manglende historisk known_at og manglende ekstra turneringsdata er uændrede
begrænsninger. Det tidligere 1.437-kamps bookmakerbenchmark er ikke genberegnet;
dets CSV-data omfatter ikke den korrigerede playoffkamp. Der er ikke målt en ny
uafhængig forbedring mod bookmakerne.

Næste afgrænsede opgave er at bevare rå API-svar som versionshistorik før kommende
refresh. Den eksisterende cache kan ellers overskrive et tidligere råsvar under
samme nøgle. Dette skal løses i den eksisterende arkitektur før nye turneringshentninger.
