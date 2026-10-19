# realm-domesday

Domesday Book as a graph: the survey of England of 1086, entry by entry, with what it says, who
held what before and after the Conquest, and where each place is today. Built from the Hull
Domesday Project's database and its transcription of the Phillimore translation, joined to the
2021 census, the 2025 indices of deprivation, Wikidata and Wikipedia.

It is meant to be useful — to historians checking a figure against its folio, to students asking
who replaced whom, to anyone wondering what their village was in 1086 — and every answer carries
the entry it came from.

| | |
|---|---|
| Entries | 18,174 of Great Domesday from Hull's coded database, and 4,397 of Little Domesday (Essex, Norfolk, Suffolk) parsed from the translation — each with its figures, its people by role, and (all but Yorkshire) its text |
| Places | 14,334, of which 13,068 are located; each in its parish and neighbourhood today |
| People and institutions | 14,042 — one record per name per county, as Hull indexes them; 168 great landholders linked by hand to Wikidata |
| Hundreds, counties | 846 (with which border which), 34 |
| Today | 7,641 parishes with Census 2021 figures; 5,329 neighbourhoods with the 2025 deprivation indices |

**Both books.** Great Domesday comes from Hull's coded database.

Little Domesday (Essex, Norfolk, Suffolk) is missing from those tables. Its entries are therefore
parsed from Hull's transcription of the translation (`scripts/little_domesday.py`), and every entry
says which way it came (`figuresSource`). Checked against Hull's own hand-coded figures, the parsed
ones agree at 85–100% on most fields and 76–84% on plough teams (`tests/check_little_domesday.py`).

Little Domesday alone counts people and stock in 1066 too. So "were there more slaves before or
after the Conquest?" has an answer, for East Anglia.

## Ask it

- *Who held Abberley before 1066, and who succeeded him?* — Wulfmer; Ralph of Tosny, his successor
  across Worcestershire (`DomesdayAntecessors`).
- *What does Domesday say about Leofwin the forester?* — one line, in Neatham: a virgate he held
  "has been taken from this manor, so the Hundred state" (`DomesdayWhatItSaysAbout`).
- *Where does it mention eels?* — 42 entries in Cambridgeshire alone; Doddington rendered 27,150
  (`DomesdayTextMentions`, `DomesdayExtractFromText`).
- *How far did the devastation reach?* — 70 hundreds, the Welsh March and the north
  (`DomesdayDevastation`).
- *Were the rich places of 1086 the comfortable places of today?* — no: r = 0.03 across 8,479
  places (`DomesdayRichThenRichNow`).
- *Which villages have shrunk since Domesday?* — Waddingworth, 60 households then and 3 now
  (`DomesdayGrowth`).

## The graph

```
DomesdayCounty ◀─IN─ DomesdayHundred ◀─IN─ DomesdayPlace ◀─DESCRIBES/INCLUDES─ DomesdayEntry ─IN─▶ DomesdayCounty
                     DomesdayHundred ◀────────────── IN_HUNDRED ─────────────── DomesdayEntry
                     DomesdayHundred ─NEIGHBOURS─ DomesdayHundred
DomesdayEntry ─[LORD_1066 | TENANT_IN_CHIEF | TENANT_1086 | …]─▶ DomesdayPerson
DomesdayPlace ─NOW_IN─▶ ModernParish          DomesdayPlace ─NOW_IN_NEIGHBOURHOOD─▶ ModernNeighbourhood
DomesdayPerson / DomesdayPlace ─WIKIPEDIA─▶ DomesdayWikipedia                     (fetched live)
```

An **entry** is one section of the Phillimore edition (`Worcestershire 15,8`). It carries:

- the figures: households by class, plough teams, ploughlands, tax, value in 1066, when acquired
  and in 1086 (in pence), mills, meadow, woodland, livestock, church, castle, market and waste;
- `text`: what it says, as a reading text;
- `textEdition`: Hull's edition with its apparatus.

Who held it is an edge by role, from Hull's coding.

## What you get

- **49 views** in `views/`:
  - finding and dossiers (`domesday.yml`);
  - the Conquest and the economy, measured across the survey (`analysis.yml`), including a regression of value on resources;
  - the rules' conclusions (`derived.yml`);
  - the text, exact and by meaning, extraction, disputes, waste, and Wikipedia (`text.yml`);
  - then and now (`then-and-now.yml`), including live district figures from realm-uk-streets when it is installed.
