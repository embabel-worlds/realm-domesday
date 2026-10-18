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
    write('02-hundreds', hundred_records,
          HEADER.format(what='Hundreds and wapentakes, the subdivisions of each county.'))

    entries = [json.loads(l) for l in open(os.path.join(cache, 'entries.jsonl'), encoding='utf-8')]
    entries_of_place = collections.Counter()
    for r in rows(cache, 'PlaceRef'):
        if r['StructIdx']:
            entries_of_place[canonical.get(r['PlacesIdx'], r['PlacesIdx'])] += 1

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
        to = ({'type': 'DomesdayHundred', 'hundredId': f"{county}:{p['Hundred']}"} if p['Hundred']
              else {'type': 'DomesdayCounty', 'code': county})
        place_records.append({'type': 'DomesdayPlace', 'data': data, 'relations': [{'predicate': 'IN', 'to': to}]})
    write('03-places', place_records,
          HEADER.format(what='Every place Domesday names, with its OS grid reference and latitude/longitude.'))
    print(f'  {located} of {len(place_records)} places located')

    refs_of_person = collections.Counter()
    for r in rows(cache, 'NameRef'):
        if r['StructIdx']:
            refs_of_person[r['NamesIdx']] += 1
    person_records = []
    for n in rows(cache, 'Names'):
        county = county_of(n['County'])
        data = {'personId': n['NamesIdx'], 'name': n['Name'], 'canonicalName': canonical_name(n['Name'])}
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
                'kind': ENTRY_KIND.get(e['type'], e['type'])}
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
        place's own, so detached parts land in the hundred that actually held them.
        """
        for r in subject:
            place = places_by_id[r['PlacesIdx']]
            if place.get('hundred') and ('IN_HUNDRED', place['county'], place['hundred']) not in seen:
                seen.add(('IN_HUNDRED', place['county'], place['hundred']))
                relations.append({'predicate': 'IN_HUNDRED',
                                  'to': {'type': 'DomesdayHundred', 'hundredId': f"{place['county']}:{place['hundred']}"}})
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

    for county in sorted(by_county):
        write(f'05-entries-{county.lower()}', by_county[county],
              HEADER.format(what=f"Every Great Domesday entry for {counties[county]['CountyName'].title()}, "
                                 "with its figures and the people it names by role."))
    if unknown_roles:
        print('  unrecognised role codes, written as NAMES:', dict(unknown_roles))


if __name__ == '__main__':
    main(sys.argv[1])
