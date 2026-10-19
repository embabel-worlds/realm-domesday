"""
Every outside source the crosswalk reads, and how each is fetched into .cache/crosswalk/raw/.

Each source is downloaded once and kept: a re-run of build_crosswalk.py reads the cached copy, and
--refresh fetches again. Wikidata is cached too, because a re-run that silently picks up a week of
community edits is not a re-run of the same build. SOURCES is the
register SOURCES.md is written from, so a source cannot be used without its vintage and licence
being stated.

Politeness is per host: Open Domesday is one sitemap request (it answers 429 to bursts), Wikidata
is batched by grid prefix with a pause between batches and a User-Agent that says who is asking,
the ONS ArcGIS services are paged at their own maxRecordCount, Nomis at its 25,000-row cap.
"""
import csv
import io
import json
import os
import time
import urllib.parse
import urllib.request
import zipfile

USER_AGENT = 'realm-domesday-crosswalk/1.0 (https://github.com/embabel-worlds/realm-domesday)'
ARCGIS = 'https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services'
NOMIS = 'https://www.nomisweb.co.uk/api/v01/dataset'
WDQS = 'https://query.wikidata.org/sparql'

OGL = 'Open Government Licence v3.0 (https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)'
ONS_LINE = 'Source: Office for National Statistics licensed under the Open Government Licence v.3.0'
OS_LINE = 'Contains OS data © Crown copyright and database right {year}'

SOURCES = {
    'opendomesday': dict(
        title='Open Domesday place sitemap', url='https://opendomesday.org/sitemap.xml',
        vintage='fetched {fetched}', licence='Only the URL paths of its place pages are used, as links. Open '
        'Domesday (Anna Powell-Smith) states its Domesday data is Hull\'s, under CC BY-NC-SA, and its folio '
        'images CC BY-SA, crediting Professor John Palmer, George Slater and opendomesday.org.'),
    'wikidata': dict(
        title='Wikidata Query Service: items with an Open Domesday settlement ID (P3118), and items with an '
        'ONS/GSS code (P836) for an English parish or Welsh community. Properties read: P3118, P31 (Q2116450 '
        'manor estate; Q21751582 deserted medieval village; Q350895 abandoned village), P1566 GeoNames, P402 '
        'OSM relation, P3616 Vision of Britain place, P3615 Vision of Britain unit, P3029 UK National Archives '
        'ID (Manorial Documents Register when F-prefixed), P836 GSS code, P625 coordinates, enwiki sitelink', url=WDQS,
        vintage='queried {fetched}', licence='CC0 1.0 (https://creativecommons.org/publicdomain/zero/1.0/). '
        'Wikipedia titles are sitelinks held in Wikidata; the articles themselves are CC BY-SA.'),
    'parishes': dict(
        title='Parishes and Non Civil Parished Areas (December 2022) Boundaries EW BGC (V3)',
        url=f'{ARCGIS}/Parishes_and_Non_Civil_Parished_Areas_December_2022_EW_BGC_V3/FeatureServer/0',
        vintage='December 2022 boundaries, generalised (20 m) and clipped to the coastline',
        licence=f'{OGL}. {ONS_LINE}. {OS_LINE.format(year=2022)}.'),
    'parish_lad': dict(
        title='Parish to Ward to Local Authority District (December 2022) Lookup in EW',
        url=f'{ARCGIS}/PAR22_WD22_LAD22_EW_LU/FeatureServer/0', vintage='December 2022',
        licence=f'{OGL}. {ONS_LINE}.'),
    'lads': dict(
        title='Local Authority Districts (December 2022) Boundaries UK BGC',
        url=f'{ARCGIS}/Local_Authority_Districts_December_2022_UK_BGC_V2/FeatureServer/0',
        vintage='December 2022; used only for the non-civil-parished areas the parish lookup omits',
        licence=f'{OGL}. {ONS_LINE}. {OS_LINE.format(year=2022)}.'),
    'lsoas': dict(
        title='Lower layer Super Output Areas (December 2021) Boundaries EW BGC (V5)',
        url=f'{ARCGIS}/Lower_layer_Super_Output_Areas_December_2021_Boundaries_EW_BGC_V5/FeatureServer/0',
        vintage='2021 LSOAs (the Census 2021 and IoD 2025 geography)',
        licence=f'{OGL}. {ONS_LINE}. {OS_LINE.format(year=2021)}.'),
    'ruc': dict(
        title='Rural Urban Classification (2021) of LSOAs in EW',
        url=f'{ARCGIS}/LSOA21_RUC21_EW_LU/FeatureServer/0', vintage='RUC 2021 on 2021 LSOAs',
        licence=f'{OGL}. {ONS_LINE}.'),
    'nomis': dict(
        title='Census 2021 parish profiles, Nomis: NM_2352_1 (PP002 Sex, all persons = usual residents), '
        'NM_2351_1 (PP001 Number of households), NM_2362_1 (PP012 Age, 3 bands)',
        url=f'{NOMIS}/NM_2352_1 ; {NOMIS}/NM_2351_1 ; {NOMIS}/NM_2362_1',
        vintage='Census Day 21 March 2021, on geography TYPE160 "2022 parishes" (ONS: properties plotted '
        'into parish boundaries current at December 2022). Only parishes and Welsh communities with at '
        'least 50 usual residents and 20 households; no non-civil-parished areas.',
        licence=f'{OGL}. {ONS_LINE}.'),
    'iod': dict(
        title='English Indices of Deprivation 2025, File 7: all ranks, scores, deciles and population denominators',
        url='https://www.gov.uk/government/statistics/english-indices-of-deprivation-2025',
        vintage='IoD2025, published 30 October 2025, on 2021 LSOAs; England only',
        licence=f'{OGL}. Source: Ministry of Housing, Communities and Local Government, English Indices of '
        'Deprivation 2025, licensed under the Open Government Licence v.3.0.'),
    'ipn': dict(
        title='Index of Place Names in Great Britain (July 2024)',
        url='https://www.arcgis.com/sharing/rest/content/items/208d9884575647c29f0dd5a1184e711a/data',
        vintage='July 2024', licence=f'{OGL}. {ONS_LINE}. {OS_LINE.format(year=2024)}.'),
}


