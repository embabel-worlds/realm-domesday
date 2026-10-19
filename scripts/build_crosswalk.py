"""
Link every Domesday place outward: to its Open Domesday page, its Wikidata settlement (and through
it Wikipedia, GeoNames, OpenStreetMap, Vision of Britain), the manor's Manorial Documents Register
record, the modern civil parish and LSOA it lies in, the nearest modern place-name, and the Census
2021 and deprivation figures of those areas.

    .cache/venv/bin/python scripts/build_crosswalk.py [--refresh]

writes .cache/crosswalk/{place_links,parishes,lsoa}.csv and SOURCES.md. Nothing here is written to
reference/: the links are a separate layer, so the realm's data licence and the sources' licences
never mix in one file without someone deciding they should.

How each link is made, and why:

- Open Domesday has no bulk id export and rate-limits its pages, but its sitemap lists every place
  as /place/<grid>/<slug>/. Hull's place id is Open Domesday's id, yet the path carries no id, so a
  place is matched on grid square and name: the same square first, then the same name 1 km and
  then 2 km away (Open Domesday moved some places), then a looser name within 1 km (it modernised
  some names: Staughton is great-staughton). Each path is claimed once, strictest tier first, except
  that a second Hull record of the same name in the same square shares its first record's path.
  Open Domesday's numeric id is usually Hull's, but not always (it renumbered some renamed places:
  Hull's Wimpton is 70916, Open Domesday's Whimpton 69483), so the path is a link, not an id.
- Wikidata's Open Domesday ID (P3118) holds those same paths, on settlement items and on "manor
  estate" items alike. The settlement is the link; the manor item is kept apart for its Manorial
  Documents Register id (P3029). Where no item carries the path, the parish item whose ONS code
  (P836, 2011 vintage) is the place's parish and whose name is the place's is taken, then an item
  of the same whole name within 3 km. The method is recorded on every link. Further than 3 km a
  same-named item was as often a neighbour (East for South Allington) as the place.
- Parish and LSOA are point-in-polygon on the place's latitude/longitude. Parishes are the December
  2022 boundaries because Census 2021 parish profiles were built on exactly those (Nomis geography
  TYPE160); a later vintage would put a place in a parish the census figures do not describe.
  Points that land in no polygon (the sea, a clipped estuary) take the nearest within 3 km, and say
  so with the distance.
- The point is the centre of Hull's 1 km grid square, so it can be 700 m from the place itself: a
  village on a parish edge can land in its neighbour. No join here is finer than that.
"""
import argparse
import collections
import csv
import difflib
import glob
import json
import math
import os
import re
import sys
import time
import unicodedata
import urllib.parse

import yaml
from pyproj import Transformer
from shapely import STRtree
from shapely.geometry import Point, shape
from shapely.ops import nearest_points

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crosswalk_sources as sources  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, '.cache', 'crosswalk')
GRID_LETTERS = 'ABCDEFGHJKLMNOPQRSTUVWXYZ'
TO_BNG = Transformer.from_crs('EPSG:4326', 'EPSG:27700', always_xy=True)
NEAREST_LIMIT_KM = 3.0
LOST_RADIUS_M = 2000
NAME_MATCH_RADIUS_M = 5000
WIKIDATA_NEAR_KM = 3.0

"""IPN descriptors that name a settlement or a parish; wards, divisions and districts do not."""
IPN_PLACE_TYPES = {'LOC': 'locality', 'PAR': 'parish', 'COM': 'community', 'BUA': 'built-up area'}


def load_places():
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'reference', '03-places-*.yml'))):
        with open(f, encoding='utf-8') as fh:
            out += [r['data'] for r in yaml.load(fh, Loader=getattr(yaml, 'CSafeLoader', yaml.SafeLoader))]
    return out


def headword(raw):
    """Hull indexes cross-references as places ('Woodwalton: see [Wood] Walton'); the headword is before ': see'."""
    name, _, target = raw.partition(': see ')
    return name.strip(), bool(target)


