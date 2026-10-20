"""
Write reference/*.yml — the Domesday graph the appliance seeds — from the converted Explorer tables
and the decoded entries.

    County <-IN- Hundred <-IN- Place <-DESCRIBES/INCLUDES- Entry -IN-> County
                                                            |
                                                            +-LORD_1066 / TENANT_IN_CHIEF / ...-> Person

What is written, and what is not:

- Places, hundreds and counties are the Explorer's gazetteer, with the OS grid reference turned
  into latitude and longitude (OSGB36 to WGS84, by pyproj). Hull marks some references with a
  trailing * or !, which its help pages do not explain; the mark is kept as gridRefMark and the
  square is plotted all the same. "??" and "--" are no location.
- People are the Explorer's index of names, one record per name per county, as Hull keeps them.
  The same man holding in two counties is two records with the same name; Hull does not join them
  and this does not pretend to.
- Entries carry the figures parsed from their coded clauses (scripts/figures.py), and an edge to
  every person named in them, by role, from Hull's own coding.
- No running text is written. The Explorer's text is Phillimore's translation; the figures and the
  coding are facts about Domesday, the prose is not ours to republish.

Great Domesday only. The Explorer holds no entries for Essex, Norfolk and Suffolk (Little
Domesday); their places and people are listed, with no entries behind them.
"""
import collections
import csv
import json
import os
import re
import sys

import yaml
from pyproj import Transformer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figures  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'reference')

"""Claims and summary sections are parts of a county's text, not counties."""
SECTION_OF = {'HC': 'HUN', 'LC': 'LIN', 'YC': 'YKS', 'YS': 'YKS', 'YB': 'YKS'}
SECTION_NAME = {'HC': 'Huntingdonshire claims', 'LC': 'Lincolnshire claims', 'YC': 'Yorkshire claims',
                'YS': 'Yorkshire summary', 'YB': 'Bruce fief'}
SECTION_KIND = {'HC': 'claim', 'LC': 'claim', 'YC': 'claim', 'YS': 'summary'}
LITTLE_DOMESDAY = {'ESS', 'NFK', 'SUF'}

NEIGHBOUR_KM = 6


def neighbouring_hundreds(hundred_records, place_records):
    """
    Domesday gives no boundaries, so two hundreds are taken to border when some place in one lies
    within NEIGHBOUR_KM of some place in the other: a hundred is a cluster of vills, and its edge is
    where its vills give way to the next one's. Six kilometres spans the gap between neighbouring
    vills without reaching across a third hundred. Each pair is listed once, from the lower id.
    """
    import math
    points = collections.defaultdict(list)
    for r in place_records:
        d = r['data']
        if 'lat' in d and d.get('hundred'):
            points[f"{d['county']}:{d['hundred']}"].append((d['lat'], d['lng']))
    cell = NEIGHBOUR_KM / 111.0
    grid = collections.defaultdict(set)
    for hid, pts in points.items():
        for lat, lng in pts:
            grid[(int(lat / cell), int(lng / cell))].add(hid)
    pairs = set()
    for hid, pts in points.items():
        for lat, lng in pts:
            gy, gx = int(lat / cell), int(lng / cell)
            for dy in (-1, 0, 1):
                for dx in (-2, -1, 0, 1, 2):
                    for other in grid.get((gy + dy, gx + dx), ()):
                        if other <= hid or (hid, other) in pairs:
                            continue
                        if any(math.hypot((lat - la) * 111.0, (lng - ln) * 111.0 * math.cos(math.radians(lat)))
                               <= NEIGHBOUR_KM for la, ln in points[other]):
                            pairs.add((hid, other))
    by_hundred = collections.defaultdict(list)
    for a, b in sorted(pairs):
        by_hundred[a].append(b)
    return [by_hundred.get(r['data']['hundredId'], []) for r in hundred_records]


