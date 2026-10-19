# people-wikidata.csv

This file links the people and institutions who matter most in Domesday to
their Wikidata items. Each row maps a `canonicalName` from `DomesdayPerson`
(reference/04-people-*.yml) to a Wikidata QID. Every link was chosen and
checked by hand. Where no item fits, or the name could belong to several
people, the QID is left empty and the note says why. A wrong link is worse
than none.

## Who is in it

The selection is computed from the reference files, not chosen by taste.

- **Tenants-in-chief, 1086.** The 150 largest holders, ranked by total
  `value1086` (in pence). The total is summed over every entry with a
  `TENANT_IN_CHIEF` relation and grouped by `canonicalName`. Hull keeps one
  record per name per county, so grouping by name merges a baron's counties
  into one figure. The King and institutions (sees, abbeys, canons) are
  included.
- **Lords, 1066.** The 60 largest holders by total `value1066` over
  `LORD_1066` relations. Fifteen further named magnates come from ranks
  61–200: earls, countesses, bishops, Asgar the constable, Engelric, and Ulf (because he was asked about). They
  sit outside the top 60 only because the entry files cover Great Domesday
  alone. Little Domesday (Essex, Norfolk, Suffolk) is absent, and that is
  where much of Asgar's and Engelric's land lay.
- **Women tenants-in-chief.** Every name with a `female` record that holds as
  tenant-in-chief, plus Christina. Hull's data marks her gender as male, but
  she is the sister of Edgar Ætheling.

`role` is `tenant-in-chief 1086`, `lord 1066` or `both`. A row is `both` when
the name is in both selections, which is the case for most of the great
churches.

## Columns

| column | meaning |
|---|---|
| canonicalName | the join key to `DomesdayPerson.canonicalName` |
| role | which selection the row came from |
| qid | the Wikidata item; empty when unlinked |
| label, description | the item's Wikidata label and English description at the time of curation. The label falls back to another language when the item has no English one |
| enwiki | the English Wikipedia article linked from the item, if there is one |
| odnbId | the Oxford DNB id (Wikidata P1415), if recorded |
| birthYear, deathYear | Wikidata's values, given only where the precision is a year. Some are known to be wrong; the note says so where it matters |
| confidence | `high` or `medium`. Unlinked rows leave it empty |
| note | why this is the right item, which nearby wrong item it is not, or why the row is unlinked |

## Method

1. Compute the selections above from reference/04 and reference/05 with
   PyYAML.
2. For each name, work out who Hull means (from the editorial suffixes,
   counties and holdings) and write the English Wikipedia title of that
   person or house.
3. Resolve titles to QIDs through English Wikipedia's `pageprops`, following
   redirects. A redirect to a section of another article is rejected, as with
   *Ilbert de Lacy*, which redirects to the family article.
4. Where English Wikipedia has nothing, search Wikidata
   (`list=search`, and SPARQL at query.wikidata.org for people whose
   allegiance is William I).
5. Check every candidate against its description, its dates, and the lede of
   its Wikipedia article: English, or Spanish where that is the only one.
   People must have died around 1066–1130 (or held land TRE). Sees must be
   the right see in 1086, and abbeys the right house.

## Conventions

- **Sees** link to Wikidata's pre-Reformation diocese items, such as
  *Roman Catholic Diocese of Lincoln (England)* or *Ancient Diocese of Wells
  (909–1088)*. Those items are the bishopric that held the land in 1086. The
  Church of England successor's QID is given in the note. The bishop himself,
  where Hull records him by name (Walkelin, Remigius, Osbern, Lanfranc,
  Thomas, Wulfstan), is a separate row linked to the person.
- **Abbeys** link to the monastery item where Wikidata has one: Ely Abbey,
  St Albans Abbey, Gloucester Abbey, New Minster. Not the later cathedral.
  Where the only item is the surviving church building (Peterborough,
  Sherborne, Romsey, Pershore, Bath, Milton), the link is `medium`.
- **Items backed only by a Spanish Wikipedia article.** Several Anglo-Norman
  tenants-in-chief have items whose only support is a recent Spanish
  Wikipedia article, often with no English label. They are linked `medium`
  when the article's holdings match Hull's counties. Their genealogies are
  not relied on.
- **Wikidata duplicates** (Ilbert de Lacy, Hugh fitzBaldric) are noted. The
  item with the better sitelinks is used.

## Wrong-man traps avoided

These candidate items share or closely resemble a Domesday name but are the
wrong person or house:

- Ralph de Mortimer → Q3419321 (fl. 1080–1104), not Q7288322 (d. 1246).
- Hugh de Beauchamp → Q18730449 (the Bedford sheriff), not Q16197364
  (Abergavenny, d. 1173).
- Nigel d'Aubigny → Q7032742 (of Cainhoe), not Q7032731 (d. 1129).
- William de Mohun → Q6837633 (d. c.1100), not Q3007349 (earl of Somerset).
- Gilbert of Ghent → Q16198957 (d. 1095), not his grandson the earl of
  Lincoln.
- Roger de Lacy → Q17099639 (d. after 1106), not the Roger de Lacy who died
  in 1211.
- Robert Gernon → the Norman lord, not the American judge whom English
  Wikipedia returns for the name.
- Guy de Craon → the 11th-century baron, not Q81069674 (1158–1205).
- Rothais → Rohese Giffard, not Rohese de Clare.
- The Devon tenant-in-chief "Godiva" is not Lady Godiva. Countess Godiva,
  wife of Earl Leofric, is linked separately.

## What is not linked

- **Common forenames among the 1066 lords**, such as Godric, Alwin, Aelfric,
  Siward, Edric, Ulf and Brictric. Hull gathers many different thegns under
  each name, so no single person can be linked.
- **Groups and blanks**, such as "thanes, two" and "_".
- **Named people with no Wikidata item**, among them Robert fitz Gerold,
  Walter the Fleming, Mainou the Breton, Colswain, Mærleswein, Æthelmær Ator,
  Ingelric, Hawise wife of Hugh fitz Grip and Gytha wife of Earl Ralph.
- **Roger Arundel.** The items that exist are bare stubs and cannot be
  verified.
- **The canons of Rouen.** Hull combines two houses, so no single item fits.
- **Most women tenants-in-chief.** They are recorded only as someone's wife,
  mother or a nun, or by a name nothing else identifies.

## Sources and licence

- **Wikidata** (https://www.wikidata.org). The QIDs, labels, descriptions,
  dates and ODNB ids are Wikidata content, released under CC0. They ship
  freely with this realm.
- **English and Spanish Wikipedia** were read to verify identity. No text
  from them is reproduced.
- **The canonicalName values and the value rankings** derive from the Hull
  Domesday Explorer database (J.J.N. Palmer and the University of Hull,
  CC BY-NC-SA). They are subject to the terms in ../DATA-LICENSE.md, like the
  rest of the reference data.

Curated 2026-10-18. Wikidata changes. Items may be merged, enriched or newly
created, so unlinked names deserve a fresh look from time to time, and a
merged QID will redirect.