- **4 DERIVE rule sets** in `rules/`:
  - who SUCCEEDED whom;
  - who was whose man (`MAN_OF`);
  - which hundreds were devastated, traced outward from the worst;
  - who held land on both sides of the Conquest.
- **The text as documents** (`sources.yml`): one per county chapter, embedded on install, searchable by meaning.
- **An app**, `apps/domesday.html`, at `/apps/realm-domesday/domesday.html`:
  - a map of every place, and search;
  - place, entry, person and county pages, with folio links, then-and-now, the text and Wikipedia;
  - tabs for the counties, the Conquest, wealth and waste, Studies and The text;
  - an Ask box;
  - its own "How it works" page.
- **A skill** (`skills/domesday`), a **focus** (`/focus domesday`), and type-level `examples:` for asking in words.

## How good is it?

**The figures** are parsed (`scripts/figures.py`) from Hull's coding of the Phillimore text.
`tests/check_against_opendomesday.py` reconciles them field by field against Open Domesday, whose
figures were coded by hand at Hull. On 450 manors (300 unseen while the parser was tuned):

| Field | Agreement | | Field | Agreement |
|---|---|---|---|---|
| villagers | 98.7% | | value in 1066 | 94.1% |
| smallholders | 98.9% | | value in 1086 | 91.3% |
| slaves | 97.7% | | men's plough teams | 88.4% |
| meadow | 97.7% | | tax (geld units) | 83.9% |
| mills | 97.8% | | lord's plough teams | 81.2% |

**The text** is Hull's transcription, joined to the entries by Phillimore reference: 14,377 entries,
every non-Yorkshire manor and borough entry.

**Hull's apparatus** is documented on `textEdition` and kept there verbatim. Its marks, read from
the Explorer's help file and matched span by span against Hull's coding:

| Mark | Meaning |
|---|---|
| `[= =]` | fief heading |
| `?M?` | marginalia |
| `<210c>` | folio |
| `[* *]` | identification |
| `^[ ]^` | implied meaning |
| `{ }` | Latin left as written |
| `{{ }}` | struck out |

**The links to today** are point tests on the centre of each place's 1 km grid square:

- The parish agrees with Wikidata's 90% of the time.
- A vill near a boundary can land in its neighbour.
- `likelyLost` is a candidate, never a finding.

**The rules** are conclusions under stated thresholds; their descriptions give them. Two examples:

- A successor holds half of a lord's entries in the county.
- A survivor is the same name in the same county, so a bare name may be two men.

## Building

`reference/` is generated; do not edit it by hand.

```bash
./scripts/build.sh
```

The build:

- downloads the Explorer v1.1 database and Hull's translation;
- builds the crosswalk to today (`scripts/build_crosswalk.py`);
- writes `reference/`.

It needs curl, unzip, git, mvn, Java 17+ and Python 3.10+. The Explorer's tables are Paradox, read
with [pdxreader](https://github.com/teverett/paradoxReader), built from source at a pinned commit
until teverett/paradoxReader#171 is released. The appliance refuses a reference file over 3 MB, so
each list is written in parts of 2.5 MB.

## Testing

```bash
EMBABEL_AUTH='Bearer …' tests/verify.sh [base-url]     # everything below, in order
```

- `tests/test_views.py`: every view, with facts that must hold. Examples:
  - Abberley: 18 villagers, £10 10s, 32 households then and 288 now;
  - Wulfmer → Ralph of Tosny;
  - Odo's Wikipedia article.
- `tests/ask_battery.py` + `tests/questions*.yml`: questions in words through `kg_ask`, reconciled against the views and against literal facts from Open Domesday and the historical record. Each also has an adversarial half, checked for invented properties.
- `tests/browser/live.mjs`: the app in a real browser against the appliance.
- `tests/browser/stub.mjs`: the app against captured envelopes, with forced empty, failed, slow and hostile cases.
- `tests/check_against_opendomesday.py`: the parser against Open Domesday.

## Licence

Code: Apache 2.0 (`LICENSE`). Data: CC BY-NC-SA (Hull: figures and translation), OGL v3.0 (ONS,
MHCLG), CC0 (Wikidata) — see `DATA-LICENSE.md`.