def get(url, params=None, accept=None, tries=4):
    if params:
        url = f'{url}?{urllib.parse.urlencode(params)}'
    headers = {'User-Agent': USER_AGENT}
    if accept:
        headers['Accept'] = accept
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=300) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            # 429 and 5xx are the services asking us to slow down; anything else is our mistake.
            if e.code not in (429, 500, 502, 503, 504) or attempt == tries - 1:
                raise
            time.sleep(int(e.headers.get('Retry-After') or 30 * (attempt + 1)))
        except (urllib.error.URLError, TimeoutError):
            if attempt == tries - 1:
                raise
            time.sleep(15 * (attempt + 1))


class Cache:
    def __init__(self, root, refresh=False):
        self.raw = os.path.join(root, 'raw')
        os.makedirs(self.raw, exist_ok=True)
        self.refresh = refresh

    def path(self, name):
        return os.path.join(self.raw, name)

    def fetched(self, name):
        p = self.path(name)
        return time.strftime('%Y-%m-%d', time.localtime(os.path.getmtime(p))) if os.path.exists(p) else None

    def keep(self, name, produce):
        p = self.path(name)
        if self.refresh or not os.path.exists(p):
            data = produce()
            with open(p + '.part', 'wb') as f:
                f.write(data if isinstance(data, bytes) else data.encode('utf-8'))
            os.replace(p + '.part', p)
        return p


def arcgis_features(service, fields, geometry=True):
    """
    Every feature of an ONS ArcGIS layer as GeoJSON, paged at the layer's maxRecordCount. Geometry is
    asked for in WGS84 because the places are; six decimals is ~0.1 m, far inside the 20 m
    generalisation of a BGC layer.
    """
    meta = json.loads(get(service, {'f': 'json'}))
    page = meta.get('maxRecordCount') or 1000
    oid = meta.get('objectIdField') or 'FID'
    out, offset = [], 0
    while True:
        params = {'where': '1=1', 'outFields': ','.join(fields), 'orderByFields': oid,
                  'resultOffset': offset, 'resultRecordCount': page, 'f': 'geojson'}
        if geometry:
            params.update(outSR=4326, geometryPrecision=6)
        else:
            params['returnGeometry'] = 'false'
        batch = json.loads(get(f'{service}/query', params))['features']
        out.extend(batch)
        if len(batch) < page:
            return json.dumps({'type': 'FeatureCollection', 'features': out})
        offset += len(batch)
        time.sleep(0.5)


def nomis_table(dataset, filters):
    """A Nomis table for every 2022 parish, paged at the API's 25,000-row cap."""
    rows, offset = [], 0
    while True:
        params = dict(filters, geography='TYPE160', measures=20100, recordlimit=25000, recordoffset=offset,
                      select='geography_code,geography_name,' + ','.join(k for k in filters) + ',obs_value')
        text = get(f'{NOMIS}/{dataset}.data.csv', params).decode('utf-8-sig')
        batch = list(csv.DictReader(io.StringIO(text)))
        rows.extend(batch)
        if len(batch) < 25000:
            break
        offset += 25000
        time.sleep(1)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


WIKIDATA_P3118 = """
SELECT ?i ?v ?manor ?deserted ?label ?geonames ?osm ?vobPlace ?vobUnit ?tna ?gss ?coord ?enwiki WHERE {{
  ?i wdt:P3118 ?v . FILTER(STRSTARTS(?v, "{prefix}"))
  BIND(EXISTS {{ ?i wdt:P31 wd:Q2116450 }} AS ?manor)
  BIND(EXISTS {{ VALUES ?lost {{ wd:Q21751582 wd:Q350895 }} ?i wdt:P31 ?lost }} AS ?deserted)
  OPTIONAL {{ ?i rdfs:label ?label FILTER(LANG(?label) = "en") }}
  OPTIONAL {{ ?i wdt:P1566 ?geonames }}
  OPTIONAL {{ ?i wdt:P402 ?osm }}
  OPTIONAL {{ ?i wdt:P3616 ?vobPlace }}
  OPTIONAL {{ ?i wdt:P3615 ?vobUnit }}
  OPTIONAL {{ ?i wdt:P3029 ?tna }}
  OPTIONAL {{ ?i wdt:P836 ?gss }}
  OPTIONAL {{ ?i wdt:P625 ?coord }}
  OPTIONAL {{ ?enwiki schema:about ?i ; schema:isPartOf <https://en.wikipedia.org/> }}
}}"""

