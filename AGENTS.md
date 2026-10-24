# Arbejde i SIG Betting Model

Læs [PRINCIPLES.md](PRINCIPLES.md) før væsentligt arbejde og følg brugerens
nyere, konkrete instruktioner ved modstrid. Principperne samler datakontrakter,
researchdybde (inklusive nørde-/bettingfora), kildekritik, validering og statuspauser.
Læs [RESEARCH_LOG.md](RESEARCH_LOG.md) og relevante statusrapporter i `reports/`
for allerede undersøgte spor; behandl dem som daterede observationer.

Kontrollér aktuel GitHub HEAD før ændringer. Bevar produktionens model og data.
Efter kodeændringer: `python -m compileall -q .` og
`python -m unittest discover -s tests -v`, relevante livekontroller samt CI på den
konkrete commit. Dokumentationsændringer kræver ikke en ny modeltest.
Hemmeligheder må aldrig indgå i repository eller udskrifter.
