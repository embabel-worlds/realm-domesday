# Data licence

The code in this repository is Apache 2.0 (`LICENSE`). The data is not: each source below keeps its
own licence, and a file under `reference/` carries the licence of what it was built from.

## Domesday — CC BY-NC-SA

The entries, places, people and figures (`reference/01-` to `05-`) are derived from the Hull
Domesday Project's database — the geocoded, coded Domesday of Professor J.J.N. Palmer and his team
at the University of Hull, published as the Domesday Explorer — and are licensed, as Hull licenses
it, under **Creative Commons Attribution-NonCommercial-ShareAlike** (CC BY-NC-SA).

- **Attribution:** Professor J.J.N. Palmer, George Slater and the University of Hull.
- **NonCommercial:** use it for anything that is not primarily for commercial advantage.
- **ShareAlike:** anything you build from this data carries the same licence.

The source is the Hull Domesday Project's own deposit:
<https://digitalcollections.hull.ac.uk/collections/3t945r28b>. The tables this realm reads come from
the Explorer's v1.1 update, published by the project at <https://www.domesdaybook.net/downloads>.

**The text.** Each entry's `text` and `textEdition` are Hull's electronic transcription of the
Phillimore translation (Phillimore, 1975–86; Little Domesday revised by Caroline and Frank Thorn),
deposited by Hull as *Domesday text translation*
(<https://digitalcollections.hull.ac.uk/concern/datasets/h989r385x>). Hull's collection licenses its
items under Creative Commons, "detailed with each item"; the licence shown for this item —
recorded as CC BY-NC-SA 2.0 UK: England and Wales — is **to be confirmed against the item page
before this text is published**. Hull's transcription omits Yorkshire for copyright reasons, and so
does this realm. The searchable documents built from the text (`sources.yml`) are made on the
appliance that installs the realm; no embeddings are shipped.

**Little Domesday.** The entries for Essex, Norfolk and Suffolk are parsed from that same text
(`scripts/little_domesday.py`), so they carry the text's licence and attribution.

## England today — Open Government Licence v3.0

`reference/00-modern-parishes-*` and `reference/00-modern-neighbourhoods-*`, and the parish,
district and neighbourhood codes on each place, are built by `scripts/build_crosswalk.py` from:

- Office for National Statistics: parish, local authority and LSOA boundaries and lookups (December
  2021/2022), and Census 2021 parish profiles via Nomis (PP001, PP002, PP012). *Source: Office for
  National Statistics licensed under the Open Government Licence v.3.0. Contains OS data © Crown
  copyright and database right 2022.*
- Ministry of Housing, Communities and Local Government: English Indices of Deprivation 2025 (OGL v3.0).
- ONS Index of Place Names 2024 and the 2021 Rural-Urban Classification (OGL v3.0).

<https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/>

## Links — CC0

The Wikidata ids on places and people, and the Wikipedia, GeoNames, Vision of Britain and Manorial
Documents Register ids reached through them, come from Wikidata, which is CC0. The people's links
in `data/people-wikidata.csv` were matched by hand; see `data/README-people-wikidata.md`.

## Fetched live, never stored

- **Wikipedia** article summaries and search results (CC BY-SA 4.0) are fetched when asked for,
  shown with their link, and not stored.
- **Today's district figures** (pay, population, claimants, crime, deprivation) come from
  realm-uk-streets when that realm is installed, under the licences it states.