def name_variants(raw):
    """
    Hull marks words it supplied with [] or {} and quotes forms it could not identify with `'. The
    full form keeps the supplied words ('[Great] Alne' is Great Alne); the bare form drops them
    ('Aston [by Budworth]' is also indexed elsewhere as plain Aston). Both are tried.
    """
    name, _ = headword(raw)
    full = re.sub(r'\s+', ' ', re.sub(r"[\[\]{}()`'?]", '', name)).strip()
    bare = re.sub(r'\s+', ' ', re.sub(r"\[[^\]]*\]|\{[^}]*\}|[`'?()]", ' ', name)).strip()
    return [v for v in dict.fromkeys([full, bare]) if v]


def ascii_fold(s):
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()


def slug(s):
    """Django's slugify, which is what Open Domesday's paths are."""
    s = re.sub(r'[^\w\s-]', '', ascii_fold(s).lower()).strip()
    return re.sub(r'[-\s]+', '-', s)


QUALIFIERS = {'great', 'little', 'north', 'south', 'east', 'west', 'upper', 'lower', 'nether', 'over', 'magna',
              'parva', 'major', 'minor', 'old', 'new', 'much', 'high', 'low', 'long', 'and', 'superior', 'inferior'}
CONNECTORS = {'on', 'upon', 'by', 'under', 'in', 'cum', 'juxta', 'next', 'near', 'with', 'super', 'sub', 'le', 'de',
              'la', 'the', 'en', 'st', 'saint', 'atte', 'at'}


def name_core(s):
    """
    The comparable core of a place-name: ascii, lower case, punctuation gone, leading and trailing
    qualifiers (Great, Little, North, Magna, Parva …) dropped, and everything from a connector on
    (on-the-Hill, by-Derby, St Mary) dropped, then the words joined so 'Upper Thong' and
    'Upperthong' meet. Two names match when their cores are equal. It is deliberately loose: it
    answers "is a place of this name here", not "is this the same place".
    """
    words = re.sub(r'[^a-z0-9]+', ' ', ascii_fold(s).lower().replace('&', ' and ').replace("'", '')).split()
    while len(words) > 1 and words[0] in QUALIFIERS:
        words = words[1:]
    for i, w in enumerate(words[1:], 1):
        if w in CONNECTORS:
            words = words[:i]
            break
    while len(words) > 1 and words[-1] in QUALIFIERS:
        words = words[:-1]
    return ''.join(words)


def strict_name(s):
    """A name compared whole: case, punctuation and 'St'/'Saint' aside, nothing is dropped."""
    words = re.sub(r'[^a-z0-9]+', ' ', ascii_fold(s).lower().replace('&', ' and ').replace("'", '')).split()
    return ''.join('st' if w == 'saint' else w for w in words)


def names_equal(raw, other):
    """
    For an identity link (a Wikidata item) the loose core is too loose — it makes South Allington
    East Allington — so the whole name must agree with one of Hull's forms.
    """
    return strict_name(other) in {strict_name(v) for v in name_variants(raw)}


def names_match(raw, other):
    """
    Cores equal, or nearly: one letter in eight may differ, because modern spelling drifted by a
    letter as often as by a word (Shottesbrook/Shottesbrooke, Occleston/Occlestone).
    """
    theirs = name_core(other)
    cores = {name_core(v) for v in name_variants(raw)} - {''}
    return theirs in cores or any(len(c) >= 5 and difflib.SequenceMatcher(None, c, theirs).ratio() >= 0.88
                                  for c in cores)


