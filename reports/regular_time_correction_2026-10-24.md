# Gennemført 90-minutters rettelse – 24. oktober 2026

## Resultat

Southampton FC – Middlesbrough FC, 12. maj 2026, er nu gemt med **0–0** som
90-minuttersresultat i den aktive Championship-historik. Kampens oprindelige
**2–1 efter forlænget spilletid** er bevaret særskilt. Kilde: football-data.org,
match_id 557838. Der er ikke hentet nye leverandørdata.

Det er brugerens godkendte 90-minutters datakontrakt og leverandørens allerede
arkiverede regularTime-felter, der ligger til grund; ingen ny sportslig hændelse
eller uafhængig resultatleverandør er slået op. Rettelsestidspunktet er en faktisk
nutidig korrektionstid, aldrig et opdigtet historisk known_at.

## Verificeret i PostgreSQL efter gemning

Den efterfølgende audit læste databasen i en ny, read-only transaktion:

| Kontrol | Resultat |
|---|---|
| Aktivt resultat | 0–0 |
| Gemte oprindelige fullTime-mål | 2–1 |
| Kildens duration | EXTRA_TIME |
| Kildens regularTime | 0–0 |
| Originalrække bevaret i tidligere workspaceversion | Ja; eksakt række kontrolleret |
| Aktuel række stemmer med korrektionsjournal | Ja |
| Tidligere workspace findes | Ja |
| Workspaceversioner | 10, tidligere 9 |
| Gemte historiske backtest-resultater | Bevarede, markeret stale |
| Model-laboratoriets gemte resultater i aktuel snapshot | Ingen; invalidation aktiveres hvis de findes |
| Kontrol efter rettelsen | 4.610 unchanged, 1 verified_regular_time, 2 administrative_record |

Korrektionen blev gemt 24. oktober 2026 kl. **13.40 dansk tid** (11:40:54 UTC).
Rå API-cache og kildefiler er ikke ændret. Den førhen aktive 2–1-række er både
bevaret i korrektionsjournalen og verificeret i den tidligere workspaceversion.
[Maskinlæsbar dokumentation](regular_time_correction_2026-10-24.json) indeholder
før/efter-række, kildebevis, versionsreference, kontrolresultater og hash af den
fulde eksporterede liveaudit.

## Hvad koden gør

- Kræver præcis én historikrække og én kildeobservation med samme kilde/kamp-ID,
  hold-ID'er, liga, sæson, dato, holdnavne og kickoff.
- Kræver FINISHED, eksplicit EXTRA_TIME/PENALTY_SHOOTOUT, gyldige regularTime-mål
  og at den aktuelle originalscore stadig matcher kildebevisets fullTime.
- Bevarer originalscore som provider_full_time_home_goals/away_goals, regularTime,
  score_duration og et hash af kildebeviset. Den aktive prognoserække bruger 0–0.
- Tilføjer data_corrections til det eksisterende workspace, med før/efter,
  begrundelse og kildebevis. Ingen separat ny databasearkitektur.
- Gemmer med den eksisterende optimistiske workspace-lås. Hvis en anden session
  har ændret arkivet, afvises rettelsen uden at ændre sessionens historie.
- Opdaterer først sessionen efter en vellykket databasecommit. Gentagelse med
  samme bevis er en no-op og skaber ingen ekstra korrektion.
- Bevarer gamle backtest-/lab-arrays, men markerer deres signaturer som forældede.
  UI viser dem ikke som aktuelle. Aktuelt fandtes kun gemt historisk backtest.
- Backtest- og model-lab-signaturer bruger nu historikkens indholdshash frem for
  kun antallet af kampe. En målændring uden ændret rækketal opdages dermed.
- Fremtidig API-import bruger regularTime ved eksplicit ekstra tid/straffespark og
  bevarer fullTime særskilt. Manglende gyldigt regularTime afvises i disse tilfælde.
- Lifecycle-kontrollen genkender en gemt og dokumenteret 90-minutterskorrektion
  uden igen at foreslå 2–1 som slutresultat for 1X2.

## Test og livebevis

- Kodecommit ved selve rettelsen: 609e87a.
- Seneste kodecommit med selvstændig arkivkontrol: **85547d14c7dc03c5751b0dc1112a8b6df175ddf3**.
- [GitHub Actions #63](https://github.com/zigzag8800/SIG-Betting-Model/actions/runs/40091012417)
  er grøn på denne commit. Joblog viser **117 tests, OK**, herunder otte AppTest-flows.
- Lokalt: compileall, 117 tests og diff-kontrol består.
- Tests dækker bl.a. præcis korrektion, bevaret original, bevarede men forældede
  testresultater, gentagelse, identitets-/kildekonflikt, ændret workspace, afvist
  databaseskrivning uden sessionsmutation, fremtidig import og kontrol af gammel version.
- Live: rettelsesknappen anvendt én gang. Derefter kørt ny PostgreSQL-audit og
  eksporteret dens resultat. Kontrollens tre versions-/rækkecheck er alle true.
- Ingen modelalgoritme er ændret. Ingen ny backtest er kørt som led i denne blok.
  Den tidligere backtest må ikke bruges som et aktuelt resultat efter dataændringen.

## Afgrænsning og næste trin

Rettelsen vedrører Championship, som ikke indgår i SIG 4.0's Top 5-forsøg. Det
historiske bookmakerbenchmark anvender ordinære E1-CSV-kampe, ikke denne playoffkamp;
dets rådata er uændrede. Fremtidige versioner af samme kildedata kan stadig kræve
ny gennemgang, fx hvis kildens identitet eller regularTime bliver korrigeret.

Næste trin er at genberegne den berørte interne historiske test på den rettede
historik, med samme indstillinger, uden leverandørdownloads. En sådan genberegning
er en korrigeret intern test og ikke ny uafhængig evidens for modelpræcision.
Versionsbevaring af rå API-svar før kommende refresh er fortsat et særskilt restpunkt.
