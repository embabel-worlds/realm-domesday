"""
Generate tests/questions.groundtruth.yml — questions whose expected answer is a LITERAL fact from a
source this realm did not produce, so the battery cannot pass by agreeing with itself.

Two sources:

- Open Domesday's manor pages (opendomesday.org), whose figures and owners were coded by hand at the
  University of Hull, separately from the Phillimore text this realm parses. Read from the pages
  tests/check_against_opendomesday.py cached; run that first. Only places with exactly one manor,
  under a name no other place shares, are used, so the question has one right answer.
- A short list of facts any history of the Conquest states.

The matchesView questions in the other files test that a question in words reaches the right figure
in the graph; these test that the figure in the graph is the TRUE one. A failure here with a passing
matchesView twin means the realm's data is wrong, not the generator.

    .cache/venv/bin/python tests/generate_groundtruth.py
"""
import collections
import glob
import os
import re
import sys

import yaml
from bs4 import BeautifulSoup, Comment

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from check_against_opendomesday import od_manors  # noqa: E402

PAGES = os.path.join(ROOT, '.cache', 'opendomesday', 'place')


def owners(html):
    """Per Phillimore reference, the 1066 lord and 1086 tenant-in-chief Open Domesday names."""
    out = {}
    body = html.split('<!-- Each entry -->', 1)[-1].split('<!-- Help text -->', 1)[0]
    for block in body.split('<hr/>'):
        soup = BeautifulSoup(block, 'html.parser')
        for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
            c.extract()
        text = re.sub(r'\s+', ' ', soup.get_text(' '))
        ref = re.search(r'Phillimore reference\s*:\s*(.+?\d[\w,\-]*)', text)
        if not ref:
            continue
        lord = re.search(r'Lord in 1066\s*:\s*(.+?)\s*\.\s', text)
        tic = re.search(r'Tenant-in-chief in 1086\s*:\s*(.+?)\s*\.\s', text)
        out[ref.group(1).strip()] = {'lord1066': lord and lord.group(1).strip(), 'tic1086': tic and tic.group(1).strip()}
    return out


def core(name):
    """The part of a name that identifies its bearer: before any comma, parenthesis or slash."""
    return re.split(r'[,(/]', name)[0].strip()


HISTORY = [
    # (question, expectation) — facts a history of the Conquest states; none is derived from this realm
    ('Who was the richest landholder in England in 1086?', {'name': 'King William'}),
    ('Who held the most land in 1086?', {'name': 'King William'}),
    ('Which county had the most waste in 1086?', {'name': 'Yorkshire'}),
    ('Where was the Harrying of the North most visible in Domesday — which county had most waste?', {'name': 'Yorkshire'}),
    ("Who was the richest lord before the Conquest, after the king?", {'name': 'Harold'}),
    ('Which earl held the most valuable land in 1066?', {'name': 'Harold'}),
    # not Hastings: the castle town has no entry of its own (it is named inside Bullington and others), so no
    # "who held <place>" reaches the Count of Eu; Rye's single entry names its holder outright
    ('Who held Rye in Sussex in 1086?', {'name': 'Fécamp'}),
    ('Which bishop was the richest tenant-in-chief in 1086?', {'name': 'Odo'}),
    ("Who was William the Conqueror's half-brother who held most land in Kent?", {'name': 'Odo'}),
    ('Which countess held the most land in 1086?', {'name': 'Judith'}),
    ('Which queen held land before the Conquest?', {'name': 'Edith'}),
    ('Who held the most land in Cheshire in 1086?', {'name': 'Hugh'}),
    ('Who held the most land in Shropshire in 1086?', {'name': 'Roger'}),
]


