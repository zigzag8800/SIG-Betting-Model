# SIG Betting Model – fælles projektprincipper

Opdateret 24. oktober 2026. Dette er projektets fælles reference for videre arbejde.
Grundlag: brugerens aktuelle instruktioner og de tilgængelige tidligere SIG-tråde.
Historiksøgning er ikke en garanti for adgang til samtlige beskeder i alle tråde.
Nyere, konkrete brugerbeslutninger har forrang for ældre planer.

## 1. Mål og kontinuitet

Ambitionen er verdens bedste fodboldanalysemodel målt på dokumenteret statistisk
præcision. Ambitionen må aldrig præsenteres som et opnået resultat.
Byg videre på eksisterende kode, funktioner, data, indstillinger og arkitektur.
Kontrollér altid aktuel GitHub HEAD før ændringer. Bevar lokalt upubliceret arbejde
og andre samtidige ændringer. Ingen genstart fra bunden uden dokumenteret behov.

SIG 3.6 er produktionsmodellen. SIG E bevares som kontrolmodel. SIG 4.0 er et
forsøg. Produktionsmodellens sandsynligheder ændres først efter uafhængig test
og dokumenteret forbedring. Høj sandsynlighed og god kalibrering prioriteres over
høje odds; høj træfsikkerhed alene dokumenterer ikke gode sandsynligheder.

Aktuel forskningsprioritet er Top 5 og datakvalitet. Tidligere planer med seks/syv
ligaer må ikke bruges som tilladelse til at slette Championship eller anden historik.

## 2. Kontrollér forudsætninger før næste trin

Vurdér separat, om vi er klar til (a) databaseaudit, (b) kodeændringer,
(c) uafhængig modeltest og (d) produktionsbrug. Ét grønt trin gør ikke de andre grønne.
Registrér aktuel commit, adgang til relevante værktøjer, live-app, databasens faktiske
læse-/skrivevej, reproducerbart testmiljø, datadækning og åbne begrænsninger.
Et manglende login er en adgangsblokering; manglende data er et forskningsproblem.
Udfør arbejde, som de tilgængelige forudsætninger understøtter, og angiv præcist,
hvilke konklusioner de ikke understøtter. Inddrag kun brugeren ved nødvendig login,
adgangsnøgle, godkendelse eller en beslutning, der faktisk kræver brugerens valg.

## 3. Research skal gå i dybden – også i nørdefora

For hver væsentlig undersøgelse udarbejdes et konkret spørgsmål og en kildeplan.
Søg bredt i følgende kildefamilier og log relevans, fund og adgangsbegrænsninger:

- Videnskabelige originalartikler, reproducerbare studier og metodekritik.
- Officiel dokumentation, dataleverandørernes feltspecifikationer og vilkår.
- GitHub-kode, tests, issues, fejlrapporter og diskussioner.
- Nørdefora, specialiserede betting-/tradingfora, udviklerfora og Reddit.
- Databaser og arkiver med dokumenteret oprindelse, tidsdækning og anvendelsesret.
- Dokumenterede insider-/whistleblowerberetninger om bookmakerpraksis, når de
  er relevante og kan vurderes ud fra identificerbar originalkilde og belæg.

Research må ikke slutte ved de første guides eller bekræftende eksempler. Søg
aktivt efter modargumenter, negative resultater, fejlslagne reproduktioner,
datalækage, selektionsbias, ændrede dataspecifikationer og skjulte antagelser.
Åbn relevante originalkilder; en søgemaskines uddrag er ikke en gennemlæst tråd.
Log hvor stor en del af en tråd, artikel eller kodebase der faktisk er gennemgået.
Forumindlæg er spor og erfaringsudsagn, ikke automatisk dokumentation for metode
eller profit. Tekniske konklusioner skal støttes af primærkilder og egne tests.
Ingen kilde vægtes højt alene på grund af afsenderens påståede insiderstatus.

