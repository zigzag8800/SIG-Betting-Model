# SIG System Register – teknisk arkitektur og revisionsstatus

**Revision:** 24. oktober 2026. **Undersøgt HEAD:** `6bd20f1203ea91d70a7327052effeb41b1e125ba`.

Dette dokument er registeret over **undersøgte** komponenter. Det er ikke en komplet liste over samtlige filer i repositoryet: den anvendte GitHub-forbindelse kunne læse navngivne filer, men ikke liste hele repositorytræet. Ukendte filer må ikke antages at være fraværende. Sammenhold med [PRINCIPLES.md](PRINCIPLES.md), [dataauditen](reports/data_quality_2026-10-24.md) og [korrigeret backtest](reports/backtest_recomputed_2026-10-24.md).

## Grundregel for status

- **Eksisterer**: implementeringen er læst i HEAD.
- **Tidligere dokumenteret**: et dateret projektbevis findes; resultatet gælder ikke automatisk nyere commits.
- **Uverificeret i HEAD**: nyeste CI/live-app/PostgreSQL er ikke kontrolleret.
- **Planlagt**: kun forslag; må ikke omtales som udført.

## Undersøgte moduler og ansvar

| Komponent | Funktion | Aktuel status | Handling |
|---|---|---|---|
| `app.py` | Streamlit, API-kald, import, session og test-UI | Eksisterer; 1.063 linjer. For mange blandede ansvar | Bevar UI og adfærd; overvej senere udtræk af importorkestrering med karakteriseringstests |
| `persistent_store.py` | PostgreSQL, cache, versioner, downloadkvoter, workspace og audit | Eksisterer; JSONB i `sig_archive` samt `sig_downloads`. Versionsskrivning nyligt ændret; uverificeret i live DB | Først regressions- og databasekontrol; ingen direkte migration |
| `sig_model.py` | Eksisterende prognosemotor og kronologisk backtest | Eksisterer, skal fungere uændret | Frys produktionsberegning indtil uafhængigt benchmark |
| `model_lab.py` | Modelvarianter/kontrol | Eksisterer | Bevar og test mod SIG E |
| `league_lab.py` | Pooling og parametersøgning | Importeret af app | Kortlæg effekter før ny tuning |
| `attack_defence_40.py` / `compare_40.py` | SIG 4.0 forskning og kontrolsammenligning | Kendt forskningsspor; ikke produktion | Bevar adskillelse |
| `archive_audit.py` | SQL-arkivaudit, metadata og ZIP/CSV-inventar | Eksisterer; 224 linjer | Én autoritativ rapport pr. defineret scope |
| `data_quality_40.py` | Top 5-dækning og spillerdatakontrol | Eksisterer; 121 linjer | Undgå parallelle, modstridende tællinger |
| `match_identity_audit.py` / `match_lifecycle.py` | Kampidentitet, kampændringer og resultatomfang | Eksisterende indgange; tidligere audit dokumenteret | Konsolider fælles identitetskontrakt før migration |
| `regular_time_correction.py` | Reviderbar 90-minutters korrektion | Tidligere dokumenteret; konkret korrektionsbevis | Bevar fuld original og revisionsspor |
| `competition_archive_40.py` | Forskningskampe på tværs af turneringer | Eksisterer; ikke verificeret fuld dækning | Afvent dokumenteret kilde-/sæsonplan |
| `schedule_features_40.py` | Tværturneringskalender og features | Eksisterende import i app | Må ikke tolke manglende spillerbelastning som nul |
| `backtest_revision.py` | Reproduktion af før/efter-backtest | Eksisterer; intern genkørsel dokumenteret | Bevar historiske sammenligninger |
| `bookmaker_lab.py` / `benchmark_diagnostics.py` | Bookmakersammenligning og diagnostik | Eksisterende imports | Ingen nye odds-/prisindsamlinger i denne fase |
| `historical_coverage.py` / `closing_source.py` | Historiske data- og kildeimportveje | Eksisterende imports | Respektér godkendelser, kvoter og cache |

## Hvad den eksisterende database allerede skelner mellem