def main():
    places = []
    for f in glob.glob(os.path.join(ROOT, 'reference', '03-places-*.yml')):
        places += [r['data'] for r in yaml.safe_load(open(f, encoding='utf-8'))]
    # Open Domesday showing one manor is not enough: the realm must hold one entry about the place too, or the
    # question has two answers (Romney Marsh is one manor there and six entries here)
    entries_about = collections.Counter()
    for f in glob.glob(os.path.join(ROOT, 'reference', '05-entries-*.yml')):
        for r in yaml.safe_load(open(f, encoding='utf-8')):
            for rel in r.get('relations', []):
                if rel['predicate'] == 'DESCRIBES':
                    entries_about[rel['to']['placeId']] += 1
    name_count = collections.Counter(p['name'].lower() for p in places)
    by_grid = collections.defaultdict(list)
    for p in places:
        if p.get('gridRef'):
            by_grid[p['gridRef']].append(p)

    questions = []
    used = 0
    # one county at a time, round robin, so no county carries the tier
    by_county = collections.defaultdict(list)
    for path in sorted(glob.glob(os.path.join(PAGES, '*', '*.html'))):
        grid = path.split(os.sep)[-2]
        county = next((p['county'] for p in by_grid.get(grid, [])), '?')
        by_county[county].append(path)
    queues = [collections.deque(v) for _, v in sorted(by_county.items())]
    ordered = []
    while any(queues):
        for qu in queues:
            if qu:
                ordered.append(qu.popleft())
    for path in ordered:
        grid, slug = path.split(os.sep)[-2], os.path.basename(path)[:-5]
        candidates = [p for p in by_grid.get(grid, []) if re.sub(r'[^a-z0-9]+', '-', p['name'].lower()).strip('-') == slug]
        if len(candidates) != 1:
            continue
        place = candidates[0]
        if name_count[place['name'].lower()] != 1 or not re.fullmatch(r"[A-Za-z' ]+", place['name']):
            continue
        if entries_about[place['placeId']] != 1:
            continue
        html = open(path, encoding='utf-8').read()
        manors, who = od_manors(html), owners(html)
        if len(manors) != 1:
            continue
        ref, figures = next(iter(manors.items()))
        name, county = place['name'], place['countyName']
        k = used % 4
        if k == 0 and 'villagers' in figures:
            questions.append({'question': f'How many villagers lived at {name} in {county}?', 'category': 'opendomesday',
                              'expect': {'value': figures['villagers']}, 'realm': {'view': 'DomesdayPlaceEntries', 'args': {'placeId': place['placeId']}, 'column': 'villagers'}, 'source': f'Open Domesday {ref}'})
        elif k == 1 and 'value1086' in figures:
            questions.append({'question': f'What was {name} in {county} worth in 1086?', 'category': 'opendomesday',
                              'expect': {'value': figures['value1086'], 'money': True}, 'realm': {'view': 'DomesdayPlaceEntries', 'args': {'placeId': place['placeId']}, 'column': 'value1086Pence'}, 'source': f'Open Domesday {ref}'})
        elif k == 2 and who.get(ref, {}).get('lord1066'):
            questions.append({'question': f'Who held {name} in {county} before the Conquest?', 'category': 'opendomesday',
                              'expect': {'name': core(who[ref]['lord1066'])}, 'realm': {'view': 'DomesdayPlaceEntries', 'args': {'placeId': place['placeId']}, 'column': 'lords1066'}, 'source': f'Open Domesday {ref}'})
        elif k == 3 and who.get(ref, {}).get('tic1086'):
            questions.append({'question': f'Who was the tenant-in-chief of {name} in {county} in 1086?', 'category': 'opendomesday',
                              'expect': {'name': core(who[ref]['tic1086'])}, 'realm': {'view': 'DomesdayPlaceEntries', 'args': {'placeId': place['placeId']}, 'column': 'tenantsInChief'}, 'source': f'Open Domesday {ref}'})
        else:
            continue
        used += 1
        if used >= 80:
            break

    for q, expect in HISTORY:
        questions.append({'question': q, 'category': 'history', 'expect': expect, 'source': 'the historical record'})

    out = os.path.join(HERE, 'questions.groundtruth.yml')
    with open(out, 'w', encoding='utf-8') as f:
        f.write('# Generated by tests/generate_groundtruth.py — expected answers are literal facts from Open Domesday\n'
                '# (coded by hand at Hull) or the historical record, never from this realm. Do not edit by hand.\n\n')
        yaml.safe_dump({'answerable': questions}, f, sort_keys=False, allow_unicode=True, width=200)
    print(f'{len(questions)} ground-truth questions '
          f'({sum(q["category"] == "opendomesday" for q in questions)} from Open Domesday, {len(HISTORY)} from history)')


if __name__ == '__main__':
    main()
