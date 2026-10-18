"""
Reconcile the parsed manorial figures against Open Domesday, field by field.

Open Domesday (opendomesday.org) publishes the figures of the Hull dataset per manor. They were
coded by hand at Hull, separately from the Phillimore text this realm parses, so agreement is
evidence and disagreement is a parser defect or a real difference worth reading.

Samples single-place manorial entries with a fixed seed, fetches each place page once (cached in
.cache/opendomesday/, one request a second), finds the manor with the same Phillimore reference,
and compares every figure Open Domesday states. Exits non-zero when a field's agreement falls below
its floor.

    .cache/venv/bin/python tests/check_against_opendomesday.py [sample=150]
"""
import csv
import json
import os
import random
import re
import sys
import time
import urllib.request

from bs4 import BeautifulSoup, Comment

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import figures  # noqa: E402

CACHE = os.path.join(ROOT, '.cache')
OD = os.path.join(CACHE, 'opendomesday')
SITE = 'https://opendomesday.org'

"""
The floor each field must reach: a little under what 450 manors measured on 2026-10-18 (300 of them
unseen while the parser was tuned). Population, meadow and mills are near-mechanical in the text.
Plough teams and assessment are phrased differently in every circuit, and Devon and Cornwall are
Phillimore's condensation of Exeter Domesday, whose lord/men split the text no longer carries — so
those floors are lower, and say so, rather than pretending to an exactness the source lacks.
"""
FLOORS = {'villagers': 0.95, 'smallholders': 0.95, 'slaves': 0.95, 'mills': 0.95, 'meadowAcres': 0.95,
          'cottagers': 0.9, 'freemen': 0.9, 'priests': 0.9, 'woodlandPigs': 0.9, 'value1066': 0.9,
          'value1086': 0.88, 'mensTeams': 0.85, 'geldUnits': 0.8, 'lordsTeams': 0.78}

"""
Open Domesday rounds: geld units to two places, and values, which it appears to hold as decimal
pounds, to within a few pence (£17 11s 4d is 4,216d; it shows 4,214).
"""
TOLERANCE = {'geldUnits': 0.01, 'value1086': 4, 'value1066': 4}

OD_POP = {'villagers': 'villagers', 'villager': 'villagers', 'smallholders': 'smallholders',
          'smallholder': 'smallholders', 'slaves': 'slaves', 'slave': 'slaves', 'cottagers': 'cottagers',
          'cottager': 'cottagers', 'freemen': 'freemen', 'freeman': 'freemen', 'priests': 'priests',
          'priest': 'priests', 'burgesses': 'burgesses', 'burgess': 'burgesses'}


def rows(name):
    with open(os.path.join(CACHE, 'csv', name + '.csv'), encoding='utf-8') as f:
        return list(csv.DictReader(f))


def fetch(url, path):
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        time.sleep(1)
        req = urllib.request.Request(url, headers={'User-Agent': 'realm-domesday reconciliation'})
        with urllib.request.urlopen(req, timeout=30) as r:
            open(path, 'wb').write(r.read())
    return open(path, encoding='utf-8').read()


def money(text):
    pence = 0
    for n, unit in re.findall(r'([\d.]+)\s+(pound|shilling|pence|penny)', text):
        pence += float(n) * {'pound': 240, 'shilling': 12}.get(unit, 1)
    return pence