def translation(cache):
    """
    Hull's transcription of the Phillimore translation (CC BY-NC-SA 2.0 UK, the same terms as the
    figures), keyed (county code, Phillimore number) exactly as the entries are. Kept verbatim,
    Hull's editorial marks and all, so a reader sees what Hull published; only the typesetter's line
    wrapping is undone. Hull omits Yorkshire, so its entries have no text.
    """
    path = os.path.join(cache, 'hull_translation.txt')
    if not os.path.exists(path):
        print('  no translation in the cache: entries carry no text')
        return {}
    raw = open(path, 'rb').read().decode('latin-1').replace('\r', '')
    heads = list(re.finditer(r'(?m)^([A-Z]{3}) (\S+)\s*$', raw))
    texts = {}
    for i, h in enumerate(heads):
        body = raw[h.end():heads[i + 1].start() if i + 1 < len(heads) else len(raw)]
        text = re.sub(r'\s+', ' ', body.replace('\x1a', '')).strip()
        if text:
            texts[(h.group(1), h.group(2))] = text
    return texts


"""
What scripts/build_crosswalk.py found for each place, and how each column is typed. Every column
is OGL (ONS, OS) or CC0 (Wikidata) — see .cache/crosswalk/SOURCES.md, which DATA-LICENSE.md repeats.
"""
PLACE_LINK_FIELDS = {
    'openDomesdayPath': 'string', 'wikidataId': 'string', 'wikipedia': 'string', 'geonamesId': 'string',
    'visionOfBritainPlaceId': 'string', 'manorialDocumentsRegisterId': 'string',
    'parishCode': 'string', 'parishName': 'string', 'ladCode': 'string', 'ladName': 'string', 'lsoa21Code': 'string',
    'modernPlaceName': 'string', 'modernPlaceDistanceKm': 'number', 'likelyLost': 'boolean',
}
MODERN_HEADER = """# {what}
# Generated by scripts/build_crosswalk.py and scripts/build_reference.py — do not edit by hand.
# Source: Office for National Statistics licensed under the Open Government Licence v.3.0;
# Ministry of Housing, Communities and Local Government, English Indices of Deprivation 2025, OGL v3.0.
# Contains OS data (c) Crown copyright and database right 2022. See DATA-LICENSE.md.
"""


def place_links(cache):
    """
    The crosswalk to today, when it has been built: places keyed by Hull id, and the parishes and
    neighbourhoods they fall in as reference records of their own. Without it the realm still builds,
    with no modern links.
    """
    folder = os.path.join(cache, 'crosswalk')
    out = {'places': {}, 'parishes': set(), 'lsoas': set(), 'parish_records': [], 'lsoa_records': []}
    if not os.path.exists(os.path.join(folder, 'place_links.csv')):
        print('  no crosswalk in the cache: places carry no modern links')
        return out
    with open(os.path.join(folder, 'place_links.csv'), encoding='utf-8') as f:
        out['places'] = {r['placeId']: r for r in csv.DictReader(f)}
    ints = {'usualResidents2021', 'households2021', 'aged0to15', 'aged16to64', 'aged65plus', 'domesdayPlaces',
            'imd2025Rank', 'imd2025Decile', 'incomeDecile2025', 'employmentDecile2025'}
    floats = {'areaHectares', 'residentsPerHectare'}
    def typed(r, skip):
        return {k: (int(v) if k in ints else float(v) if k in floats else v)
                for k, v in r.items() if v not in (None, '') and k not in skip}
    with open(os.path.join(folder, 'parishes.csv'), encoding='utf-8') as f:
        for r in csv.DictReader(f):
            out['parishes'].add(r['parishCode'])
            out['parish_records'].append({'type': 'ModernParish', 'data': typed(r, set())})
    with open(os.path.join(folder, 'lsoa.csv'), encoding='utf-8') as f:
        for r in csv.DictReader(f):
            out['lsoas'].add(r['lsoa21Code'])
            out['lsoa_records'].append({'type': 'ModernNeighbourhood', 'data': typed(r, {'ladCode2024'})})
    return out


LITTLE_ROLE = {'SUBTENANT_1086': 'TENANT_1086'}
LITTLE_DOMESDAY_ID_BASE = 200000


