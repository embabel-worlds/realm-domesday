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
- **People are one record per name per county.** To ask about a person across England, match by
  name and aggregate — `DomesdayPersonSummary` and `DomesdayPersonHoldings` do. Find the exact name
  with `DomesdayPersonSearch` first: Hull writes `Bishop Odo/of Bayeux`, `Count Robert/of Mortain`,
  `Earl Roger (of Shrewsbury)`, `King William`, `King Edward`, `Earl Harold`, `Queen Edith`.
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

- **Little Domesday: Essex, Norfolk, Suffolk.** Their places and people are listed; their entries,
  and so every figure, are not. A question about population or value there is unanswerable from
  this realm — say so.
- **The text.** No running text of Domesday is stored, only the figures and names coded from it.
  Quotations are not available.
- **Individuals below the landholders.** Villagers and slaves are counts; none is named.
- **Anything after 1086, or modern population.** Domesday is a survey of 1066 and 1086.
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
| richest manors | `DomesdayRichestManors {county}` |
| biggest falls / rises in value | `DomesdayValueChange {direction, county}` |
| the Harrying of the North / waste | `DomesdayWaste {county}` |
| castles, markets, churches | `DomesdayFeature {feature, county}` |
| what was near here | `DomesdayPlacesNear {lat, lng, km}` |

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
RETURN p.countyName AS county, e.ref AS ref, collect(DISTINCT l.name) AS lord1066, collect(DISTINCT t.name) AS tenantInChief

// mills in each county
MATCH (e:DomesdayEntry) RETURN e.countyName AS county, sum(e.mills) AS mills ORDER BY mills DESC
```
