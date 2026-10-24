# Kampstatus, flytninger og resultatkorrektioner – 24. oktober 2026

## Leveret og testet

Ny kontrol i SIG 4.0-afsnittet under PostgreSQL-audit sammenligner allerede gemt
API-cache med aktivt workspace. Den bruger kilde + match_id som identitet; dato
og holdnavne er oplysninger om kampen, ikke dens permanente nøgle. Kontrollen er
read-only og anvender ingen forslag. Resultaterne kan downloades som JSON.

Importens eksisterende merge er desuden sikret mod at indsætte samme kilde-ID
under en anden dato/hold-nøgle, og mod at nedgradere et afsluttet resultat til en
ikke-afsluttet status. En sådan import afvises med synlig konflikt og bevarer
kamplisterne. Flytninger bliver endnu ikke automatisk godkendt eller materialiseret.

- Udgangspunkt: HEAD `cebf229`.
- Nyeste kode: `98eeb8f5c9ecca4d6001da6418aa83d9d2b949a7`.
- [GitHub Actions #61](https://github.com/zigzag8800/SIG-Betting-Model/actions/runs/40089412304)
  er grøn. Jobloggen viser **105 tests, OK**, inklusive seks AppTest-flows.
- Lokalt: compileall, de samme 105 tests samt diff-kontrol består.
- Live: ny audit og eksport kørt med eksisterende PostgreSQL-cache. Advarsel om
  scorevarighed og detaljer om mål efter 90 minutter blev observeret i appen.
- Ingen ny leverandørhentning, datakorrektion, sletning eller modelændring udført.

## Faktisk fund i eksisterende data

| Klassifikation | Antal |
|---|---:|
| Samme fodboldtilstand som aktiv historik/kampprogram | 4.610 |
| Administrative poster uden aktiv modpart | 2 |
| Målgrundlag kræver gennemgang | 1 |
| Aktiv post mangler i de undersøgte cache-svar | 0 |

Der blev sammenlignet 4.611 aktive poster med 4.613 gemte observationer.
Der var ingen konkurrerende ID-versioner i dette aktuelle sammenligningsgrundlag.
Det beviser ikke, at der aldrig har været flytninger eller korrektioner; tidligere
råsvar er ikke et komplet append-only hændelsesarkiv.

De to administrative poster er de tidligere dokumenterede AWARDED/CANCELLED-rækker.
Detaljer og hash af den eksporterede live-rapport findes i
[lifecycle_review_2026-10-24.json](lifecycle_review_2026-10-24.json).

### Ny, væsentlig datakvalitetsbegrænsning

Kilde `football-data.org`, match_id **557838**, Championship 2025/26:

- Southampton FC – Middlesbrough FC, kickoff 2026-05-12 19:00 UTC.
- Status FINISHED; leverandørens score/duration er **EXTRA_TIME**.
- Gemte fullTime-mål og aktive home_goals/away_goals: **2–1**.
- Gemte regularTime-mål: **0–0**.

Dette er et direkte fund i eksisterende leverandørfelter, ikke en uafhængig
verifikation af kampens sportslige forløb. Feltdefinitionen er dog dokumenteret:
fullTime kan være et resultat efter forlænget spilletid. Derfor er den aktive
2–1-række ikke et dokumenteret korrekt 90-minutters målgrundlag.

Rækken er **ikke rettet** og findes fortsat i Championship-historikken. Tidligere
validering af heltallige mål var en syntaktisk kontrol, ikke kontrol af varighed.
En historisk test med denne række skal derfor genvurderes før en 90-minutters
præcisionspåstand. Senere Championship-form/Elo kan også være påvirket.
Top 5-forsøget filtrerer ELC fra. Det eksisterende bookmakerbenchmark bruger E1's
ordinære 552 kampe og ikke denne playoffkamp; der er ikke beregnet et nyt benchmark.

## Præcisering af 1X2-markedet

Brugeren præciserede, at 90-minuttersresultatet er det relevante 1X2-grundlag.
Det betyder normal spilletid plus dommerens tillægstid, uden ekstra tid eller
straffespark. Både opening og closing 1X2 skal sammenlignes med samme udfald.
Pristidspunkt er ikke markedsvarighed. Vinder af opgøret/går videre er særskilte
markeder. Leverandørens regularTime 0–0 er derfor korrekt kandidat til den
konkrete 1X2-række; den aktive 2–1-række er endnu ikke ændret. William Hills
officielle Match Betting-afsnit bekræfter skellet for deres ordinære 1X2-marked.

## Besluttede regler

| Situation | Håndtering i den nye kontrol |
|---|---|
| Samme kilde-ID, samme fodboldtilstand | Uændret; gentagen observation giver ingen dublet |
| Samme ID, dokumenteret nyere kickoff | Forslag til flytning; ingen ekstra kamp; ingen automatisk anvendelse |
| POSTPONED/SUSPENDED | Bevar observation; må ikke behandles som spillet resultat eller aktivt klart kandidatprogram |
| CANCELLED/AWARDED | Separat administrativ status; ingen automatisk spillet træningskamp |
| Ny FINISHED-status | Kræv gyldige mål, korrekt varighed og særskilt gennemgang før anvendelse |
| Ændret slutresultat | Bevar original; særskilt korrektion til gennemgang |
| FINISHED → ikke-afsluttet | Ingen automatisk nedgradering eller sletning af mål |
| Ældre provider_updated_at | Klassificér som gammel observation |
| Samme providertid, forskelligt indhold | Versionskonflikt; vælg ikke en vilkårlig vinder |
| Manglende versionstid eller identitet | Gennemgang; download-/ankomstorden er ikke en bevist kildeversion |
| Ekstra tid, straffespark eller ukendt målvarighed | Ikke et dokumenteret 90-minutters målgrundlag |
| Kamp udebliver fra et svar | Dækningsproblem; aldrig automatisk sletning |

Identiteten er kilde-navngivet, så en anden leverandørs samme nummer ikke slås
sammen. Hold-ID, liga/turnering og sæson kontrolleres ved ændringer. Ingen fuzzy
navnematch. Dato og UTC-kickoff skal stemme overens. Ens måltal i streng/nummerværdi
og ens UTC-tid skrevet med Z/+00:00 skaber ikke en falsk ændring.

Alle nye klassifikationer er forslag. Selv en konsistent nyere version er ikke
alene bevis for, at målene er korrekte, eller at de var kendt på et historisk
prognosetidspunkt. provider_updated_at er aldrig automatisk known_at.

## Kilder og kildekritik

- [football-data.org v4 Match](https://docs.football-data.org/general/v4/match.html):
  originalt matchobjekt, ID, sæson, utcDate, lastUpdated og statusser undersøgt.
- [Leverandørens scoredefinition](https://docs.football-data.org/general/v4/overtime.html):
  hele den korte side gennemgået; fullTime er også løbende score, duration skal
  undersøges ved ekstra tid/straffespark. Dette er den relevante datakontrakt.
- [Microsofts event-sourcing-beskrivelse](https://learn.microsoft.com/th-th/azure/architecture/patterns/event-sourcing):
  original arkitekturreference om bevaret historik, idempotens, rækkefølge og
  samtidighed undersøgt. Dette er designstøtte; SIG er ikke ombygget til et nyt system.
- [Stack Overflow om out-of-order events](https://stackoverflow.com/questions/78635839/how-to-maintain-data-integrity-with-concurrent-and-out-of-order-events):
  problem og løsningsdiskussion undersøgt; praktisk spor, ikke bevis for vores kode.
- [Digital Spy, indlæg 202–204](https://forums.digitalspy.com/discussion/2494370/david-flett-s-football-betting-thread-26-27-season/p9):
  erfaringsudsagn om udsættelse/afregning; ingen generel regel udledt.
- [William Hills egne fodboldregler](https://help.williamhill.com/hc/en-gb/articles/36444262255133--General-Football-Rules):
  officielle regler om udsættelse, afbrudte kampe og afregning undersøgt. De viser,
  hvorfor leverandørens kampstatus og bookmakerens afregning skal holdes adskilt;
  de anvendes ikke som regler for andre bookmakere eller som tilladelse til spil.

Ingen statistisk modelhypotese eller insiderpåstand er implementeret. Tidligere
forskningskilder og nørdeforumspor er bevaret i RESEARCH_LOG.md; ingen påstand om
udtømmende forskning eller en fuldt gennemlæst forumhistorik fremsættes.

## Næste afgrænsede skridt

1. Byg en reversibel, versionsbundet korrektionsvej for den ene dokumenterede
   90-minutters kandidat. Originalscore, score_duration, regularTime og begrundelse
   skal bevares. Et preview må ikke skrives tilbage uden ny kontrol af workspace-CAS.
2. Sikr versionsbevaring af rå API-observationer før kommende refresh. Den nuværende
   api_matches-cache kan overskrives under samme nøgle; workspaceversioner bevarer
   normaliserede snapshots, men er ikke fulde råsvar med alle tidsfelter.
3. Når en korrektion anvendes, markér afledte tests som forældede og genberegn kun
   de berørte analyser. En ændret historisk rapport må ikke fremstå som en ny
   uafhængig validering.
4. Gå derefter videre efter den [afgrænsede turneringsdataplan](competition_data_plan.md).
