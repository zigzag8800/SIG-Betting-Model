# Forudsætninger – 24. oktober 2026

## Beslutning

Vi kan færdiggøre den igangværende database-/datakvalitetsundersøgelse med de
nuværende adgange. Det foreliggende grundlag er endnu ikke tilstrækkeligt til at
påstå fuld historisk point-in-time-validering eller en forbedret produktionsmodel.

## Kontrolleret grundlag

- GitHub: aktuel kode-HEAD ved kontrollens start var `3fbf76a`; connectorens læsning
  lykkedes. Skriveadgang blev demonstreret ved de foregående kodecommits.
- CI: kodecommit `3fbf76a` har grøn SIG regression checks #57,
  https://github.com/zigzag8800/SIG-Betting-Model/actions/runs/40087221395 .
- Streamlit: privat adgang blev verificeret i den foregående arbejdsblok.
  Nye sessioner kan kræve sikker genindtastning af arkivets adgangskode.
- PostgreSQL: serverens separate læsetransaktion efter metadatarettelsen viste
  de gemte oplysninger. Der er ingen verificeret direkte lokal databaseforbindelse;
  den fungerende kontrolvej går gennem den adgangsbeskyttede Streamlit-server.
- Aktivt workspace: 2.792 afsluttede og 1.819 kommende kampe. Metadata blev genskabt
  fra 12 eksisterende API-cacheposter med entydigt match på liga/dato/hold og
  resultatkontrol for historiske kampe. Ingen konflikt og intet nyt leverandørkald.
- Lag undersøgt: inventar af samtlige sig_archive-kategorier, aktuelle kampe,
  alle 12 API-cacheposter, seks arkiverede CSV'er og ni workspaceversioner efter
  rettelsen. Versioner og kildefiler er alternative repræsentationer, ikke ekstra
  unikke kampe. Ét importeret backtestarkiv er identificeret, ikke rå træningsdata.

## Det, der fortsat begrænser opgaven

- Historisk `known_at` mangler. Kickoff eller indlæsningstid kan ikke erstatte det.
- Normaliseret ligaarkiv/API-cache dækker startårene 2025 og 2026. Råfilernes navn
  angiver 2025/26; audit beholder sæson som ukendt, hvor selve CSV-rækken ikke
  har eksplicit sæson. Ingen påstand om bredere historik på dette grundlag.
- Top 5 har 2.102 gyldige afsluttede resultater. Den aktive Ligue 1-historik har
  305 for 2025/26; API-cachen har yderligere en AWARDED-post. La Liga 2026/27 har
  en CANCELLED-post i cachen, men ikke i aktive kamplister. Dette er først en
  konstatering af leverandørstatus; sportslig hændelse/korrekt resultat er ikke
  uafhængigt efterprøvet. De må ikke automatisk føjes til spillet træningshistorik.
- Undersøgte forskningsarkiver og tidligere workspaceversioner har nul registrerede
  ekstra turneringskampe. Ingen tilsvarende turneringer i de 12 API-cacheposter.
  Spillerbelastning og omfattende europæisk/pokal-/landsholdshistorik er ikke klar.
- Den originale leverandør-ZIP er bevaret og inventeret, men dens øvrige, ikke
  udvalgte medlemmer er ikke alle gennemgået. Rapporten må ikke kaldes komplet
  kampinventar for alle data i ZIP'en, før den kontrol er udført.
- Sammenligning med forventede kamptal skal tage højde for sæsonstadie,
  turneringsformat og administrative afgørelser. Rækketælling er ikke nok.
- Lokal Streamlit AppTest kunne ikke køres i det benyttede Python-miljø, fordi
  streamlit ikke var installeret. Unit suite og compile kan køres; relevante
  flows blev verificeret i live-appen. Et komplet lokalt apptestmiljø er et åbent punkt.
- Historik på tværs af chats er målrettet genfundet, ikke udtømmende gennemlæst.
  RESEARCH_LOG.md skelner gennemlæste kilder fra søgeresultater og åbne spor.

## Ikke-publiceret arbejde skal bevares

En yderligere lokal rettelse i audit-arbejdstræets app.py bevarer sæson fra
importjobbet, håndterer importkonflikter uden delvis udskiftning af kamplister og
opdaterer loaded_combos efter en vellykket sammenfletning. Den var lokalt testet,
men var ikke med i `3fbf76a`. Principopdateringen publicerer ikke denne kode skjult.

## Næste afgrænsede arbejdsblok

1. Afslut inventaret af den allerede gemte ZIP uden nye leverandørkald.
2. Dokumentér status-/sæsonforskelle og forventede kamptal med klare nævnere.
3. Færdiggør og gennemgå den lokale importrettelse med specifikke regressionstests,
   publicér den separat og verificér CI og relevante liveflows.
4. Aflever den samlede dækningsrapport, restmangler og et nyt kontrolpunkt.

Ingen ny model, xG-/tidlig-oddsfunktion, betaling, sletning eller ny leverandørhentning
indgår i denne arbejdsblok. Større modelresearch kommer efter datakvalitetsarbejdet.