`sig_archive` anvender sammensat nøgle `(kind,key)` og `payload jsonb`. Observerede typer i kode inkluderer `workspace`, `workspace_version`, `api_matches`, `api_matches_version`, `source_csv`, `provider_bundle`, `imported_backtest` og `diagnostic`. Dette er **logiske dataskel**, selvom det ikke er normaliserede relationstabeller. `sig_downloads` håndhæver leverandørkvoter separat.

Det er derfor forkert at hævde, at data ikke kan adskilles i den gamle database. Risikoen er derimod svagere relations-/datokontrakter, vanskeligere konsistenskontrol og blanding af aktive data, historiske versioner og forskningsdata i et generelt JSON-lag.

## Dateret evidens – ikke aktuel livepåstand

- Den dokumenterede databaseaudit opgjorde **2.792** afsluttede, **1.819** kommende og **2.102** afsluttede Top 5-kampe. Kilde: `reports/data_quality_2026-10-24.md`.
- Den korrigerede interne backtest omfattede **2.398** identiske testkampe med Brier **0,2066035893** efter korrektion. Kilde: `reports/backtest_recomputed_2026-10-24.md`.
- Sidst dokumenterede grønne CI i ovenstående rapport var Actions #64 på **e00b077** med **123 tests**. **Ingen grøn CI, komplet repositoryinventar eller live PostgreSQL-verifikation er dokumenteret for HEAD 6bd20f1**.

## Prioriteret fundliste

1. **P0 – Test- og installationsbevis mangler** for ændringerne til API-versionshistorik. Ingen nye importer, før regressions-/livekontrol er udført.
2. **P0 – Proveniens:** versionerne indeholder parsede `matches`-arrays, ikke originale HTTP-body/headers; `saved_at` er indsættelsestid, ikke historisk `known_at`. Kræv præcis terminologi.
3. **P1 – Adgangs- og teststruktur:** `app.py` kombinerer flere ansvar. Reduktion bør ske i små adfærdsbevarende skridt, ikke ved omskrivning.
4. **P1 – Datamodel:** `(kind,key,payload)` er fleksibel, men har ikke eksplicitte fremmednøgler, separate kampversioner eller spillerrelationer. Undersøg et **nyt skema sideløbende**, ikke automatisk ny fysisk database.
5. **P1 – Datadækning:** historisk `known_at`, internationale/pokalkampe og dokumenteret spillerbelastning er ikke klar til uafhængig modelvalidering.
6. **P2 – Duplikeret kontrol:** samme begreb (fx dækning eller scorevaliditet) har flere rapporteringsveje. Definér én canonical kontrakt og regressionstest, inden eventuel konsolidering.
7. **P2 – Ukendt repositoryomfang:** komplet filtreoversigt, alle CI-runs og status for upubliceret Work-arbejde skal afklares inden schema-beslutningen.

## Beslutning om Database 2.0

**Ingen sletning, ingen flytning, ingen ny produktionsdatabase nu.**

Den anbefalede kandidat er et versioneret PostgreSQL-skema i samme eksisterende instans, med **read-only migration fra låst snapshot**, eksplicitte kilde- og kamp-ID'er, sæsoner, hold, kamphændelser, resultatomfang, spilletid, kildeobservationer, historiske medlemskaber og modelkørsler.

Før designet vedtages:
1. Eksportér komplet skema-, tabel-, indeks-, view-, constraint- og referenceinventar i read-only transaktion.
2. Kortlæg alle eksisterende læse-/skriveveje, inkl. eventuelle andre scripts uden for den undersøgte filliste.
3. Definér datakontrakter og tre testcases pr. kritisk objekt: normal, konflikt, sen rettelse.
4. Lav en **migrationsprototype kun på isolerede testdata**; sammenlign eksakte populationer, hashes, mål og originale versioner.
5. Beslut eksplicit, om den nye struktur giver mærkbar bedre korrekthed, auditabilitet eller anvendelighed end forbedringer af den gamle.
6. Produktionsskift kræver uafhængig kontrol, grøn CI, live read-only parity-rapport og plan for tilbagerulning.

## Arbejdsdisciplin

Før nyt udviklingstrin: kontrollér HEAD → søg eksisterende funktion → angiv konkret fejl/hypotese → vælg mindst mulige ændring → regressionstest → CI på eksakt commit → live-verifikation ved relevans → dokumentér status og nyt restpunkt. Skeln konsekvent mellem **gemt kode** og **faktisk verificeret effekt**.
