# realm-domesday

Domesday Book as a graph: the survey of England of 1086, entry by entry, from the Hull Domesday
Project's database. Install it and the world can answer "who held Abberley before the Conquest?",
"which county lost most value after 1066?", "where did Earl Harold's land go?" — by saved view, in
the app, or in plain English.

| | |
|---|---|
| Places | 14,776, of which 13,486 are located (OS grid reference → latitude/longitude) |
| People and institutions | 14,042 — one record per name per county, as Hull indexes them |
| Entries | 18,174 — every entry of Great Domesday, with its figures and its people by role |
| Hundreds, counties | 973, 34 |

**Great Domesday only.** Essex, Norfolk and Suffolk are in Little Domesday, which the Domesday
Explorer does not hold: their places and people are here, their entries and figures are not.

## The graph

```
DomesdayCounty <-IN- DomesdayHundred <-IN- DomesdayPlace <-DESCRIBES/INCLUDES- DomesdayEntry -IN-> DomesdayCounty
DomesdayEntry -[LORD_1066 | OVERLORD_1066 | TENANT_IN_CHIEF | TENANT_1086 | SUBTENANT_1086 | ...]-> DomesdayPerson
```

An **entry** is one section of the Phillimore edition (`Worcestershire 15,8`) and carries the
figures: households by class, plough teams (the lord's and the men's), ploughlands, tax in geld
units, the annual value in 1066, when acquired and in 1086 (in pence), mills, meadow, woodland,
fisheries, livestock, and whether it mentions a church, a castle, a market or waste. Who held it is
an edge by role, from Hull's coding.

## What you get

- **21 views** (`views/domesday.yml`) — find a place or a person; a place's dossier; an entry in
  full; a person across England; the greatest landholders before and after the Conquest; who
  replaced whom; women landholders; county and hundred totals; the richest manors; the greatest
  falls and rises in value; waste; castles and markets; places near a point; a map layer.
- **An app**, `apps/domesday.html`, served at `/apps/realm-domesday/domesday.html`: a map of every
  place, search, place / entry / person / county pages with links to the folio in Open Domesday,
  the Conquest, wealth and waste, and an Ask box. It ships its own "How it works" page.
- **A skill** (`skills/domesday`) and a **focus** (`/focus domesday`) for asking in words, and
  type-level `examples:` that steer the text-to-Cypher generator.

## How good are the figures?

They are parsed (`scripts/figures.py`) from Hull's coding of the Phillimore text, which states them
in formulaic clauses ("8 villagers and 4 smallholders with 4 ploughs", "value before 1066 £7 now
£10 10s"). `tests/check_against_opendomesday.py` reconciles them field by field against Open
Domesday, whose figures were coded by hand at Hull. On 450 manors (2026-10-18; 300 unseen while the
parser was tuned):

| Field | Agreement | | Field | Agreement |
|---|---|---|---|---|
| villagers | 98.7% | | value in 1066 | 94.1% |
| smallholders | 98.9% | | value in 1086 | 91.3% |
| slaves | 97.7% | | men's plough teams | 88.4% |
| meadow | 97.7% | | tax (geld units) | 83.9% |
| mills | 97.8% | | lord's plough teams | 81.2% |

The lord's plough teams are phrased a dozen ways across the circuits, and Devon and Cornwall are
Phillimore's condensation of Exeter Domesday, whose split the text no longer carries. Every entry
cites its Phillimore reference, so any figure can be checked against the folio.

## Building the reference data

`reference/` is generated; do not edit it by hand.

```bash
./scripts/build.sh        # downloads the Explorer v1.1 database, converts, decodes, writes reference/
```

It needs curl, unzip, git, mvn, Java 17+ and Python 3.10+. The Explorer's tables are Paradox; they
are read with [pdxreader](https://github.com/teverett/paradoxReader), built from source at a
pinned commit until teverett/paradoxReader#171 — which fixes its number decoding and lost records —
is released. The Explorer's text store is undocumented; `scripts/decode_textbase.py` says what the
bytes turned out to be. No running text is written to `reference/`: it is Phillimore's
translation, not ours to republish.

The appliance refuses a reference file over 3 MB, so each list is written in parts of 2.5 MB.

## Testing

```bash
EMBABEL_AUTH='Bearer …' tests/verify.sh [base-url]     # everything below, in order
```

- `tests/test_views.py` — every view, defaults and varied parameters, with facts that must hold
  (Abberley: 18 villagers, £10 10s; King William heads 1086; Yorkshire heads the waste).
- `tests/ask_battery.py` + `tests/questions.yml` — questions in words through `kg_ask`, reconciled
  against the views, and an adversarial half (Little Domesday, the text, modern population, 1200)
  asked three times each and checked against the live schema for invented properties.
- `tests/browser/live.mjs` — the app in a real browser against the appliance.
- `tests/browser/stub.mjs` — the app against captured envelopes, with forced empty, failed, slow and
  hostile cases. Runs without an appliance.
- `tests/check_against_opendomesday.py` — the parser against Open Domesday (fetches politely, caches).

## Licence

Code: Apache 2.0 (`LICENSE`). Data: CC BY-NC-SA, Professor J.J.N. Palmer and the University of
Hull — see `DATA-LICENSE.md`.
