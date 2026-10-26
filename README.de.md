# /pitch – AI Business Idea Court für Claude

`/pitch` macht aus einem offenen Wunsch („Wie verdiene ich Geld mit KI-Videos?“) **eine
begründete Geschäftsidee und einen umsetzbaren Produktplan**. Der Skill baut auf dem
[`/court`-Skill von Alex Chen](https://github.com/alexyc9381/court-skill) auf. Bei `/court` stellst du eine
fertige Idee vor Gericht; hier entwickeln zwölf Geschworene erst eigene Ideen.

```
/pitch How do I make money with AI videos?
/pitch Ich möchte mit maximal 500 Euro und als Einzelperson ein digitales Produkt aufbauen.
/pitch --quick Welche Software könnte ich als Solo-Entwickler verkaufen?
```

## Ablauf

| Phase | Wer | Was |
|---|---|---|
| 1 Anfrage verstehen | Claude (Protokollführer) | Ziel, Bedürfnis, Einschränkungen, Annahmen → `request.md`. Bei zu vagen Anfragen eine gezielte Rückfrage, bei Garantie-Erwartungen ein „Reality check“. |
| (Recherche) | Claude | Eine gemeinsame Recherche für die ganze Jury: bestehende Angebote und Preise, Wettbewerbsdichte, Plattformregeln → `research.md` mit Quellen. |
| 2 Ideen | 12 Juroren, gleichzeitig und unabhängig | Je eine konkrete Idee mit Problem, Zielgruppe, Lösung, Geschäftsmodell, Preis, Vorteil, Aufwand, Startkosten, Risiken, Nachfragetest und Annahmen. |
| 3 Debatte | 12 Juroren | Jeder liest alle Ideen: Top 3, stärkster Einwand, Verbesserung, Kombination, zu verwerfende Idee. |
| 3b Shortlist | Obmann/Obfrau | Fasst die Debatte zusammen, verwirft Ideen, verbessert und kombiniert, und erstellt eine Shortlist mit 3–5 Kandidaten. |
| 4 Bewertung | 3 unabhängige Gutachter | 0–10 je Kriterium, optional KO bei Verletzung harter Vorgaben (z. B. Budget). |
| 5 Urteil | Richter | Wählt den Score-Ersten oder einen Kandidaten innerhalb von 3 Punkten; Executive Summary und Begründung. |
| 6–8 Plan | Produktarchitekt | Produktkonzept, MVP, Geschäftsmodell, Technik, Validierung, Roadmap, Risiken, 3 Sofortmaßnahmen. |

Das Skript `ideacourt.py` **berechnet die Scores deterministisch**, und zwar nicht das Sprachmodell:

| Kriterium | Gewicht |
|---|---:|
| Marktbedarf und Kundenproblem | 20 % |
| Umsatz- und Gewinnpotenzial | 20 % |
| Erreichbarkeit der Zielgruppe | 15 % |
| Technische und operative Umsetzbarkeit | 15 % |
| Wettbewerbsvorteil und Differenzierung | 10 % |
| Startkosten und Kapitalbedarf (höher = günstiger) | 10 % |
| Risiken und Regulierung (höher = sicherer) | 10 % |

`Score = Σ (Durchschnitt der Gutachter / 10 × Gewicht)`, Ergebnis 0–100. Ein Kandidat, den die Mehrheit
der Gutachter per KO ausschließt, kann nicht gewinnen. Die Stimmen aus der Debatte (3/2/1 Punkte)
werden angezeigt, entscheiden aber nicht. Eigene Gewichte: `--weights market=30,revenue=20,reach=10,feasibility=15,edge=5,cost=15,risk=5`.

Das Ergebnis ist `.ideacourt/<lauf>/REPORT.md` mit 13 Abschnitten: Executive Summary, Interpretation,
die zwölf Ideen, Ergebnis der Debatte, Bewertungstabelle, Gewinner, Produktkonzept, Geschäftsmodell,
technischer Plan, Validierung, Roadmap, Risiken/offene Fragen und Sofortmaßnahmen. Alle Ideen,
Debattenbeiträge, Bewertungsbögen und Briefings liegen daneben.

**Kosten:** Ein vollständiger Lauf umfasst 30 Sub-Agent-Aufrufe (12 Ideen + 12 Debattenbeiträge +
1 Obmann + 3 Gutachter + 1 Richter + 1 Architekt). Mit `--quick` sind es 16 Aufrufe: keine eigene
Debattenrunde und nur 1 Gutachter.

## Installation

Voraussetzung: Python 3 (auf Windows z. B. über `py -3`). Es gibt keine weiteren Abhängigkeiten.

**Claude Code (lokal):**

```bash
py -3 build.py --install      # Windows; sonst: python3 build.py --install
```

Das Skript kopiert den Skill nach `~/.claude/skills/pitch/`. Starte Claude Code danach neu
und tippe `/pitch <dein Ziel>`.

**claude.ai / Claude Desktop:** `py -3 build.py` erzeugt `dist/pitch-skill.zip`. Lade die
Datei unter *Settings → Capabilities → Skills* hoch, genauso wie `court-skill.zip`. Hochgeladene Skills
synchronisiert Claude Code automatisch. Installiere deshalb nur **einen** der beiden Wege, sonst
erscheint der Skill doppelt.

Tipp: Stelle für den Lauf den Accept-Edits-Modus ein (Shift+Tab), weil jeder Sub-Agent eine Datei
in `.ideacourt/` schreibt.

## Tests

```bash
py -3 -m unittest discover -s tests -v
```

- `tests/test_ideacourt.py`: Phasenreihenfolge, Validierung fehlerhafter Ausgaben, Score-Formel,
  Mittelung, Budget-KO (Szenario C), Gleichstand und Richterwahl, Debattenstimmen, Quick-Modus,
  Sprachen, alle 13 Report-Abschnitte sowie die Regeln in den Briefings und in `SKILL.md`
  (Szenarien A–E). Die Sub-Agenten werden dabei durch Fixture-Dateien ersetzt.
- `tests/test_court_regression.py` (Szenario F): Ein vollständiger `/court`-Prozess läuft aus
  `court-skill.zip` (Pfad über `COURT_SKILL_ZIP` oder Zip im Repo-Ordner), und die installierte Kopie von `/court` muss unverändert sein. Liegt das Zip
  nicht vor, wird der Test übersprungen.

Die Tests prüfen nur die Buchführung. Wie gut die Ideen eines echten Laufs sind, zeigt erst ein Lauf
mit echten Sub-Agenten.

## Grenzen

- Die Juroren, Gutachter und der Richter sind **Rollen desselben Modells**, keine unabhängigen
  Experten. Die Rollen mit eigenen Briefings, die getrennte Ideenfindung und die gemittelten
  Bewertungen verringern Gefälligkeitsurteile, verhindern sie aber nicht ganz.
- Ein hoher Score ist eine Entscheidungshilfe, **keine Erfolgsgarantie**. Marktzahlen ohne Quelle sind
  als Schätzung oder Hypothese gekennzeichnet.
- Ohne Web-Werkzeug findet keine Recherche statt. Das sagen die Briefings dann ausdrücklich.

## Lizenz

MIT, siehe [`LICENSE`](LICENSE). Der Skill basiert auf
[court](https://github.com/alexyc9381/court-skill) © 2026 Alex Chen, MIT.
