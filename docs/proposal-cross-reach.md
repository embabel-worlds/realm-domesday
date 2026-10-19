# Proposal: Domesday text, Little Domesday, and data from outside 1086

Status: proposal, 2026-10-18. Every source below was fetched or queried before it was listed;
where a fact could not be checked it says so.

## Summary

Four additions, in order of value:

1. **The Domesday text, searchable.** Hull has published the Phillimore translation as a plain-text
   file under the same CC BY-NC-SA licence as the figures this realm already ships: 33 counties,
   18,779 entries, each headed by its Phillimore reference (`WOR 15,8`), so it joins to our
   entries one to one. It lands through `lane: documents` with no handler code.
2. **Little Domesday.** The same Hull text covers Essex, Norfolk and Suffolk, which have no entries
   here today, and Hull's current collection lists the Little Domesday statistics tables beside it.
   Little Domesday records people in 1066 as well as 1086, so "were there more slaves before or
   after the Conquest" becomes answerable for East Anglia.
3. **An identity spine through Wikidata (CC0).** 13,232 Wikidata items carry an Open Domesday
   settlement id; 8,325 of our places (58%) reach one, and through it Wikipedia, GeoNames, the
   current civil parish code, Vision of Britain, OpenStreetMap and the Manorial Documents Register.
   A spatial join on our lat/lng gives a modern parish to nearly every other place.
4. **Then and now.** With a parish code and a point, a Domesday place meets the 2021 Census, the
   2025 indices of deprivation, the National Heritage List, mills c.1800 and c.1900, ancient
   woodland and land quality — and the appliance's UK places realm, which already joins 23 types
   (house prices, density, income, crime, flood) to a place by its coordinates.

## 1. The text

| | |
|---|---|
| Source | Hull, *Domesday text translation*, digitalcollections.hull.ac.uk (dataset h989r385x; file h989r387g, 7.4 MB, Latin-1, CRLF) |
| Licence | CC BY-NC-SA 2.0 UK, stated on the item record |
| Coverage | 33 counties including Little Domesday; **Yorkshire omitted** "for copyright reasons" |
| Key | Each entry opens `CODE chapter,section` — our `ref` |
| Quality | Typed, not OCR. Editorial markup to keep or strip: `^[Dover]^`, `{ora}`, `<of Farningham>`, `[* In EASTRY Lathe *]` |

