# SIG – researchlog

Denne log angiver undersøgte kilder og åbne spor. En registreret kilde er ikke en
anbefalet integration eller et reproduceret forskningsresultat. Se PRINCIPLES.md.

## 24. oktober 2026 – forudsætninger og datakvalitet

Spørgsmål: Har vi adgang, data og kontrolmetoder til at afslutte den eksisterende
databaseaudit, og hvilke begrænsninger forhindrer en stærkere valideringspåstand?

| Kilde / ophav | Faktisk gennemgang | Evidens og relevans | Begrænsning / næste kontrol |
|---|---|---|---|
| [football-data.org v4 Match](https://docs.football-data.org/general/v4/match.html), leverandør | Dokumentation åbnet; felteksempel og statusdefinitioner undersøgt | Primær dokumentation for kamp-/hold-ID, sæson, UTC-tid og særskilte statusser; støtter eksplicit håndtering af AWARDED/CANCELLED | Dokumenterer datakontrakten, ikke at en bestemt historisk kamp er sportsligt korrekt registreret |
| [PostgreSQL SET TRANSACTION](https://www.postgresql.org/docs/current/sql-set-transaction.html), PostgreSQL | Officiel reference åbnet; isolation og read-only undersøgt | Primær dokumentation for undersøgelse i konsistent repeatable-read-transaktion uden datamutation | Verificér også egne SQL-kald og faktiske live-resultater; isolation gør ikke kildedata korrekte |
| [Gneiting & Raftery 2007](https://sites.stat.washington.edu/raftery/Research/PDF/Gneiting2007jasa.pdf), originalartikel | PDF åbnet; abstract og oversigt over scoringregler læst | Primær metodekilde til probabilistisk evaluering; relevant for Brier/log-score | Ikke fuldt gennemlæst eller reproduceret i denne forudsætningskontrol; fremtidig metodegennemgang kræver præcise afsnit og egne eksempler |
| [Bet Angel-forum: Any way to backtest an automated strategy?](https://forum.betangel.com/viewtopic.php?t=17789), flere deltagere, 2018 | Første trådside åbnet; indledende indlæg og søgeuddrag om overfitting undersøgt | Erfaringsudsagn og uenighed om backtest kontra fremadrettet bevis; giver spørgsmål til testdesign | 69 indlæg over fem sider; ikke hele tråden læst. Ingen profitpåstand eller generel metodekonklusion accepteres på dette grundlag |
| [Reddit r/algobetting: preventing data leakage](https://www.reddit.com/r/algobetting/comments/1h6smq0/), 2024 | Søgeuddrag set; direkte åbning fejlede | Spor om sæsonholdout, tidsrækkefølge og skæv testpopulation | Ikke gennemlæst originaltråd; lav evidens, ingen teknisk konklusion baseret alene på den |
| [Tomashcv/FootballMarketResearch](https://github.com/Tomashcv/FootballMarketResearch), repositoryforfatter | Repositoryside åbnet; søgeresultatets forfatterrapporterede negative/positive resultater identificeret | Primært artefakt og muligt reproduktionsspor; interessant fordi negative fund bevares | Kode, datasæt og resultatpåstande er ikke reproduceret eller accepteret som benchmark. Ingen ekstern kode kørt |
| Tidligere SIG-tråde, via Personal Context | Målrettet søgning efter krav om research, kvalitet, præcision, adgang og status | Brugerens tidligere eksplicitte krav understøtter de fælles principper | Søgeværktøjet giver udvalgt tilgængelig historik, ikke garanti for samtlige tråde eller fulde filindhold |

### Åbne spor og afgrænsning

- Ingen dokumenteret insider-/whistleblowerberetning er valideret i denne kontrol.
  Der er ikke identificeret et behov for en sådan kilde for at afgøre egne
  PostgreSQL-rækketællinger. Et fremtidigt udsagn om bookmakerpraksis kræver
  særskilt originalkilde og verifikation.
- Udviklerfora og konkrete GitHub-issues er en del af kildeplanen, men der er
  ikke gennemført en særskilt issue-/udviklerforumundersøgelse i dette kontrolpunkt.
- Undersøgelsen er en indledende vurdering af forudsætninger, ikke en fuldført
  litteraturgennemgang af fodboldmodellering. Næste databasearbejde afgrænses i
  reports/readiness_2026-10-24.md. Ingen leverandørdata blev hentet i denne kontrol.

## 24. oktober 2026 – afslutning af arkivkontrol

- Spørgsmål: indeholder den allerede gemte sæson-ZIP mere end de seks indlæste
  divisioner, og kan importkonflikter ødelægge tidligere data?
- [Python 3.11 zipfile](https://docs.python.org/3.11/library/zipfile.html) blev åbnet;
  memberlæsning og dokumenterede ekstraktions-/ressourceproblemer kontrolleret.
  Egen implementering læser i hukommelsen med eksplicitte fil-/udvidelsesgrænser.
- [Leverandørens arkivside](https://football-data.co.uk/downloadm.php) blev søgt
  for fil- og oddsdefinitioner. Direkte notes.txt-læsning returnerede 429; ingen
  genforsøg eller ekstra sæsondata hentet. Referencefeltet C er dokumenteret som
  closing; ingen ny oddsmodel eller integration blev implementeret.
- Reproduktion: 22 eksisterende ZIP-medlemmer, 7.647 rækker, én ugyldig målpost
  i F2.csv. Aktive ID-/tids-/dubletkontroller og detaljer er i
  [den faktiske rapport](reports/data_quality_2026-10-24.md).
- Egne GitHub-diffs, regressionssuite, fire AppTest-flows, grøn CI #59 og eksport
  fra adgangsbeskyttet live-app er den konkrete evidens for rettelserne.
- De tidligere loggede forumspor gav risikospørgsmål om leakage og overfitting,
  ikke belæg for nye databasetal. Ingen nye insiderpåstande blev brugt. En separat
  udviklerforum-/issueundersøgelse blev ikke nødvendig for denne reproducerede
  lokale importfejl; det er ikke en påstand om en fuld litteraturgennemgang.

## 24. oktober 2026 – kampers livscyklus og scorevarighed

Spørgsmål: kan flytninger, sene svar og ændrede slutresultater behandles uden at
miste historik eller skabe dubletter, og er fullTime altid et 90-minutters resultat?

- football-data.org v4 Match og den korte score/duration-side blev åbnet; den sidste
  gennemgået fuldt. Primær datakontrakt viser behovet for REGULAR/EXTRA_TIME/
  PENALTY_SHOOTOUT-kontrol og adskillelse af løbende og afsluttede mål.
- Microsofts egen event-sourcing-reference (Learn og GitHub) blev undersøgt for
  bevaret historik, ordering og idempotens. Ingen ekstern kode blev kørt eller ny
  arkitektur indført; eksisterende workspace, cache og optimistiske låse bevares.
- Stack Overflow-spørgsmålet om out-of-order events blev åbnet og problem/
  timestampdiskussion undersøgt. Forumsporet bruges som modargument til blind
  ankomstsortering, mens kodebeslutningen støttes af egne regressionstests.
- Digital Spy-indlæg 202–204 blev læst som konkret erfaring med udsættelse og
  afregning. William Hills originale fodboldregler blev åbnet for regler om
  postponement/abandonment. Afregningsregler er bookmaker-/markedsafhængige og
  blev ikke implementeret i modelhistorikken.
- Søgning efter football-data.org-specifikke GitHub-issues gav ikke en relevant
  verificeret fejlrapport. Den beskrevne fejl er reproduceret i vores eget merge-
  og AppTest-flow; ingen påstand om fuldstændig issuegennemgang.
- Ingen ny statistisk metode eller insiderpåstand undersøgt/indført i denne blok.
  Tidligere metodeartikler er fortsat baggrund; ændringen vedrører datakontrakt.
- Reproduceret fund: match 557838, Southampton–Middlesbrough, EXTRA_TIME 2–1 og
  regularTime 0–0 i den eksisterende cache. Det aktive 2–1-resultat er ikke ændret.
  [Rapport og kilder](reports/match_lifecycle_2026-10-24.md) angiver test- og livebevis.