def little_domesday(cache, texts, canonical, places_by_id, hundred_ids):
    """
    Essex, Norfolk and Suffolk — Little Domesday — which the Explorer's tables do not hold. Their
    entries are built by scripts/little_domesday.py from Hull's transcription of the translation,
    so their figures are PARSED FROM THE TEXT (figuresSource), not Hull's coding, and agree with
    Hull's hand-coded figures at 85-100% on most fields (tests/check_little_domesday.py). The
    tenant-in-chief is Hull's index; the lord of 1066 and the 1086 tenant are read from "held" and
    "holds" in the text. Little Domesday records 1066 and when-acquired figures too, carried as
    <figure>1066 and <figure>Later. A "holds from" reading is the 1086 tenant, TENANT_1086, as it is
    in Great Domesday.
    """
    path = os.path.join(cache, 'little_domesday.json')
    if not os.path.exists(path):
        print('  no Little Domesday in the cache: Essex, Norfolk and Suffolk have no entries')
        return {}, []
    source = json.load(open(path, encoding='utf-8'))
    out, figures_out = collections.defaultdict(list), []
    for i, e in enumerate(source['entries']):
        county = e['county']
        data = {k: v for k, v in e.items() if k not in ('placeRefs', 'people', 'name', 'hundred')}
        # A number, like the Explorer's entry ids, so links and routes treat both books alike; in the
        # parser's own order, which follows the text, so a rebuild keeps every id.
        data['entryId'] = str(LITTLE_DOMESDAY_ID_BASE + i)
        # Little Domesday's counts for 1066 and for when acquired go on figure nodes of their own: on
        # the entry, sixty `<figure>1066` properties beside the 1086 ones invite a query to read the
        # wrong year. value1066 and valueLater stay, as every entry in both books has them.
        moments = {'1066': {}, 'Later': {}}
        for k in list(data):
            m = re.fullmatch(r'(.+?)(1066|Later)', k)
            if m and k not in ('value1066', 'valueLater'):
                moments[m.group(2)][m.group(1)] = data.pop(k)
        data['figuresSource'] = 'parsed from the translation'
        if (county, e['phillimore']) in texts:
            data['textEdition'] = texts[(county, e['phillimore'])]
            data['text'] = reading_text(data['textEdition'])
        data['name'] = e.get('name') or data['ref']
        relations = [{'predicate': 'IN', 'to': {'type': 'DomesdayCounty', 'code': county}}]
        seen = set()
        for r in e.get('placeRefs', []):
            pid = canonical.get(r['placeId'], r['placeId'])
            if pid not in places_by_id or (r['predicate'], pid) in seen:
                continue
            seen.add((r['predicate'], pid))
            relations.append({'predicate': r['predicate'], 'to': {'type': 'DomesdayPlace', 'placeId': pid}})
            place = places_by_id[pid]
            if r['predicate'] == 'DESCRIBES' and place.get('hundred'):
                hundred = f"{county}:{place['hundred']}"
                if hundred not in hundred_ids:
                    hundred = f"{place['county']}:{place['hundred']}"
                if hundred in hundred_ids and ('IN_HUNDRED', hundred) not in seen:
                    seen.add(('IN_HUNDRED', hundred))
                    relations.append({'predicate': 'IN_HUNDRED', 'to': {'type': 'DomesdayHundred', 'hundredId': hundred}})
        for person in e.get('people', []):
            predicate = LITTLE_ROLE.get(person['predicate'], person['predicate'])
            if (predicate, person['personId']) not in seen:
                seen.add((predicate, person['personId']))
                relations.append({'predicate': predicate, 'to': {'type': 'DomesdayPerson', 'personId': person['personId']}})
        for moment, figures_then in moments.items():
            if figures_then:
                fid = f"{data['entryId']}:{moment.lower()}"
                figures_out.append({'type': 'DomesdayFigures', 'data': {
                    'figuresId': fid, 'moment': '1066' if moment == '1066' else 'when acquired', 'ref': data['ref'], **figures_then}})
                relations.append({'predicate': 'FIGURES_1066' if moment == '1066' else 'FIGURES_WHEN_ACQUIRED',
                                  'to': {'type': 'DomesdayFigures', 'figuresId': fid}})
        out[county].append({'type': 'DomesdayEntry', 'data': data, 'relations': relations})
    print(f"  Little Domesday: {sum(len(v) for v in out.values())} entries from the translation, {len(figures_out)} earlier counts")
    return out, figures_out


