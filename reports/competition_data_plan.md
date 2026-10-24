# Afgrænset plan for ekstra turneringsdata

Status 24. oktober 2026: **plan, ingen nye data hentet og ingen betaling oprettet**.
Grundlaget er Top 5-klubbernes allerede gemte 2025/26- og 2026/27-ligakampe.
Championship bevares, men udvider ikke automatisk SIG 4.0's forskningsscope.

## Rækkefølge

Færdiggør først resultatvarighed, råversionshistorik og korrektionsvej som beskrevet
[her](match_lifecycle_2026-10-24.md). Afklar dernæst officiel turneringsidentitet,
kontoadgang, licens, kvote og forventet dækning pr. kilde. Lokale kodekonstanter
eller tests mod egne konstanter dokumenterer ikke en leverandørs aktuelle katalog.

| Datablok | Første brug | Påkrævede oplysninger | Dækningskontrol før brug |
|---|---|---|---|
| Champions League, Europa League, Conference League | Klubbernes ekstra kampprogram | Kilde/kamp-ID, turnering/sæson/stadie, begge hold-ID, faktisk og planlagt kickoff, status og versions-/observationstid | Verificér alle relevante Top 5-klubbers kampe inkl. afgrænsede kvalifikationsrunder; dokumentér udeladelser |
| Nationale pokaler i Top 5-lande | Ekstra kampe og restitution | Samme felter, plus regularTime/fullTime, duration og replay-/omkampsrelation hvor dokumenteret | Afklar hver turnerings runder; en ny kamp må ikke fuzzy-kobles som en flytning |
| Landskampe | Først senere individuel spillerbelastning | Kamp-ID, landsholds-/spiller-ID, minutter og kamp-/indlæsningstid | Klubtilhørsforhold skal være historisk dateret; et klubnavn må ikke bruges som landsholdskobling |
| Spilleropstillinger og minutter | Individuel restitution | Verificeret spiller-ID, historisk klub-ID, spilleminutter, udskiftninger og informationstid | Et manglende spillersvar er ukendt belastning, ikke nul minutter |

Klubkampprogram kan undersøges før spillerbelastning; landshold påvirker ikke
klubbelastning automatisk uden verificerede spillermappinger. Ingen ny prognosefeature
aktiveres blot fordi en tabel er udfyldt.

## Indhentning og accept

- Genbrug og auditér eksisterende relevante cacheposter først. De nuværende 12
  cacheposter indeholder ingen af ovenstående ekstra turneringsdatasæt.
- Fastlæg forventet kampliste fra dokumenteret turneringsformat eller en verificeret
  officiel kampoversigt. Gem både antal og nævnerens afgrænsning.
- Afklar provider-katalog og brugerens abonnement før en batch. Et 403 er manglende
  adgang, ikke en tom turnering; 429 stopper resterende kald; ved invalid token stoppes
  batchen. Ingen retry-løkker eller gentagelse af kendt afviste kombinationer.
- Lav en konkret manifestliste med kilde, turnering, sæson, ønskede felter, forventede
  kald, cachetræffere, adgang/omkostning og prioritet før nye hentninger.
- Ingen nye Football-Data.co.uk-forsøg uden brugerens særskilte godkendelse; højst to
  forsøg pr. rullende syv døgn i fælles ledger. En ny betalt kilde kræver brugerbeslutning.
- Acceptér først et datasæt til forskning efter ID-/status-/tids-/varighedskontrol,
  eksplicit liste over mangler og ingen uforklarede konflikter. Data kan arkiveres som
  ufuldstændige uden at få status som modelklare.
- Manglende historisk known_at skal beskrives som begrænsning; nutidig indlæsning kan
  etablere en faktisk observationstid fremover, ikke skabe fortidig viden.
- Hold den allerede brugte 1.437-kamps bookmakeranalyse som udviklingsinformation.
  Fastlæg en fremtidig, urørt evalueringsperiode og kriterier før modeloptimering.

Planen kræver ingen ny konto eller dataleverandørhentning for at blive gennemgået.
Næste konkrete adgangsbeslutning træffes først ud fra det færdige manifest, ikke
ud fra et gæt om gratis-/betalingsadgang.
