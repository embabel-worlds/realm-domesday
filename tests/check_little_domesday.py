"""
Reconcile scripts/little_domesday.py against Open Domesday, field by field, for Little Domesday.

Open Domesday's Essex, Norfolk and Suffolk figures were coded by hand at Hull from the Latin, so
they share neither the text nor the parser this reads. Agreement is evidence the parse is right;
a disagreement is a parser defect or a real difference worth reading. Its 1086 figures are the
ones compared. It states no 1066 or later population, so those fields have nothing to check
against, and the report says so rather than leaving them out silently.

Samples entries with one subject place that has a grid reference, with a fixed seed, fetching
each place page once through check_against_opendomesday.fetch (cached, one request a second).

    .cache/venv/bin/python scripts/little_domesday.py .cache
    .cache/venv/bin/python tests/check_little_domesday.py [sample=120]     # OFFLINE=1: cached pages only
                                                         # SEED=n: another sample (1086 is the tuning one)
"""
import collections
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_against_opendomesday as od  # noqa: E402

CACHE = od.CACHE

"""Open Domesday counts sokemen and free men together, as freemen; so does the comparison."""
COMPARED = ['villagers', 'smallholders', 'slaves', 'freemen', 'priests', 'lordsTeams', 'mensTeams', 'value1086',
            'value1066', 'valueLater', 'geldUnits', 'meadowAcres', 'woodlandPigs', 'mills', 'saltHouses', 'cobs',
            'cattle', 'cows', 'pigs', 'sheep', 'goats', 'beehives', 'cobs1066', 'cattle1066', 'cows1066', 'pigs1066', 'sheep1066',
            'goats1066']
UNCHECKED = ['villagers1066', 'smallholders1066', 'slaves1066', 'lordsTeams1066', 'mensTeams1066', 'taxPence',
             'horses', 'pastureSheep']

"""
Open Domesday rounds as it stores: geld units cut to two places, values to within a few pence, and
meadow held in whole acres with halves rounded to even (4.5 shows as 4, 5.5 as 6).
"""
TOLERANCE = dict(od.TOLERANCE, valueLater=4)
ROUND_EVEN = {'meadowAcres'}
LIVESTOCK = {'cob': 'cobs', 'cobs': 'cobs', 'cattle': 'cattle', 'cow': 'cows', 'cows': 'cows', 'pig': 'pigs', 'pigs': 'pigs', 'sheep': 'sheep',
             'goat': 'goats', 'goats': 'goats', 'beehive': 'beehives', 'beehives': 'beehives'}


def od_extra(html):
    """The Little Domesday resources od_manors does not read: salt-houses and livestock in 1086."""
    out = {}
    body = html.split('<!-- Each entry -->', 1)[-1].split('<!-- Help text -->', 1)[0]
    for block in body.split('<hr/>'):
        text = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', block))
        ref = re.search(r'Phillimore reference\s*:\s*(.+?\d[\w,\-]*)', text)
        if not ref:
            continue
        f = {}
        m = re.search(r'([\d.]+) salthouses?', text)
        if m:
            f['saltHouses'] = float(m.group(1))
        # Little Domesday's mills carry no value, so od_manors' "N mills, value" misses them
        m = re.search(r'Other resources\s*:.*?(?<![\w.])([\d.]+) mills?\b', text)
        if m:
            f['mills'] = float(m.group(1))
        for year, suffix in (('1086', ''), ('1066', '1066')):
            stock = re.search(r'Livestock in ' + year + r'\s*:(.*?)(?:Livestock in|Valuation|Owners|Other|$)', text)
            for n, word in re.findall(r'([\d.]+)\s+([A-Za-z]+)', stock.group(1) if stock else ''):
                if word.lower() in LIVESTOCK:
                    f[LIVESTOCK[word.lower()] + suffix] = float(n)
        # Open Domesday gives royal land "exemption units" where others have geld units
        m = re.search(r'Taxable value ([\d.]+) (?:geld|exemption) units', text)
        if m:
            f['geldUnits'] = float(m.group(1))
        m = re.search(r'Annual value to lord\s*:(.*?)(?:Taxable|Owners|Other information|$)', text)
        for part in (m.group(1).split(';') if m else []):
            if 'when acquired' in part:
                f['valueLater'] = od.money(part)
        out[ref.group(1).strip()] = f
    return out