WIKIDATA_PARISHES = """
SELECT ?i ?gss ?label ?geonames ?osm ?vobPlace ?vobUnit ?coord ?enwiki WHERE {{
  ?i wdt:P836 ?gss . FILTER(STRSTARTS(?gss, "{prefix}"))
  OPTIONAL {{ ?i rdfs:label ?label FILTER(LANG(?label) = "en") }}
  OPTIONAL {{ ?i wdt:P1566 ?geonames }}
  OPTIONAL {{ ?i wdt:P402 ?osm }}
  OPTIONAL {{ ?i wdt:P3616 ?vobPlace }}
  OPTIONAL {{ ?i wdt:P3615 ?vobUnit }}
  OPTIONAL {{ ?i wdt:P625 ?coord }}
  OPTIONAL {{ ?enwiki schema:about ?i ; schema:isPartOf <https://en.wikipedia.org/> }}
}}"""


def sparql_batches(template, prefixes):
    """
    One query per prefix rather than one for everything: each stays well inside WDQS's 60 s limit,
    and a failure costs one batch. The pause is the service's own etiquette, not a rate we measured.
    """
    rows, header = [], None
    for prefix in prefixes:
        text = get(WDQS, {'query': template.format(prefix=prefix)}, accept='text/csv').decode('utf-8')
        lines = list(csv.reader(io.StringIO(text)))
        header = lines[0]
        rows.extend(lines[1:])
        time.sleep(2)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue()


def iod_file7():
    """The File 7 asset URL is resolved from GOV.UK's content API, since asset URLs change on reissue."""
    page = json.loads(get('https://www.gov.uk/api/content/government/statistics/english-indices-of-deprivation-2025'))
    url = next(a['url'] for a in page['details']['attachments'] if a.get('title', '').startswith('File 7'))
    return get(url)


def ipn_csv():
    with zipfile.ZipFile(io.BytesIO(get(SOURCES['ipn']['url']))) as z:
        name = next(n for n in z.namelist() if n.lower().endswith('.csv'))
        return z.read(name)


def fetch_all(cache, grid_prefixes):
    """Fetch (or reuse) every source. Returns name -> local path."""
    p = {}
    p['opendomesday'] = cache.keep('opendomesday-sitemap.xml', lambda: get('https://opendomesday.org/sitemap.xml'))
    p['wd_p3118'] = cache.keep('wikidata-p3118.csv', lambda: sparql_batches(WIKIDATA_P3118, grid_prefixes))
    p['wd_parishes'] = cache.keep('wikidata-p836-parishes.csv',
                                  lambda: sparql_batches(WIKIDATA_PARISHES, ['E04', 'W04']))
    p['parishes'] = cache.keep('parncp22-bgc.geojson', lambda: arcgis_features(
        SOURCES['parishes']['url'], ['PARNCP22CD', 'PARNCP22NM', 'Shape__Area']))
    p['parish_lad'] = cache.keep('par22-wd22-lad22.geojson', lambda: arcgis_features(
        SOURCES['parish_lad']['url'], ['PAR22CD', 'PAR22NM', 'LAD22CD', 'LAD22NM'], geometry=False))
    p['lads'] = cache.keep('lad22-bgc.geojson', lambda: arcgis_features(
        SOURCES['lads']['url'], ['LAD22CD', 'LAD22NM']))
    p['lsoas'] = cache.keep('lsoa21-bgc.geojson', lambda: arcgis_features(
        SOURCES['lsoas']['url'], ['LSOA21CD', 'LSOA21NM']))
    p['ruc'] = cache.keep('lsoa21-ruc21.geojson', lambda: arcgis_features(
        SOURCES['ruc']['url'], ['LSOA21CD', 'RUC21CD', 'RUC21NM', 'Urban_rural_flag'], geometry=False))
    p['pp002'] = cache.keep('nomis-pp002-residents.csv', lambda: nomis_table('NM_2352_1', {'c_sex': 0}))
    p['pp001'] = cache.keep('nomis-pp001-households.csv', lambda: nomis_table('NM_2351_1', {'c2021_hh_1': 0}))
    p['pp012'] = cache.keep('nomis-pp012-age.csv', lambda: nomis_table('NM_2362_1', {'c2021_age_4b': '1,2,3'}))
    p['iod'] = cache.keep('iod2025-file7.csv', iod_file7)
    p['ipn'] = cache.keep('ipn-gb-2024.csv', ipn_csv)
    return p
