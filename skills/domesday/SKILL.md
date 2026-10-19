---
name: domesday
description: Answer questions about Domesday Book (1086) from realm-domesday — places, people, landholders before and after the Norman Conquest, population, plough teams, tax and values, mills, churches, castles and waste. Use when someone asks about Domesday, 1086, the Conquest's effect on land, a medieval English place or landholder, or "what was <place> like in 1086".
---

# Domesday Book, in this world

realm-domesday holds the Hull Domesday Project's coding of Great Domesday: every entry, every place
and every person it names. Prefer a saved view; write Cypher only when none fits. Every view starts
`Domesday` — run `view_run` with no arguments to list them.

## The model

```
DomesdayCounty <-IN- DomesdayHundred <-IN- DomesdayPlace <-DESCRIBES/INCLUDES- DomesdayEntry -IN-> DomesdayCounty
DomesdayEntry -[LORD_1066 | OVERLORD_1066 | TENANT_IN_CHIEF | TENANT_1086 | SUBTENANT_1086 | ...]-> DomesdayPerson
```

- **An entry is where the figures are.** Households, villagers, plough teams, value — all are
  properties of `DomesdayEntry`, never of a place. A place's figures are the sum over the entries
  that DESCRIBE it. A big place may have several entries, one per holder.
- **Who held it is an edge, by role.** "Who held X in 1066" = `LORD_1066`. "Who held X in 1086" =
  `TENANT_IN_CHIEF` (held of the king) and `TENANT_1086` (held of the tenant-in-chief, the man on the
  ground). "Who took over X's land" = the same entries' `LORD_1066` and `TENANT_IN_CHIEF`.
- **People are one record per name per county.** To ask about a person across England, match on
  `canonicalName` and aggregate by it — `DomesdayPersonSummary` and `DomesdayPersonHoldings` do.
  `name` keeps Hull's brackets for words it supplied, so one man is `Earl Harold`, `(Earl) Harold` and
  `{Earl} Harold`; grouping by `name` splits him three ways. Find the name with `DomesdayPersonSearch`
  first: `Bishop Odo/of Bayeux`, `Count Robert/of Mortain`, `Earl Roger of Shrewsbury`, `King William`.
- **A hundred's figures are its entries by `IN_HUNDRED`** (one edge per entry per hundred), filtered
  on the hundred's county. An entry points at its own county's hundred, so detached parts count with
  the hundred they belonged to (Oswaldslow, Worcestershire, reaches into Gloucestershire and
  Warwickshire). `DomesdayHundredSummary` does this.
- **Boroughs are not manors.** Shrewsbury, Oxford and the other towns are kind `urban`; "manor"
  questions filter `e.kind = 'manor'`.
- **Places recur.** There are several Abbertons and dozens of Nortons; always show the county.
  `DomesdayPlaceSearch` first, then `DomesdayPlaceEntries` with its `placeId`.

## Units — say them

- **Money is in PENCE.** £1 = 20s = 240d. `value1086 2520` is £10 10s. Views also return pounds.
- **Households, not people.** Domesday counts heads of household; historians multiply by four or
  five for a population, and that multiplier is an estimate, not data. Say so if you use it.
- **Geld units** are the tax assessment: hides, carucates (Danelaw) or sulungs (Kent), each one unit.
- **Ploughlands** are land for so many ploughs — capacity. **Plough teams** are the teams there.
- **An absent figure is not zero.** It means the entry does not state it. Sum only what is stated,
  and when comparing 1066 with 1086 compare only entries that state both (`DomesdayCountySummary`
  does: its `comparableEntries`).

## What is NOT here — refuse, do not invent

- **Little Domesday: Essex, Norfolk, Suffolk** IS here, but its figures are read from the
  translation by a parser (`figuresSource`), agreeing with Hull's hand-coded figures at 85–100% on
  most fields and 76–84% for plough teams — say so when a number turns on it. It alone counts people
  and stock in 1066 (`villagers1066`, `slaves1066` …), so a people comparison across the Conquest
  speaks for East Anglia, never for England.