def grid_km(ref):
    """'SO7567' as whole kilometres east and north of the OSGB origin."""
    l1, l2 = GRID_LETTERS.index(ref[0]), GRID_LETTERS.index(ref[1])
    return (((l1 - 2) % 5) * 5 + l2 % 5) * 100 + int(ref[2:4]), (19 - (l1 // 5) * 5 - l2 // 5) * 100 + int(ref[4:6])


def haversine_km(a, b):
    (la1, lo1), (la2, lo2) = a, b
    p1, p2 = math.radians(la1), math.radians(la2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(h))


# --- Open Domesday ---------------------------------------------------------------------------------

def match_open_domesday(places, sitemap_path):
    with open(sitemap_path, encoding='utf-8') as f:
        paths = sorted(set(re.findall(r'opendomesday\.org/place/([A-Z]{2}\d{4}/[^/<]+)/', f.read())))
    by_square = collections.defaultdict(list)
    for p in paths:
        if not p.startswith('XX'):
            by_square[grid_km(p[:6])].append(p)
    unlocated = collections.defaultdict(list)
    for p in paths:
        if p.startswith('XX'):
            unlocated[p[7:]].append(p)

    claimed, result = set(), {}

    def around(grid, reach=1):
        e, n = grid_km(grid)
        return [(p, max(abs(e - x), abs(n - y))) for x in range(e - reach, e + reach + 1)
                for y in range(n - reach, n + reach + 1) for p in by_square.get((x, y), [])]

    def claim(place, path, how):
        claimed.add(path)
        result[place['placeId']] = (path, how)

    """
    Lowest id first, because Open Domesday's id is Hull's: where Hull keeps two records of one place
    (Addingham 301 in Burghshire, 306 in Craven), the page is 301's, and 306 shares it.
    """
    candidates = sorted((p for p in places if not headword(p['name'])[1] and name_variants(p['name'])),
                        key=lambda p: int(p['placeId']))
    """An unlocated name is only a match when it is unlocated and unique on both sides."""
    unlocated_slugs = collections.Counter(s for p in candidates if not p.get('gridRef')
                                          for s in {slug(v) for v in name_variants(p['name'])})
    for p in candidates:
        slugs = [slug(v) for v in name_variants(p['name'])]
        grid = p.get('gridRef')
        if grid:
            hit = next((f'{grid}/{s}' for s in slugs if f'{grid}/{s}' in by_square.get(grid_km(grid), [])), None)
            if hit:
                claim(p, hit, 'exact (shared)' if hit in claimed else 'exact')
        else:
            hits = [u for s in slugs for u in unlocated.get(s, [])]
            if len(set(hits)) == 1 and hits[0] not in claimed and all(unlocated_slugs[s] == 1 for s in set(slugs)):
                claim(p, hits[0], 'unlocated+name')
    """
    The same name a square or two away. Two squares is not a guess: Prenton is SJ3184 in Hull and
    SJ3086 in Open Domesday, and Open Domesday's own id for SJ3086/prenton is Hull's 50091.
    """
    for reach in (1, 2):
        for p in candidates:
            grid = p.get('gridRef')
            if p['placeId'] in result or not grid:
                continue
            slugs = {slug(v) for v in name_variants(p['name'])}
            near = sorted((d, path) for path, d in around(grid, reach) if path[7:] in slugs and path not in claimed)
            if near:
                claim(p, near[0][1], f'grid±{reach}km+name')
    for p in candidates:
        grid = p.get('gridRef')
        if p['placeId'] in result or not grid:
            continue
        slugs = [slug(v) for v in name_variants(p['name'])]
        scored = []
        for path, d in around(grid):
            if path in claimed:
                continue
            theirs = path[7:]
            ratio = max(difflib.SequenceMatcher(None, s, theirs).ratio() for s in slugs)
            shared = any(len(w) >= 4 and (w in theirs.split('-') or theirs in s.split('-'))
                         for s in slugs for w in s.split('-'))
            if ratio >= 0.8 or shared:
                scored.append((d, -ratio, path))
        if scored:
            claim(p, sorted(scored)[0][2], 'grid±1km+fuzzy-name')
    return result, len(paths) - len(claimed)


# --- Wikidata --------------------------------------------------------------------------------------

def qid(uri):
    return uri.rsplit('/', 1)[-1]


def point_of(wkt):
    m = re.match(r'Point\(([-\d.eE]+) ([-\d.eE]+)\)', wkt or '')
    return (float(m.group(2)), float(m.group(1))) if m else None


def load_items(path, key):
    """Rows of a SPARQL CSV folded into one record per item; multi-valued properties keep every value."""
    items = {}
    with open(path, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            it = items.setdefault(qid(r['i']), collections.defaultdict(set))
            for k, v in r.items():
                if v and k != 'i':
                    it[k].add(v)
    for q, it in items.items():
        it['qid'] = q
        it['point'] = next(filter(None, map(point_of, sorted(it.get('coord', ())))), None)
        it['is_manor'] = 'true' in it.get('manor', ())
        it['is_deserted'] = 'true' in it.get('deserted', ())
    return items


def first(values):
    """Deterministic choice among a property's values: numeric ids by number, others as text."""
    vals = sorted(values or (), key=lambda v: (len(v), v))
    return vals[0] if vals else ''


def settlement_rank(it):
    """Prefer the item a reader would want: one with an article, then the civil parish, then the oldest."""
    return (not it.get('enwiki'), not it.get('gss'), int(it['qid'][1:]))


def wikipedia_title(url):
    return urllib.parse.unquote(url.rsplit('/wiki/', 1)[-1]).replace('_', ' ') if url else ''


# --- Geography -------------------------------------------------------------------------------------

class Areas:
    """Polygons of one boundary layer, queried by point; falls back to the nearest within 3 km."""

    def __init__(self, geojson_path, code, name):
        with open(geojson_path, encoding='utf-8') as f:
            feats = [x for x in json.load(f)['features'] if x.get('geometry')]
        self.props = [x['properties'] for x in feats]
        self.geoms = [shape(x['geometry']) for x in feats]
        self.tree = STRtree(self.geoms)
        self.code, self.name = code, name

    def locate(self, lat, lng):
        pt = Point(lng, lat)
        hits = sorted(self.tree.query(pt, predicate='intersects'), key=lambda i: self.props[i][self.code])
        if hits:
            return self.props[hits[0]], 'within', None
        i = self.tree.query_nearest(pt, max_distance=0.06)
        if len(i) == 0:
            return None, '', None
        near = nearest_points(self.geoms[i[0]], pt)[0]
        km = haversine_km((lat, lng), (near.y, near.x))
        return (self.props[i[0]], 'nearest', round(km, 2)) if km <= NEAREST_LIMIT_KM else (None, '', None)


def read_text_any(path):
    raw = open(path, 'rb').read()
    try:
        return raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        return raw.decode('cp1252')


class PlaceNames:
    """The IPN's settlements and parishes as points on the National Grid, for nearest and within-radius."""

    def __init__(self, path):
        rows = [r for r in csv.DictReader(read_text_any(path).splitlines())
                if r['descnm'] in IPN_PLACE_TYPES and r['gridgb1e'] and r['gridgb1n']]
        self.rows = rows
        self.tree = STRtree([Point(float(r['gridgb1e']), float(r['gridgb1n'])) for r in rows])

    def near(self, lat, lng, raw_name):
        pt = Point(*TO_BNG.transform(lng, lat))
        i = self.tree.query_nearest(pt)[0]
        nearest = self.rows[i]
        nearest_m = pt.distance(self.tree.geometries[i])
        matches = sorted((pt.distance(self.tree.geometries[j]), self.rows[j]['place23nm'])
                         for j in self.tree.query(pt, predicate='dwithin', distance=NAME_MATCH_RADIUS_M)
                         if names_match(raw_name, self.rows[j]['place23nm']))
        return nearest, nearest_m, (matches[0] if matches else None)


# --- Assembly --------------------------------------------------------------------------------------

def nomis_values(path):
    with open(path, encoding='utf-8') as f:
        return {r['GEOGRAPHY_CODE']: r for r in csv.DictReader(f)}


def km(x):
    return '' if x is None else f'{x:.2f}'


def main(refresh):
    started = time.time()
    places = load_places()
    os.makedirs(OUT, exist_ok=True)
    cache = sources.Cache(OUT, refresh)
    prefixes = sorted({p['gridRef'][:2] for p in places if p.get('gridRef')} | {'XX'})
    paths = sources.fetch_all(cache, prefixes)
    print(f'sources ready in {time.time() - started:.0f}s')

    od, od_unclaimed = match_open_domesday(places, paths['opendomesday'])

    items = load_items(paths['wd_p3118'], 'v')
    by_path = collections.defaultdict(list)
    for it in items.values():
        for v in it.get('v', ()):
            by_path[v].append(it)
    parish_items = load_items(paths['wd_parishes'], 'gss')
    by_gss = collections.defaultdict(list)
    for it in parish_items.values():
        for g in it.get('gss', ()):
            by_gss[g].append(it)
    named_items = collections.defaultdict(list)
    for it in list(items.values()) + list(parish_items.values()):
        if not it['is_manor'] and it['point']:
            for label in it.get('label', ()):
                named_items[strict_name(label)].append(it)
    wd_squares = collections.defaultdict(list)
    for v, its in by_path.items():
        if re.match(r'[A-HJ-Z]{2}\d{4}/', v) and not v.startswith('XX'):
            wd_squares[grid_km(v[:6])].append(v)
    used_paths = {path for path, _ in od.values()}

    parishes = Areas(paths['parishes'], 'PARNCP22CD', 'PARNCP22NM')
    lsoas = Areas(paths['lsoas'], 'LSOA21CD', 'LSOA21NM')
    lads = Areas(paths['lads'], 'LAD22CD', 'LAD22NM')
    with open(paths['parish_lad'], encoding='utf-8') as f:
        parish_lad = {x['properties']['PAR22CD']: x['properties'] for x in json.load(f)['features']}
    names = PlaceNames(paths['ipn'])
    print(f'boundaries and names loaded at {time.time() - started:.0f}s')

    rows, parish_hits, lsoa_hits = [], collections.Counter(), collections.Counter()
    parish_area = {}
    for p in sorted(places, key=lambda p: int(p['placeId'])):
        row = {k: p.get(k, '') for k in ('placeId', 'name', 'county', 'gridRef', 'lat', 'lng')}
        path, how = od.get(p['placeId'], ('', ''))
        row['openDomesdayPath'], row['openDomesdayMatch'] = path, how
        located = 'lat' in p
        here = (p['lat'], p['lng']) if located else None

        parish = None
        if located:
            props, method, dist = parishes.locate(*here)
            if props:
                parish = props['PARNCP22CD']
                parish_area[parish] = props
                parish_hits[parish] += 1
                row.update(parishCode=parish, parishName=props['PARNCP22NM'], parishMethod=method,
                           parishDistanceKm=km(dist))
                lad = parish_lad.get(parish)
                if not lad:
                    lad_props, _, _ = lads.locate(*here)
                    lad = lad_props and {'LAD22CD': lad_props['LAD22CD'], 'LAD22NM': lad_props['LAD22NM']}
                if lad:
                    row.update(ladCode=lad['LAD22CD'], ladName=lad['LAD22NM'])
            props, method, dist = lsoas.locate(*here)
            if props:
                lsoa_hits[props['LSOA21CD']] += 1
                row.update(lsoa21Code=props['LSOA21CD'], lsoaMethod=method, lsoaDistanceKm=km(dist))

        settlement, method, manors = None, '', []
        if path:
            here_items = by_path.get(path, [])
            manors = [it for it in here_items if it['is_manor']]
            towns = sorted((it for it in here_items if not it['is_manor']), key=settlement_rank)
            if towns:
                settlement = towns[0]
                method = 'exact path' if how in ('exact', 'exact (shared)', 'unlocated+name') else how
        if not settlement and p.get('gridRef'):
            e, n = grid_km(p['gridRef'])
            slugs = {slug(v) for v in name_variants(p['name'])}
            near = sorted((max(abs(e - x), abs(n - y)), v) for x in (e - 1, e, e + 1) for y in (n - 1, n, n + 1)
                          for v in wd_squares.get((x, y), []) if v[7:] in slugs and v not in used_paths)
            for _, v in near:
                towns = sorted((it for it in by_path[v] if not it['is_manor']), key=settlement_rank)
                manors = manors or [it for it in by_path[v] if it['is_manor']]
                if towns:
                    settlement, method = towns[0], 'grid±1km+name'
                    break
        if not settlement and parish:
            towns = sorted((it for it in by_gss.get(parish, []) if any(names_equal(p['name'], l) for l in it.get('label', ()))),
                           key=settlement_rank)
            if towns:
                settlement, method = towns[0], 'parish-code+name'
        if not settlement and located:
            keys = {strict_name(v) for v in name_variants(p['name'])} - {''}
            near = sorted(((haversine_km(here, it['point']), settlement_rank(it), it['qid'], it)
                           for k in keys for it in named_items.get(k, [])), key=lambda t: t[:3])
            if near and near[0][0] <= WIKIDATA_NEAR_KM:
                settlement, method = near[0][3], f'name-within-{WIKIDATA_NEAR_KM:g}km'

        if settlement:
            row.update(wikidataId=settlement['qid'], wikidataLabel=first(settlement.get('label')),
                       wikidataMatchMethod=method, wikipedia=wikipedia_title(first(settlement.get('enwiki'))),
                       geonamesId=first(settlement.get('geonames')), osmRelationId=first(settlement.get('osm')),
                       visionOfBritainPlaceId=first(settlement.get('vobPlace')),
                       wikidataDeserted=str(settlement['is_deserted']).lower())
            if located and settlement['point']:
                row['wikidataDistanceKm'] = km(haversine_km(here, settlement['point']))
        if manors:
            manors.sort(key=lambda it: int(it['qid'][1:]))
            row['manorWikidataId'] = ';'.join(it['qid'] for it in manors)
            row['manorialDocumentsRegisterId'] = ';'.join(sorted(
                {t for it in manors for t in it.get('tna', ()) if t.startswith('F')}))

        if located:
            nearest, nearest_m, match = names.near(p['lat'], p['lng'], p['name'])
            row.update(modernPlaceName=nearest['place23nm'], modernPlaceType=IPN_PLACE_TYPES[nearest['descnm']],
                       modernPlaceDistanceKm=km(nearest_m / 1000),
                       nameMatches=str(names_match(p['name'], nearest['place23nm'])).lower())
            if match:
                row.update(nameMatchPlaceName=match[1], nameMatchDistanceKm=km(match[0] / 1000))
            """
            The coordinator's definition, kept literal: lost from the modern gazetteers, not proven
            deserted. A village Wikidata types as deserted is linked, so it is not likelyLost;
            wikidataDeserted carries that evidence separately rather than redefining the flag.
            """
            lost = not settlement and not (match and match[0] <= LOST_RADIUS_M)
            row['likelyLost'] = str(lost).lower()
        rows.append(row)
    print(f'places linked at {time.time() - started:.0f}s')

    write_csv('place_links.csv', PLACE_COLUMNS, rows)
    write_parishes(paths, parish_hits, parish_area, parish_lad, lads)
    write_lsoas(paths, lsoa_hits)
    write_sources(cache)
    print(f'{len(rows)} places; {od_unclaimed} Open Domesday paths claimed by no place; '
          f'{time.time() - started:.0f}s')


PLACE_COLUMNS = ['placeId', 'name', 'county', 'gridRef', 'lat', 'lng', 'openDomesdayPath', 'openDomesdayMatch',
                 'wikidataId', 'wikidataLabel', 'wikidataMatchMethod', 'wikidataDistanceKm', 'wikipedia', 'geonamesId',
                 'osmRelationId', 'visionOfBritainPlaceId', 'manorWikidataId', 'manorialDocumentsRegisterId',
                 'parishCode', 'parishName', 'parishMethod', 'parishDistanceKm', 'ladCode', 'ladName',
                 'lsoa21Code', 'lsoaMethod', 'lsoaDistanceKm', 'modernPlaceName', 'modernPlaceType',
                 'modernPlaceDistanceKm', 'nameMatches', 'nameMatchPlaceName', 'nameMatchDistanceKm', 'likelyLost',
                 'wikidataDeserted']


def write_csv(name, columns, rows):
    with open(os.path.join(OUT, name), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    print(f'  {name}: {len(rows)} rows')


def write_parishes(paths, hits, area, parish_lad, lads):
    residents = nomis_values(paths['pp002'])
    households = nomis_values(paths['pp001'])
    ages = collections.defaultdict(dict)
    with open(paths['pp012'], encoding='utf-8') as f:
        for r in csv.DictReader(f):
            ages[r['GEOGRAPHY_CODE']][r['C2021_AGE_4B']] = r['OBS_VALUE']
    rows = []
    for code in sorted(hits):
        props = area[code]
        lad = parish_lad.get(code) or {}
        if not lad:
            lad_props, _, _ = lads.locate(*lads_point(paths, code))
            lad = lad_props or {}
        hectares = round(props['Shape__Area'] / 10000, 1) if props.get('Shape__Area') else None
        res = residents.get(code, {}).get('OBS_VALUE', '')
        rows.append({'parishCode': code, 'parishName': props['PARNCP22NM'], 'ladCode': lad.get('LAD22CD', ''),
                     'ladName': lad.get('LAD22NM', ''), 'domesdayPlaces': hits[code], 'usualResidents2021': res,
                     'households2021': households.get(code, {}).get('OBS_VALUE', ''),
                     'aged0to15': ages[code].get('1', ''), 'aged16to64': ages[code].get('2', ''),
                     'aged65plus': ages[code].get('3', ''), 'areaHectares': hectares or '',
                     'residentsPerHectare': f'{int(res) / hectares:.2f}' if res and hectares else ''})
    write_csv('parishes.csv', list(rows[0]), rows)


_parish_points = {}


def lads_point(paths, code):
    """A point inside a non-civil-parished area, for the LAD it belongs to (the lookup omits them)."""
    if not _parish_points:
        with open(paths['parishes'], encoding='utf-8') as f:
            for x in json.load(f)['features']:
                if x['properties']['PARNCP22CD'].startswith('E43'):
                    pt = shape(x['geometry']).representative_point()
                    _parish_points[x['properties']['PARNCP22CD']] = (pt.y, pt.x)
    return _parish_points[code]


def write_lsoas(paths, hits):
    with open(paths['lsoas'], encoding='utf-8') as f:
        names = {x['properties']['LSOA21CD']: x['properties']['LSOA21NM'] for x in json.load(f)['features']}
    with open(paths['ruc'], encoding='utf-8') as f:
        ruc = {x['properties']['LSOA21CD']: x['properties'] for x in json.load(f)['features']}
    iod = {}
    for r in csv.DictReader(read_text_any(paths['iod']).splitlines()):
        iod[r['LSOA code (2021)']] = r
    col = lambda r, start: next((v for k, v in r.items() if k.startswith(start)), '')  # noqa: E731
    rows = []
    for code in sorted(hits):
        r, u = iod.get(code, {}), ruc.get(code, {})
        rows.append({'lsoa21Code': code, 'lsoaName': names.get(code, ''), 'domesdayPlaces': hits[code],
                     'imd2025Rank': col(r, 'Index of Multiple Deprivation (IMD) Rank'),
                     'imd2025Decile': col(r, 'Index of Multiple Deprivation (IMD) Decile'),
                     'incomeDecile2025': col(r, 'Income Decile'), 'employmentDecile2025': col(r, 'Employment Decile'),
                     'ladCode2024': r.get('Local Authority District code (2024)', ''),
                     'ruc21Code': u.get('RUC21CD', ''), 'ruc21Name': u.get('RUC21NM', ''),
                     'urbanRural': u.get('Urban_rural_flag', '')})
    write_csv('lsoa.csv', list(rows[0]), rows)


def write_sources(cache):
    fetched = {'opendomesday': cache.fetched('opendomesday-sitemap.xml'), 'wikidata': cache.fetched('wikidata-p3118.csv')}
    lines = ['# Sources of the Domesday crosswalk', '',
             'Generated by `scripts/build_crosswalk.py`. Every file in this directory derives from the sources '
             'below; the attribution lines are the ones each licence asks for.', '']
    for key, s in sources.SOURCES.items():
        lines += [f"## {s['title']}", '', f"- URL: {s['url']}",
                  f"- Vintage: {s['vintage'].format(fetched=fetched.get(key) or 'on build')}",
                  f"- Licence: {s['licence']}", '']
    lines += ['## Geography agreement', '',
              '- Parish codes are December 2022 (`PARNCP22CD`), the boundaries Census 2021 parish profiles were '
              'compiled on (Nomis TYPE160, "2022 parishes"). Codes `E43…` are non-civil-parished areas, which '
              'Nomis does not publish; they have no census figures here.',
              '- LAD codes are December 2022, from the PAR22–WD22–LAD22 lookup; for non-civil-parished areas, '
              'from the LAD (December 2022) boundary containing the point.',
              '- LSOA codes are 2021, the geography of both Census 2021 and IoD2025. IoD2025 covers England only; '
              'Welsh LSOAs carry no IMD.',
              '- `areaHectares` is the BGC polygon area (generalised, clipped to the coast), so it is approximate.', '']
    with open(os.path.join(OUT, 'SOURCES.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--refresh', action='store_true', help='download every source again')
    main(ap.parse_args().refresh)