**Shape.** `scripts/build.sh` downloads the file; the build adds `text` to each `DomesdayEntry`
(the entry's own words, markup normalised) and writes nothing else new. A `sources.yml` declares
one document per county fief — `lane: documents`, `from.cypher` over the entries, `uri`
`domesday://phillimore/WOR/15`, markdown with one heading per entry, `sync: on-install`. Search and
`RELEVANT_TO` then come from the host. Embeddings are computed on the appliance, never shipped:
vectors over NC-SA text are best treated as derived material.

**Secondary text.** Hull also publishes the Phillimore county introductions, notes and
appendices. Two items' licences were checked (BY-NC-SA 2.0 UK); each must be checked before it is
used.

**Yorkshire.** The only open translation is Bawdwen's *Dom Boc* (1809, public domain), with
long-s OCR ("fhillings") and no Phillimore numbering — it joins by place and holder, not by
reference. Worth doing after the rest, flagged as a different translation.

**Considered and set aside.** Farley's 1783 Latin: public domain, OCR unusable. Victoria County
History translations on British History Online: BHO's terms forbid storing them in any retrieval
system. The archive.org VCH volumes are public domain in the US but the Norfolk translator's
UK copyright likely runs to 2031. Exon Domesday (Thorn): excellent, cross-referenced to Great
Domesday, but CC BY-NC-ND — chunking is arguably a derivative. Alecto/Penguin and TNA's
translation: copyright. An unlicensed Phillimore upload on archive.org: not used.

## 2. Little Domesday

Explorer 1.1, our source, has no Essex, Norfolk or Suffolk entries. Hull's 2025 collection lists
Statistics, Places, Names, Claims and Boroughs databases "for about 21,000 holdings". **Not yet
downloaded** — the first task is to confirm they carry the East Anglian entries and their coding
matches Explorer's. If they do, the same build adds ~4,400 entries and the realm stops refusing
Essex. Open Domesday also holds them, but only as scraped pages; Hull's tables are the source.

## 3. The identity spine

| Bridge | Adds | Licence | Places reached |
|---|---|---|---|
| Hull `placeId` = Open Domesday place id | Open Domesday URL (`SY2998/axminster`), the key Wikidata uses | — | 36/36 sampled identical; 12,733 map to a URL |
| Wikidata P3118 | QID, then everything below | CC0 | 8,325 (58%) |
| ↳ English Wikipedia | article | CC BY-SA | 8,187 |
| ↳ ONS GSS code (P836) | civil parish (2011 vintage) | OGL | 5,809 |
| ↳ GeoNames, OSM, Vision of Britain | gazetteers, boundaries, census units | CC BY / ODbL / mixed | 7,690 / 5,737 / 7,768 |
| ↳ Manorial Documents Register (P3029) | where a manor's records are held | CC0 id | 4,855 |
| ONS Index of Place Names 2024, or point-in-polygon on Dec 2023 parishes | parish, ward, district codes | OGL | 9,719 by name ≤ 2 km; ~all 13,068 gridded places by point |

Shipped as reference data (CC0 and OGL ship freely), as properties on `DomesdayPlace`:
`wikidataId`, `wikipedia`, `parishCode`, `parishName`, `districtCode`, `geonamesId`. One SPARQL
query and one boundary file; no runtime dependency.

**People are the hard half.** Wikidata has 28 Open Domesday person ids, at least one on the wrong
man. Our person records are name strings per county; PASE Domesday has 17,499 identified
individuals keyed by county and Phillimore reference — exactly the join we need — but its terms
allow individual non-commercial use only, anything else by written consent of its directors.
Proposed: ask PASE; meanwhile hand-curate the ~150 greatest tenants-in-chief to Wikidata QIDs
(expect ~90% with Wikipedia, ~50% with ODNB), since automated name search picked the wrong Roger de
Lacy, Lanfranc and Gilbert de Gant.

## 4. Then and now

Ranked by value for effort. Each is OGL or CC BY unless marked.

| Dataset | Join | Question it answers |
|---|---|---|
| **Census 2021 parish profiles** (Nomis PP001–PP014) | parish code | "Abberley had 32 households in 1086; how many now?" — households against households, never people |
| **The appliance's UK places realm** | a Domesday place opens a watched place at its lat/lng | house prices, density, income, deprivation, crime, flood alerts — 23 types already joined there |
| **Indices of Deprivation 2025** | point → LSOA | "were the richest manors of 1086 the affluent places of 2025?" |
| **National Heritage List** (Historic England) | spatial | listed churches, scheduled mottes and deserted villages at Domesday places; name-classified, so mills under-count |
| **Mills of Britain** (NLS, CC BY 4.0) | spatial, buffered | mills in 1086, c.1800 (23,621), c.1900 |
| **Ancient woodland; Agricultural Land Classification** (Natural England) | per point | Domesday woodland against surviving ancient wood; plough teams against land grade |
| **Markets and Fairs to 1516** (Letters) | county + name, or grid | first record, chartered markets, 1334 lay subsidy values for ~2,400 places. **No licence stated** — ask before shipping |

**Mechanism, to settle before building.** The census, deprivation and heritage figures can ship
as reference keyed by parish code or fetched per point by a producer. The UK places bridge is a
cross-realm join on place: the realm declares the spine, and the question is whether a Domesday
place can open a watched place by coordinates without the user adding it by hand.

**Non-commercial, possible later in their own files:** Hearth Tax Digital (1660s–80s, CC BY-NC),
Inquisitions Post Mortem 1399–1447 (CC BY-NC-SA). **Not usable:** the Gatehouse castles gazetteer
forbids commercial use; parish populations 1801–1911 need a UK Data Service login; the 1334 and
1377 subsidies, the 1291 Taxatio and the Valor (1535) have no open digital release yet.

## Traps

- **A vill is not a parish.** A parish may hold several vills; sum entries per place and places per
  parish before comparing.
- **Different years count different things.** Domesday heads of household; 1377 people over 14;
  hearth tax hearths; 2021 usual residents. Compare households with households.
- **Money is not one axis.** A manor's annual value, a tax on movables and church income differ.
- **Boundaries moved** (1894, 1974): join on points and codes, never on county names. Parish codes
  differ by vintage (Wikidata 2011, Nomis 2022).
- **Open Domesday's entry ids drift from Hull's** by one in places — join entries on Phillimore
  reference, places on id.
- **Wikidata duplicates.** Settlement and manor-estate items share P3118 values; filter by type.

## Licence posture

The realm's data is already CC BY-NC-SA (Hull). The text adds nothing new to that. Wikidata,
ONS, OS, Natural England and Historic England data is CC0 or OGL and ships freely beside it.
Anything NC-only stays in its own file with its own licence line. An appliance sold commercially
running this realm already raises the non-commercial question; none of this proposal changes it.

## Proposed order

1. Text and Little Domesday together — one source, one build change, the largest gain.
2. The Wikidata and parish spine — one query, one boundary file.
3. Census 2021, deprivation, heritage, and the UK places bridge — "then and now" views and battery
   questions with literal answers.
4. Mills, woodland, land quality, markets — thematic views.
5. People: PASE by consent; hand-curated magnates meanwhile.