Skeln eksplicit mellem **dokumenteret observation**, **reproduceret resultat**,
**hypotese**, **erfaringsudsagn** og **rygte/ubekræftet påstand**. To sider, der
kopierer samme historie, er ikke to uafhængige kilder. For hver væsentlig kilde
registreres URL, dato, ophav, påstand, evidensniveau, relevans, begrænsning og en
mulig falsifikation/test. Se [RESEARCH_LOG.md](RESEARCH_LOG.md).

Dybden skal følge den konkrete risiko: en datakontrakt skal afklares og testes før
import; en modelidé kræver reproduktion og uafhængig evaluering. Ingen kan love
at undersøge hele internettet. En udeladt kildefamilie eller en uløst modstrid
skal fremgå, når den kan ændre beslutningen. Manglende belæg skal føre til
usikkerhed eller en afgrænset test, ikke til opdigtede forklaringer.

## 4. Datakvalitet før flere modeller

Før en ny modelsammenligning verificeres faktisk PostgreSQL-dækning pr. liga,
turnering og sæson. Sessionsdata, aktivt workspace, rå API-cache, rå CSV/ZIP og
historiske workspaceversioner opgøres særskilt. De må ikke lægges sammen som
unikke kampe. En komplet rapport kræver et defineret undersøgelsesomfang;
uforarbejdede ZIP-medlemmer og uundersøgte lag skal nævnes.

Kontrollér kamp-ID med kilde-navnerum, hold-ID, UTC-kickoff, sæson, status,
heltallige ikke-negative mål, dubletter, modstridende oplysninger, datakilde og
historisk informationstidspunkt. Skeln en spillet kamp fra en administrativt
afgjort, udsat eller aflyst kamp. Et felt med indhold er ikke nødvendigvis gyldigt.
Forventet antal kampe kræver dokumenteret turneringsformat og afgrænsning;
kommende kampe må ikke kaldes manglende resultater.

Bevar rådata og versionshistorik. Sparsomme importer må ikke slette dokumenterede
metadata. Identitets- og resultatkonflikter skal synliggøres og undersøges.
Genskab kun metadata ved en entydig, dokumenteret kildekobling; ingen gættede
ID'er eller fuzzy navnekoblinger uden særskilt validering. Gem originale oplysninger
før rettelser. Ingen sletning eller nulstilling uden udtrykkelig godkendelse.

`kickoff_utc`, leverandørens `lastUpdated`, vores indlæsningstidspunkt og
`known_at` er forskellige begreber. Opfind aldrig et historisk `known_at` ud fra
downloadtidspunktet. Manglende historik begrænser point-in-time-påstande, også
når et kronologisk testprogram ellers er korrekt skrevet.

## 5. Adgang, kvoter og omkostninger

Ingen nøgler eller adgangskoder i GitHub, rapporter, tests, CSV'er eller chatudskrifter.
Brug Secrets og sikker loginindtastning. Genbrug eksisterende data før nye kald.
Football-Data.co.uk kræver brugerens udtrykkelige godkendelse for hvert nyt forsøg;
det varige fælles register håndhæver højst to forsøg pr. rullende syv døgn.
Fejlede forsøg tæller. Cachegenbrug kræver ingen ny leverandørhentning.
Historiske kald uden for registeret er ikke automatisk kendt.
Respektér samtlige leverandørers aktuelle vilkår, adgangsniveau og rategrænser.
Gratis løsninger foretrækkes; betaling eller nye abonnementer kræver en konkret
brugerbeslutning. At researche Betfair som kilde medfører ingen Betfair-integration.

## 6. Validering og modeller

Faktiske mål og målt prognosepræcision er udgangspunktet. xG må undersøges,
men skal bevise ekstra værdi i uafhængige tests. Tidlige odds er en fremtidig idé;
der bygges ingen funktioner til dem under den aktuelle datakvalitetsopgave.

