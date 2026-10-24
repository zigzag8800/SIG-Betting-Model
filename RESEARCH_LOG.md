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