def main(sample=120):
    data = json.load(open(os.path.join(CACHE, 'little_domesday.json'), encoding='utf-8'))
    places = {p['PlacesIdx']: p for p in od.rows('Places')}
    candidates = []
    for e in data['entries']:
        subject = [r for r in e['placeRefs'] if r['predicate'] == 'DESCRIBES']
        if e['kind'] == 'manor' and len(subject) == 1 and places[subject[0]['placeId']]['OSrefs'][:6].isalnum():
            candidates.append((e, places[subject[0]['placeId']]))
    # SEED draws a different sample: the default one is the sample the parser was tuned against
    random.Random(int(os.environ.get('SEED', 1086))).shuffle(candidates)

    sitemap = od.fetch(od.SITE + '/sitemap.xml', os.path.join(od.OD, 'sitemap.xml'))
    by_grid = collections.defaultdict(list)
    for path, grid in re.findall(r'<loc>https://opendomesday.org(/place/([A-Z]{2}\d{4})/[^<]+)</loc>', sitemap):
        by_grid[grid].append(path)

    agree, compared, misses, used = collections.Counter(), collections.Counter(), collections.defaultdict(list), 0
    for e, place in candidates:
        if used >= sample:
            break
        slug = re.sub(r'[^a-z0-9]+', '-', re.sub(r'\[.*?\]', '', place['Vill']).lower()).strip('-')
        urls = sorted({u for u in by_grid.get(place['OSrefs'].rstrip('*!'), []) if u.rstrip('/').endswith('/' + slug)})
        if len(urls) != 1:
            continue
        path = os.path.join(od.OD, urls[0].strip('/') + '.html')
        # OFFLINE=1 reconciles the pages already cached, for when the site is slow or down
        if os.environ.get('OFFLINE') and not os.path.exists(path):
            continue
        try:
            html = od.fetch(od.SITE + urls[0], path)
        except OSError as e:
            print(f'  skipped {urls[0]}: {e}')
            continue
        theirs = od.od_manors(html).get(e['ref'])
        if theirs is None:
            continue
        theirs.update(od_extra(html).get(e['ref'], {}))
        used += 1
        ours = dict(e)
        ours['freemen'] = ours.get('freemen', 0) + ours.get('freeMen', 0) or ours.get('freemen')
        for key in COMPARED:
            if key not in theirs and key not in ours:
                continue
            compared[key] += 1
            mine = float(ours.get(key) or 0)
            if key in ROUND_EVEN:
                mine = round(mine)
            elif key == 'geldUnits':
                mine = int(mine * 100) / 100
            if abs(mine - float(theirs.get(key, 0))) <= TOLERANCE.get(key, 1e-6):
                agree[key] += 1
            else:
                misses[key].append((e['entryId'], ours.get(key), theirs.get(key)))

    print(f'{used} Little Domesday entries reconciled against Open Domesday')
    for key in sorted(compared, key=lambda k: -compared[k]):
        print(f'  {key:14} {agree[key]:4}/{compared[key]:<4} {agree[key] / compared[key]:6.1%}')
        for ref, ours, theirs in misses[key][:int(os.environ.get('SHOW', 4))]:
            print(f'      {ref:12} ours={ours} opendomesday={theirs}')
    print('  not checkable against Open Domesday (it does not state them):', ', '.join(UNCHECKED))
    sys.exit(0 if used else 1)


if __name__ == '__main__':
    main(*(int(a) for a in sys.argv[1:]))