- **The text** is stored for every county but Yorkshire (Hull's transcription omits it): an entry's
  `text` is the reading text, `textEdition` Hull's edition with its apparatus. Quote the text for
  what Domesday SAYS and the figures for what it COUNTS, and give the entry's ref with every quote.
- **Individuals below the landholders.** Villagers and slaves are counts; none is named.
- **Anything after 1086** is not in Domesday — but today IS in this realm, deliberately and apart:
  each place's parish and neighbourhood with the 2021 census and the 2025 deprivation indices
  (`ModernParish`, `ModernNeighbourhood`). Compare households with households, never Domesday
  households with modern residents.
- The figures are parsed from Hull's coding of the text and agree with Open Domesday's to 81–99% by
  field (lowest: the lord's plough teams). For one manor, show its figures and its reference
  (`Worcestershire 15,8`) so a reader can check it.

## Questions → views

| Asked | View |
|---|---|
| find a place / is X in Domesday | `DomesdayPlaceSearch {name}` |
| what was X like in 1086 / who held X | `DomesdayPlaceEntries {placeId}` |
| one entry in full | `DomesdayEntryDetail {entryId}` |
| find a person | `DomesdayPersonSearch {name}` |
| what did P hold / how rich was P | `DomesdayPersonHoldings {name}`, `DomesdayPersonSummary {name}` |
| richest men of 1086 / who gained from the Conquest | `DomesdayGreatestLandholders` |
| greatest English lords before 1066 | `DomesdayGreatestLords1066` |
| who replaced whom / where did Harold's land go | `DomesdayConquestTransfers {lord1066}` |
| women landholders | `DomesdayWomenLandholders` |
| county comparison, change since 1066, waste, mills | `DomesdayCountySummary` |
| hundreds of a county | `DomesdayHundredSummary {county}` |
| richest manors (boroughs are kind `urban`; `kind: all` for every entry) | `DomesdayRichestManors {county, kind}` |
| biggest falls / rises in value | `DomesdayValueChange {direction, county}` |
| the Harrying of the North / waste | `DomesdayWaste {county}` |
| castles, markets, churches | `DomesdayFeature {feature, county}` |
| what was near here | `DomesdayPlacesNear {lat, lng, km}` |
| who succeeded whom / P's antecessor | `DomesdayAntecessors {name}` |
| a lord's men / whose man was P | `DomesdayMenOf {name}` |
| English who kept their land | `DomesdayConquestSurvivors` |
| what became of the English lords | `DomesdayFateOfEnglishLords` |
| how far the devastation reached | `DomesdayDevastation {county}` |
| who held the land: King, Church, lay | `DomesdayWhoHeldTheLand {county}` |
| women's land 1066 vs 1086 | `DomesdayWomenBeforeAfter` |
| over- or under-valued manors / what drove value | `DomesdayValueAnomalies {county}` |
| understocked land / ploughs vs ploughlands | `DomesdayPloughStocking` |
| how scattered an estate was | `DomesdayFeeScatter` |
| where Domesday mentions a word (eels, salt, vineyard) | `DomesdayTextMentions {word, county}`, `DomesdayTextMentionsByCounty {word}` |
| find passages by meaning | `DomesdaySearchText {query}` (model calls) |
| what Domesday says about a person | `DomesdayWhatItSaysAbout {name}` (one model call) |
| renders the figures do not code | `DomesdayExtractFromText {word, what, county}` (one model call) |
| why land was waste | `DomesdayWhyWaste {county}` (one model call) |
| disputes, claims, seizures | `DomesdayDisputes {county}` |
| a person's Wikipedia article | `DomesdayPersonWikipedia {name}`; else `DomesdayWikipediaMentions {name}` (pages that only mention them) |
| a place's Wikipedia article | `DomesdayPlaceWikipedia {placeId}` |
| a place then and now | `DomesdayThenAndNow {placeId}` |
| a place today (pay, population, crime) | `DomesdayPlaceToday {placeId}` (needs realm-uk-streets) |
| grown most / shrunk since 1086 | `DomesdayGrowth {order}` |
| lost villages | `DomesdayLostVillages {county}` |
| were the rich places of 1086 rich now | `DomesdayRichThenRichNow {county}` |

County codes: BDF BRK BUK CAM CHS CON DBY DEV DOR ESS GLS HAM HEF HRT HUN KEN LEC LIN MDX NFK NTH
NTT OXF RUT SHR SOM STS SUF SUR SUS WAR WIL WOR YKS.

## Cypher, when no view fits

Label every node, alias every column, no UNION. Patterns:

```cypher
// total villagers in a county
MATCH (e:DomesdayEntry {county: 'WOR'}) RETURN sum(e.villagers) AS villagers

// who held a place in 1066 and 1086
MATCH (p:DomesdayPlace)<-[:DESCRIBES]-(e:DomesdayEntry)
WHERE toLower(p.name) = 'abberley'
OPTIONAL MATCH (e)-[:LORD_1066]->(l:DomesdayPerson)
OPTIONAL MATCH (e)-[:TENANT_IN_CHIEF]->(t:DomesdayPerson)
RETURN p.countyName AS county, e.ref AS ref, collect(DISTINCT l.canonicalName) AS lord1066, collect(DISTINCT t.canonicalName) AS tenantInChief

// mills in each county
MATCH (e:DomesdayEntry) RETURN e.countyName AS county, sum(e.mills) AS mills ORDER BY mills DESC
```