def reading_text(edition):
    """
    The entry as a reader takes it, from Hull's edition text. Hull marks its apparatus (Explorer
    HELPdoc.rtf "editorial codes", matched span by span against the Textbase): [= =] the fief
    heading, ?M? and ?5? marginalia and chapter numbers, <210c> folio and column, any other <...>
    Hull's own conjectured byname for a man Domesday names by first name only, {{...}} text the
    scribe struck out. None of that is what the entry says, so it goes; a figure struck out must not
    be read as one. What an editor supplied stays, in Phillimore's square brackets: [* *] an
    identification made elsewhere, ^[ ]^ the implied meaning, [ ] words supplied. {...} is a word
    left in Latin or its Domesday spelling (ora, inland, a lost place) and is kept as written.
    """
    t = re.sub(r'\{\{.*?\}\}', '', edition)
    t = re.sub(r'\[=.*?=\]', '', t)
    t = re.sub(r'\?\[?[A-Za-z0-9]{1,4}\]?\?', '', t)
    t = re.sub(r'<[^<>]*>', '', t)
    t = re.sub(r'\[\*+\s*\*+\]', '', t)
    for _ in range(3):  # marks nest: ^[Drogo [* son of Mauger *] holds]^
        t = re.sub(r'\^\[((?:(?!\]\^).)*)\]\^', r'[\1]', t)
        t = re.sub(r'\[\*\s*(.*?)\s*\*\]', r'[\1]', t)
    t = re.sub(r'\{([^{}]*)\}', r'\1', t)
    return re.sub(r'\s+', ' ', t).strip()


def canonical_name(name):
    """
    Hull brackets the words it supplied — () from elsewhere in Domesday, {} from outside it — so one
    man is indexed as `Earl Harold`, `(Earl) Harold` and `{Earl} Harold`. Dropping the brackets and
    keeping their words gives the name a count across England can group on; `name` keeps Hull's form.
    """
    return re.sub(r'\s+', ' ', re.sub(r'[()\[\]{}]', '', name)).strip()


ENTRY_KIND = {'E': 'manor', 'F': 'fief heading', 'U': 'urban', 'L': 'rubric', 'I': 'index of landholders',
              'C': 'customs', 'W': 'Wales', 'B': 'Bruce fief'}

"""Hull's place codes: lower case is the subject of the entry, upper case a holding within it."""
HOLDING = {'1': 'manor', '7': 'land', '5': 'jurisdiction', '0': 'unclassified', '4': 'dependency',
           '3': 'outlier', '2': 'borough', '8': 'former manorial centre'}

"""
Hull's landholder codes, as NameRef carries them, and the edge each becomes. The meaning of each
was read off the Textbase: every NameRef code coincides with one span code (T1· with TW1, the
tenant-in-chief; T8· with TE1, the lord in 1066; and so on), checked over all 63,601 references.
"""
ROLE = {'T8·': 'LORD_1066', 't8·': 'OVERLORD_1066', 'T9·': 'MAN_OF_OVERLORD_1066', 't9·': 'UNDERLORD_1066',
        'T10': 'MAN_OF_UNDERLORD_1066', 'T12': 'HELD_PART_1066', 'T15': 'URBAN_HOLDER_1066',
        't11': 'JURISDICTION_1066', 'T88': 'PRIOR_LORD', 't88': 'PRIOR_OVERLORD',
        'T1·': 'TENANT_IN_CHIEF', 't1·': 'TENANT_IN_CHIEF', 'T2·': 'TENANT_1086', 'T3·': 'SUBTENANT_1086',
        'T4·': 'HELD_PART_1086', 'T34': 'HELD_PART_1086', 'T14': 'URBAN_HOLDER_1086', 'T11': 'JURISDICTION_1086',
        'T5·': 'HOLDER_1070', 'T6·': 'CLAIMANT', 'T7·': 'DEFENDANT', 'T13': 'OFFICIAL', 'T20': 'INSTITUTION',
        'T0·': 'NAMES', '': 'NAMES'}

GENDER = {'M': 'male', 'F': 'female'}

FIGURES = ['households', 'villagers', 'smallholders', 'slaves', 'cottagers', 'freemen', 'freeMen', 'priests',
           'burgesses', 'ploughmen', 'riders', 'menAtArms', 'frenchmen', 'englishmen', 'smiths', 'swineherds',
           'beekeepers', 'fishermen', 'ploughlands', 'lordsTeams', 'mensTeams', 'ploughTeams', 'geldUnits',
           'value1066', 'valueLater', 'value1086', 'mills', 'meadowAcres', 'woodlandPigs', 'fisheries',
           'saltHouses', 'sheep', 'cattle', 'goats', 'hasChurch', 'hasCastle', 'hasMarket', 'isWaste']