def od_manors(html):
    """Open Domesday manor blocks keyed by Phillimore reference, each a dict of figures."""
    out = {}
    # manors follow the first "Each entry" comment, one per <hr/>, until the help text
    body = html.split('<!-- Each entry -->', 1)[-1].split('<!-- Help text -->', 1)[0]
    for block in body.split('<hr/>'):
        soup = BeautifulSoup(block, 'html.parser')
        for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
            c.replace_with(' ' + c + ' ')
        text = re.sub(r'\s+', ' ', soup.get_text(' '))
        ref = re.search(r'Phillimore reference\s*:\s*(.+?\d[\w,\-]*)', text)
        if not ref:
            continue
        f = {}
        pop = re.search(r'Households[^:]{0,160}:(.*?)(?:Land and resources|Valuation|Owners|$)', text)
        if pop:
            for n, word in re.findall(r'([\d.]+)\s+([A-Za-z]+)', pop.group(1)):
                key = OD_POP.get(word.lower())
                if key:
                    f[key] = f.get(key, 0) + float(n)
        for n in re.findall(r"([\d.]+) lord's plough teams", text):
            f['lordsTeams'] = float(n)
        for n in re.findall(r"([\d.]+) men's plough teams", text):
            f['mensTeams'] = float(n)
        m = re.search(r'Taxable value ([\d.]+) geld units', text)
        if m:
            f['geldUnits'] = float(m.group(1))
        m = re.search(r'Annual value to lord\s*:(.*?)(?:Taxable|Owners|Other information|$)', text)
        if m:
            for part in m.group(1).split(';'):
                if 'in 1086' in part:
                    f['value1086'] = money(part)
                elif 'in 1066' in part:
                    f['value1066'] = money(part)
        m = re.search(r'Meadow ([\d.]+) acres', text)
        if m:
            f['meadowAcres'] = float(m.group(1))
        m = re.search(r'Woodland ([\d.]+) pigs', text)
        if m:
            f['woodlandPigs'] = float(m.group(1))
        m = re.search(r'([\d.]+) mills?, value', text)
        if m:
            f['mills'] = float(m.group(1))
        out[ref.group(1).strip()] = f
    return out


def main(sample=150):
    places = {p['PlacesIdx']: p for p in rows('Places')}
    counties = {c['County']: c['CountyName'].title() for c in rows('county')}
    subjects = {}
    for r in rows('PlaceRef'):
        if r['Pcode'][:1] == 'p' and r['StructIdx']:
            subjects.setdefault(r['StructIdx'], set()).add(r['PlacesIdx'])
    entries = [json.loads(l) for l in open(os.path.join(CACHE, 'entries.jsonl'))]
    candidates = [e for e in entries if e['type'] == 'E' and len(subjects.get(e['structIdx'], ())) == 1
                  and places.get(next(iter(subjects[e['structIdx']])), {}).get('OSrefs')]
    random.Random(1086).shuffle(candidates)

    sitemap = fetch(SITE + '/sitemap.xml', os.path.join(OD, 'sitemap.xml'))
    by_grid = {}
    for path in re.findall(r'<loc>https://opendomesday.org(/place/([A-Z]{2}\d{4})/[^<]+)</loc>', sitemap):
        by_grid.setdefault(path[1], []).append(path[0])

    agree, compared, misses, used = {}, {}, {}, 0
    for e in candidates:
        if used >= sample:
            break
        place = places[next(iter(subjects[e['structIdx']]))]
        slug = re.sub(r'[^a-z0-9]+', '-', place['Vill'].lower()).strip('-')
        # the sitemap lists each place twice
        urls = sorted({u for u in by_grid.get(place['OSrefs'], []) if u.rstrip('/').endswith('/' + slug)})
        if len(urls) != 1:
            continue
        manors = od_manors(fetch(SITE + urls[0], os.path.join(OD, urls[0].strip('/') + '.html')))
        od = manors.get(f"{counties.get(e['county'], e['county'])} {e['phillimore']}")
        if od is None:
            continue
        used += 1
        ours = figures.figures(e)
        # Open Domesday counts liberi homines and sokemen together, as freemen
        if 'freeMen' in ours:
            ours['freemen'] = ours.get('freemen', 0) + ours['freeMen']
        for key, value in od.items():
            compared[key] = compared.get(key, 0) + 1
            if abs(float(ours.get(key, 0)) - value) <= TOLERANCE.get(key, 1e-6):
                agree[key] = agree.get(key, 0) + 1
            else:
                misses.setdefault(key, []).append((f"{e['county']} {e['phillimore']}", ours.get(key), value))

    print(f'{used} manors reconciled against Open Domesday')
    failed = False
    for key in sorted(compared, key=lambda k: -compared[k]):
        rate = agree.get(key, 0) / compared[key]
        floor = FLOORS.get(key)
        verdict = '' if floor is None else ('ok' if rate >= floor else f'BELOW {floor:.0%}')
        failed |= verdict.startswith('BELOW')
        print(f'  {key:14} {agree.get(key, 0):4}/{compared[key]:<4} {rate:6.1%}  {verdict}')
        for ref, ours, theirs in misses.get(key, [])[:int(os.environ.get("SHOW", 4))]:
            print(f'      {ref:12} ours={ours} opendomesday={theirs}')
    sys.exit(1 if failed or used == 0 else 0)


if __name__ == '__main__':
    main(*(int(a) for a in sys.argv[1:]))