Sammenlign modeller på identiske kampe og ens informationstidspunkt. Anvend
kronologisk/walk-forward-evaluering, separat udvikling og urørt sluttest,
Brier-score, log-loss, kalibrering, usikkerhed og relevante liga-/markedssegmenter.
Dokumentér definitionen af Brier (sum eller gennemsnit over udfald) og metoden til
marginjustering. Brug relevante bookmakerbenchmarks og SIG E som kontrol.
Kontrollér datalækage i hele dataflowet, ikke kun i prognosefunktionen.
Log afprøvede varianter og negative fund. Vælg ikke parametre på sluttesten.
Et allerede undersøgt benchmark på 1.437 kampe er udviklingsinformation;
gentagen optimering på det gør det ikke til en ny uafhængig test.

Statistisk forbedring, profit og praktisk gennemførlighed er forskellige påstande.
Ingen af dem følger alene af en grøn regressionstest eller høj historisk træfsikkerhed.
Spillerbelastning kræver dokumenterede ID'er, historisk klubtilhørsforhold, minutter,
landskampe og tilgængelighedstid; manglende registrering betyder ikke nul belastning.

## 7. Implementering, bevis og kontrolpauser

Lav afgrænsede rettelser i eksisterende moduler med regressionstests, der rammer
fejlens årsag. Kør compile og relevante automatiske tests efter kodeændringer;
kontrollér GitHub Actions på den præcise kodecommit og verificér relevante liveflows.
Dokumentationsændringer kontrolleres for links, sammenhæng og korrekt status.

Rapportér adskilt: foreslået, lokalt ændret, lokalt testet, publiceret i GitHub,
grøn CI, verificeret i live-app og verificeret gemt i PostgreSQL. Påstå aldrig
et senere trin på grundlag af et tidligere. Log kendte restfejl og test, der ikke
kunne køres. Bevar brugerens mulighed for at gennemgå en konkret ændring.

Giv korte fremskridtsmeldinger under arbejdet. Hold et tydeligt kontrolpunkt efter
hvert større trin: undersøgelse, rettelse og verificering. Status skal beskrive
fund, præcise ændringer, faktisk testbevis, begrænsninger og næste trin. Undgå
lange serier af usynlige ændringer. Fortsæt almindeligt autoriseret arbejde
selvstændigt; statuspauser er ikke en ny generel godkendelsespligt. Stop ved
brugerens pauseønske. Afslut altid med et tydeligt **NÆSTE STEP**.

## 8. Kampændringer og resultatvarighed

Brug kilde + kamp-ID som permanent identitet; dato/kickoff må kunne ændres uden
at skabe en ekstra kamp. Statushistorik og originalresultater skal bevares.
Konkurrerende eller uordnede versioner kræver eksplicit konfliktkontrol; ankomsttid
og provider lastUpdated må ikke forveksles med historisk known_at.
Skeln mellem numerisk gyldigt målresultat og korrekt 90-minutters målgrundlag.
Forlænget spilletid, straffespark, administrativ afgørelse og bookmakerafregning
er forskellige forhold. En score/fullTime må ikke automatisk bruges som regularTime.
Se [de testede kontrolregler og det aktuelle fund](reports/match_lifecycle_2026-10-24.md).
En read-only kontrol er ikke en gennemført datakorrektion eller en implementeret
versionshistorik; disse trin skal rapporteres særskilt.

For almindelige 1X2-markeder er resultatgrundlaget 90 minutter plus dommerens
tillægstid; forlænget spilletid og straffespark medregnes ikke. Det gælder både
åbnings- og closing odds på samme marked. Tidspunktet for prisregistreringen
ændrer ikke markedets afregningsgrundlag. Vinder af opgøret/går videre er andre
markeder og må ikke blandes ind i et 90-minutters benchmark. Ved den fundne
EXTRA_TIME-kamp er det gemte regularTime-resultat 0–0 den relevante kandidat,
ikke fullTime-resultatet 2–1. Der bygges ingen funktion til tidlige odds hermed.