TO_WGS84 = Transformer.from_crs('EPSG:27700', 'EPSG:4326', always_xy=True)
GRID_LETTERS = 'ABCDEFGHJKLMNOPQRSTUVWXYZ'


def grid_to_latlng(ref):
    """OS grid reference ('SO7567') to the centre of its square, as (lat, lng)."""
    m = re.fullmatch(r'([A-HJ-Z]{2})(\d{2,10})', ref or '')
    if not m or len(m.group(2)) % 2:
        return None
    l1, l2 = (GRID_LETTERS.index(c) for c in m.group(1))
    e100 = ((l1 - 2) % 5) * 5 + l2 % 5
    n100 = 19 - (l1 // 5) * 5 - l2 // 5
    digits = m.group(2)
    half = len(digits) // 2
    size = 10 ** (5 - half)
    easting = e100 * 100000 + int(digits[:half]) * size + size / 2
    northing = n100 * 100000 + int(digits[half:]) * size + size / 2
    lng, lat = TO_WGS84.transform(easting, northing)
    return round(lat, 5), round(lng, 5)


def home_county(place):
    """
    The county a place lies in. Hull's `County` is the county whose TEXT names the place; where that
    is not where it lies (`WrongCountyCode` Y), `WrongCounty` is. Hastings is named in the text of
    six counties and lies in Sussex.
    """
    if place.get('WrongCountyCode') == 'Y' and place.get('WrongCounty'):
        return county_of(place['WrongCounty'])
    return county_of(place['County'])


def canonical_places(places):
    """
    Hull keeps one place record per county text that names a place, so Hastings is seven records.
    Each record named in another county is folded into the record for the same name and grid square
    in the county it lies in, when there is one; the map, the search and every county total then see
    one Hastings, in Sussex. Returns alias id -> canonical id.
    """
    home = {}
    for p in places:
        if p.get('WrongCountyCode') != 'Y':
            home.setdefault((p['Vill'], p['OSrefs'], county_of(p['County'])), p['PlacesIdx'])
    out = {}
    for p in places:
        if p.get('WrongCountyCode') == 'Y' and p.get('WrongCounty'):
            target = home.get((p['Vill'], p['OSrefs'], county_of(p['WrongCounty'])))
            if target:
                out[p['PlacesIdx']] = target
    return out


def rows(cache, name):
    with open(os.path.join(cache, 'csv', name + '.csv'), encoding='utf-8') as f:
        return list(csv.DictReader(f))


def county_of(code):
    return SECTION_OF.get(code, code)


"""
The host's YAML reader refuses a file over 3 MB whole, so each list is written in parts of at most
MAX_CHARS, named <stem>-01.yml, <stem>-02.yml, … in the order they seed.
"""
MAX_CHARS = 2_500_000


def write(stem, records, header):
    parts, part, size = [], [], 0
    for r in records:
        text = yaml.safe_dump([r], allow_unicode=True, sort_keys=False, width=200)
        if part and size + len(text) > MAX_CHARS:
            parts.append(part)
            part, size = [], 0
        part.append(text)
        size += len(text)
    parts.append(part)
    for i, chunk in enumerate(parts, 1):
        name = f'{stem}-{i:02d}.yml'
        with open(os.path.join(OUT, name), 'w', encoding='utf-8') as f:
            f.write(header)
            f.write(''.join(chunk))
    print(f'{stem}: {len(records)} records in {len(parts)} file(s)')


HEADER = """# {what}
# Generated by scripts/build_reference.py from the Hull Domesday Explorer database (J.J.N. Palmer
# and the University of Hull, CC BY-NC-SA) — do not edit by hand. See DATA-LICENSE.md.

"""


def main(cache):
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if f.endswith('.yml'):
            os.remove(os.path.join(OUT, f))

    counties = {c['County']: c for c in rows(cache, 'county') if c['County'] not in SECTION_OF}
    images = collections.defaultdict(list)
    for r in rows(cache, 'Images'):
        images[r['StructIdx']].append(r['Image'])

    county_records = [{'type': 'DomesdayCounty', 'data': {
        'code': code, 'name': c['CountyName'].title(), 'circuit': int(c['Circuit']),
        'inGreatDomesday': code not in LITTLE_DOMESDAY}} for code, c in sorted(counties.items())]
    write('01-counties', county_records, HEADER.format(what='The 34 counties of Domesday, with their circuit.'))

    places = rows(cache, 'Places')
    canonical = canonical_places(places)
    places = [p for p in places if p['PlacesIdx'] not in canonical]
    print(f'  {len(canonical)} places named in another county folded into their own county\'s record')
    hundreds = {}
    for p in places:
        county = home_county(p)
        if p['Hundred'] and county in counties:
            hundreds[(county, p['Hundred'])] = None
    hundred_records = [{'type': 'DomesdayHundred', 'data': {
        'hundredId': f'{county}:{name}', 'name': name, 'county': county,
        'countyName': counties[county]['CountyName'].title()},
        'relations': [{'predicate': 'IN', 'to': {'type': 'DomesdayCounty', 'code': county}}]}
        for county, name in sorted(hundreds)]

    entries = [json.loads(l) for l in open(os.path.join(cache, 'entries.jsonl'), encoding='utf-8')]
    texts = translation(cache)
    entries_of_place = collections.Counter()
    for r in rows(cache, 'PlaceRef'):
        if r['StructIdx']:
            entries_of_place[canonical.get(r['PlacesIdx'], r['PlacesIdx'])] += 1

    crosswalk = place_links(cache)
    place_records, located = [], 0
    for p in places:
        county = home_county(p)
        if county not in counties:
            continue
        data = {'placeId': p['PlacesIdx'], 'name': p['Vill'], 'county': county,
                'countyName': counties[county]['CountyName'].title()}
        if p['Hundred']:
            data['hundred'] = p['Hundred']
        if p['Area']:
            data['area'] = p['Area']
        if p['Location']:
            data['locationNote'] = p['Location']
        grid = re.fullmatch(r'([A-HJ-Z]{2}\d+)([*!]?)', p['OSrefs'] or '')
        if grid:
            data['gridRef'] = grid.group(1)
            if grid.group(2):
                data['gridRefMark'] = grid.group(2)
            point = grid_to_latlng(grid.group(1))
            if point:
                data['lat'], data['lng'] = point
                located += 1
        data['entryCount'] = entries_of_place[p['PlacesIdx']]
        data['inLittleDomesday'] = county in LITTLE_DOMESDAY
        # A place is IN its hundred and nothing else: a hundredless place pointing at its county instead gave
        # IN two meanings, and a model that saw (:DomesdayPlace)-[:IN]->(:DomesdayCounty) used it for every
        # place and found 314 of 14,334. Its county is on the place itself (countyName).
        relations = ([{'predicate': 'IN', 'to': {'type': 'DomesdayHundred', 'hundredId': f"{county}:{p['Hundred']}"}}]
                     if p['Hundred'] else [])
        link = crosswalk['places'].get(p['PlacesIdx'], {})
        for field, kind in PLACE_LINK_FIELDS.items():
            if link.get(field) not in (None, ''):
                data[field] = (float(link[field]) if kind == 'number'
                               else link[field] == 'true' if kind == 'boolean' else link[field])
        if data.get('parishCode') in crosswalk['parishes']:
            relations.append({'predicate': 'NOW_IN', 'to': {'type': 'ModernParish', 'parishCode': data['parishCode']}})
        if data.get('lsoa21Code') in crosswalk['lsoas']:
            relations.append({'predicate': 'NOW_IN_NEIGHBOURHOOD',
                              'to': {'type': 'ModernNeighbourhood', 'lsoa21Code': data['lsoa21Code']}})
        place_records.append({'type': 'DomesdayPlace', 'data': data, 'relations': relations})
    for record, neighbours in zip(hundred_records, neighbouring_hundreds(hundred_records, place_records)):
        record['relations'] += [{'predicate': 'NEIGHBOURS', 'to': {'type': 'DomesdayHundred', 'hundredId': n}}
                                for n in neighbours]
    write('02-hundreds', hundred_records,
          HEADER.format(what='Hundreds and wapentakes, the subdivisions of each county, and which border which.'))
    write('00-modern-parishes', crosswalk['parish_records'], MODERN_HEADER.format(
        what="Today's civil parishes (and unparished areas) that Domesday places lie in, with Census 2021 figures."))
    write('00-modern-neighbourhoods', crosswalk['lsoa_records'], MODERN_HEADER.format(
        what='The 2021 neighbourhoods (LSOAs) Domesday places lie in, with the English Indices of Deprivation 2025.'))
    write('03-places', place_records,
          HEADER.format(what='Every place Domesday names, with its OS grid reference and latitude/longitude.'))
    print(f'  {located} of {len(place_records)} places located')

    refs_of_person = collections.Counter()
    for r in rows(cache, 'NameRef'):
        if r['StructIdx']:
            refs_of_person[r['NamesIdx']] += 1
    """
    Wikidata and Wikipedia for the people who matter most, matched BY HAND (data/people-wikidata.csv,
    CC0 ids): a name search finds a namesake as readily as the man, so no person is linked by
    machine. Linked by canonical name, so every county record of a magnate carries it.
    """
    links = {}
    with open(os.path.join(ROOT, 'data', 'people-wikidata.csv'), encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if r.get('qid'):
                links[r['canonicalName']] = r
    person_records = []
    for n in rows(cache, 'Names'):
        county = county_of(n['County'])
        data = {'personId': n['NamesIdx'], 'name': n['Name'], 'canonicalName': canonical_name(n['Name'])}
        link = links.get(data['canonicalName'])
        if link:
            data['wikidataId'] = link['qid']
            if link.get('enwiki'):
                data['wikipedia'] = link['enwiki'].replace(' ', '_')
            if link.get('odnbId'):
                data['odnbId'] = link['odnbId']
            data['linkConfidence'] = link['confidence']
        # What a Wikipedia search is given: the first of Hull's slash-separated alternatives
        # (`Thorkell of Warwick/son of Alwin the sheriff`), since the search takes the name as one
        # phrase and no article carries both forms; the producer adds the period.
        data['wikipediaSearch'] = data['canonicalName'].split('/')[0].strip()
        if county in counties:
            data['county'] = county
            data['countyName'] = counties[county]['CountyName'].title()
        data['gender'] = GENDER.get(n['GenderCode'], 'unknown')
        data['isInstitution'] = n['ChurchCode'] not in ('', '-')
        data['entryCount'] = refs_of_person[n['NamesIdx']]
        person_records.append({'type': 'DomesdayPerson', 'data': data})
    write('04-people', person_records,
          HEADER.format(what="Hull's index of the people Domesday names, one record per name per county."))

    places_by_id = {r['data']['placeId']: r['data'] for r in place_records}
    hundred_ids = {r['data']['hundredId'] for r in hundred_records}
    people_by_id = {r['data']['personId'] for r in person_records}
    place_refs = collections.defaultdict(list)
    for r in rows(cache, 'PlaceRef'):
        r = dict(r, PlacesIdx=canonical.get(r['PlacesIdx'], r['PlacesIdx']))
        if r['StructIdx'] and r['PlacesIdx'] in places_by_id:
            place_refs[r['StructIdx']].append(r)
    name_refs = collections.defaultdict(list)
    for r in rows(cache, 'NameRef'):
        if r['StructIdx'] and r['NamesIdx'] in people_by_id:
            name_refs[r['StructIdx']].append(r)

    unknown_roles = collections.Counter()
    by_county = collections.defaultdict(list)
    for e in entries:
        county = county_of(e['county'])
        name = counties[county]['CountyName'].title()
        subject = [r for r in place_refs[e['structIdx']] if r['Pcode'][:1] == 'p']
        data = {'entryId': e['structIdx'], 'ref': f"{name} {e['phillimore']}", 'phillimore': e['phillimore'],
                'county': county, 'countyName': name,
                'kind': ENTRY_KIND.get(e['type'], e['type']),
                'edition': 'Great Domesday', 'figuresSource': 'Hull coding'}
        if e['county'] in SECTION_NAME:
            data['section'] = SECTION_NAME[e['county']]
        places_named = list(dict.fromkeys(places_by_id[r['PlacesIdx']]['name'] for r in subject))
        if places_named:
            data['places'] = ', '.join(places_named)
            data['name'] = f"{data['places']} ({data['ref']})"
        else:
            data['name'] = data['ref']
        if subject:
            data['holding'] = HOLDING.get(subject[0]['Pcode'][1:2], 'unclassified')
            # Hull types a borough's own entry (Shrewsbury, Oxford) as an ordinary entry; its place says otherwise.
            if data['kind'] == 'manor' and data['holding'] == 'borough':
                data['kind'] = 'urban'
        # A claim or a summary line restates a holding entered elsewhere in the county; it is not another manor.
        if data['kind'] == 'manor' and e['county'] in SECTION_KIND:
            data['kind'] = SECTION_KIND[e['county']]
        if (data['county'], data['phillimore']) in texts:
            data['textEdition'] = texts[(data['county'], data['phillimore'])]
            data['text'] = reading_text(data['textEdition'])
        f = figures.figures(e)
        for key in FIGURES:
            if key in f:
                data[key] = f[key]
        if images.get(e['structIdx']):
            m = re.match(r'([a-z]+)\\(\d+)\.png', images[e['structIdx']][0])
            if m:
                data['folio'] = f'{m.group(1).upper()} {int(m.group(2))}'
        relations = [{'predicate': 'IN', 'to': {'type': 'DomesdayCounty', 'code': county}}]
        seen = set()
        for r in place_refs[e['structIdx']]:
            predicate = 'DESCRIBES' if r['Pcode'][:1] == 'p' else 'INCLUDES'
            if (predicate, r['PlacesIdx']) not in seen:
                seen.add((predicate, r['PlacesIdx']))
                relations.append({'predicate': predicate, 'to': {'type': 'DomesdayPlace', 'placeId': r['PlacesIdx']}})
        """
        One edge per hundred the entry is about, however many of its places lie there: summed through
        DESCRIBES, an entry naming three places in one hundred counts three times. The hundred is the
        ENTRY's county's hundred of that name when there is one: a detached part of Oswaldslow lies in
        a Gloucestershire place but is written in Worcestershire's text, under Worcestershire's
        Oswaldslow, and "Worcestershire's hundreds" must include it.
        """
        for r in subject:
            place = places_by_id[r['PlacesIdx']]
            if not place.get('hundred'):
                continue
            hundred = f"{county}:{place['hundred']}"
            if hundred not in hundred_ids:
                hundred = f"{place['county']}:{place['hundred']}"
            if ('IN_HUNDRED', hundred) not in seen:
                seen.add(('IN_HUNDRED', hundred))
                relations.append({'predicate': 'IN_HUNDRED', 'to': {'type': 'DomesdayHundred', 'hundredId': hundred}})
        named = {r['NamesIdx'] for r in name_refs[e['structIdx']] if ROLE.get(r['Tcode']) not in (None, 'NAMES')}
        for r in name_refs[e['structIdx']]:
            predicate = ROLE.get(r['Tcode'])
            if predicate == 'NAMES' and r['NamesIdx'] in named:
                continue  # a person already linked by role is not linked again as merely named
            if predicate is None:
                unknown_roles[r['Tcode']] += 1
                predicate = 'NAMES'
            if (predicate, r['NamesIdx']) not in seen:
                seen.add((predicate, r['NamesIdx']))
                relations.append({'predicate': predicate, 'to': {'type': 'DomesdayPerson', 'personId': r['NamesIdx']}})
        by_county[county].append({'type': 'DomesdayEntry', 'data': data, 'relations': relations})

    little, earlier = little_domesday(cache, texts, canonical, places_by_id, hundred_ids)
    for county, records in little.items():
        by_county[county].extend(records)
    # Written before the entries, which point at them.
    write('045-figures', earlier, HEADER.format(
        what="Little Domesday's counts for 1066 and for when the holder acquired the land, parsed from the translation."))

    for county in sorted(by_county):
        write(f'05-entries-{county.lower()}', by_county[county],
              HEADER.format(what=f"Every Great Domesday entry for {counties[county]['CountyName'].title()}, "
                                 "with its figures and the people it names by role."))
    if unknown_roles:
        print('  unrecognised role codes, written as NAMES:', dict(unknown_roles))


if __name__ == '__main__':
    main(sys.argv[1])
