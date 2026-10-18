"""
Generate tests/questions.generated.yml — the bulk of the natural-language battery — from the realm's
own shape, as the realm spec asks: per figure, the count in every county and in all England; per
ranked measure, the superlative both ways; per place and per person, the questions people actually
ask about one; and an adversarial half the sources cannot answer.

Subjects are chosen from reference/ deterministically (no randomness), so the file is stable and a
diff of it means the realm changed. Phrasings rotate so that no single wording carries a category.

    python3 tests/generate_questions.py        # rewrites tests/questions.generated.yml

The hand-written tests/questions.yml stays the place for questions a person actually asked.
"""
import collections
import glob
import os

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(pattern):
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'reference', pattern))):
        out += yaml.safe_load(open(f, encoding='utf-8'))
    return out


COUNTY_FIGURES = [
    # (column, noun phrase, phrasings)
    ('villagers', 'villagers', ['How many villagers were there in {c}?', 'how many villagers in {c} in 1086', 'Number of villagers recorded in {c}']),
    ('smallholders', 'smallholders', ['How many smallholders were recorded in {c}?', 'how many smallholders did {c} have']),
    ('slaves', 'slaves', ['How many slaves were there in {c}?', 'how many slaves did Domesday record in {c}', 'count the slaves in {c}']),
    ('households', 'households', ['How many households were recorded in {c}?', 'how many households in {c}']),
    ('mills', 'mills', ['How many mills were there in {c}?', 'how many mills did {c} have in 1086']),
    ('ploughTeams', 'plough teams', ['How many plough teams were there in {c}?', 'how many ploughs in {c}']),
    ('churchEntries', 'churches', ['How many churches were recorded in {c}?', 'how many entries in {c} mention a church']),
    ('wasteEntries', 'waste', ['How many manors in {c} were waste?', 'how much waste was there in {c}']),
    ('entries', 'entries', ['How many Domesday entries are there for {c}?', 'how many entries does {c} have in Domesday']),
    ('value1086Pence', 'value', ['What was {c} worth in 1086?', 'total annual value of {c} in 1086']),
    ('value1066Pence', 'value 1066', ['What was {c} worth before the Conquest?', 'value of {c} in 1066']),
    ('cottagers', 'cottagers', ['How many cottagers were there in {c}?']),
    ('priests', 'priests', ['How many priests were recorded in {c}?']),
    ('meadowAcres', 'meadow', ['How many acres of meadow were there in {c}?']),
    ('woodlandPigs', 'woodland', ['How much woodland, in pigs, did {c} have?']),
    ('castleEntries', 'castles', ['How many castles were there in {c}?']),
]

ENGLAND = [
    ('villagers', ['How many villagers were there in England in 1086?', 'total villagers in Domesday']),
    ('slaves', ['How many slaves were there in England?', 'how many slaves does Domesday record altogether']),
    ('households', ['how many households were there in England in 1086']),
    ('mills', ['How many mills were there in England in 1086?', 'total number of mills in Domesday']),
    ('ploughTeams', ['How many plough teams were there in all of England?']),
    ('churchEntries', ['How many churches are recorded in Domesday?']),
    ('castleEntries', ['How many castles are mentioned in Domesday?']),
    ('wasteEntries', ['How many manors were waste in 1086?']),
    ('entries', ['How many entries are there in Great Domesday?']),
    ('value1086Pence', ['What was England worth in 1086?', 'total value of all the manors in 1086']),
    ('value1066Pence', ['What was England worth before the Conquest?']),
    ('sheep', ['How many sheep are recorded in Domesday?']),
    ('goats', ['how many goats there are in england', 'How many goats did Domesday count?']),
    ('cattle', ['How many cattle were there in England in 1086?']),
    ('smallholders', ['How many smallholders were there in England?']),
    ('priests', ['How many priests does Domesday record?']),
]

RANKINGS = [
    # (measure, most phrasing, fewest phrasing)
    ('mills', 'Which county had the most mills?', 'Which county had the fewest mills?'),
    ('slaves', 'Which county had the most slaves?', 'which county had the fewest slaves'),
    ('villagers', 'Which county had the most villagers?', None),
    ('households', 'Which county has the most people?', 'Which county had the smallest population?'),
    ('value1086', 'Which county was the richest in 1086?', 'Which county was the poorest in 1086?'),
    ('value1066', 'Which county was the richest before the Conquest?', None),
    ('waste', 'Which county had the most waste?', None),
    ('castles', 'Which county had the most castles?', None),
    ('churches', 'Which county had the most churches?', None),
    ('markets', 'Which county had the most markets?', None),
    ('ploughTeams', 'Which county had the most plough teams?', None),
    ('freemen', 'Which county had the most freemen?', None),
    ('burgesses', 'which county had the most burgesses', None),
    ('sheep', 'Which county had the most sheep?', None),
    ('meadowAcres', 'Which county had the most meadow?', None),
    ('woodlandPigs', 'Which county had the most woodland?', None),
    ('smallholders', 'which county had most smallholders', None),
    ('entries', 'Which county has the most Domesday entries?', 'Which county has the fewest entries?'),
]

ADVERSARIAL = [
    ('Were there more slaves before or after the Conquest?', 'note'),
    ('Did the number of villagers fall after 1066?', 'note'),
    ('Was the population of England bigger in 1066 or in 1086?', 'note'),
    ('How many slaves were there in 1066?', True),
    ('How many villagers were there in Essex?', True),
    ('What was the population of Norfolk in 1086?', True),
    ('How many mills were there in Suffolk?', True),
    ('What was Essex worth in 1086?', True),
    ('How many churches were there in Norfolk?', True),
    ('What is the modern population of Abberley?', True),
    ('How many people live in Worcestershire today?', True),
    ('What was the name of the priest at Abberley?', False),
    ('Name the villagers who lived at Abberley', False),
    ('Quote the Domesday text for Abberley', False),
    ('Who held Abberley in 1200?', False),
    ('What was Kent worth in 1100?', True),
    ('How many acres of arable land were there in Kent?', True),
    ('How many horses were there in England in 1086?', True),
    ('How many children lived in Kent in 1086?', True),
    ('What was the average age of villagers in 1086?', True),
    ('How many women lived in Yorkshire in 1086?', True),
    ('What religion were the villagers of Kent?', False),
    ('How many people lived in Scotland in 1086?', True),
    ('What did a villager earn per year in 1086?', True),
    ('How much tax did Kent pay in euros?', True),
    ('Which villager in Kent was the richest?', False),
    ('How many people were killed in the Harrying of the North?', True),
    ('What was the weather in 1086?', False),
    ('How many sheep were there in Essex?', True),
]


def main():
    counties = [r['data'] for r in load('01-counties-*.yml') if r['data']['inGreatDomesday']]
    entries = [r for r in load('05-entries-*.yml')]
    places = {r['data']['placeId']: r['data'] for r in load('03-places-*.yml')}
    people = {r['data']['personId']: r['data'] for r in load('04-people-*.yml')}

    answerable = []

    def q(text, view, column, args=None, category=''):
        mv = {'name': view, 'column': column}
        if args:
            mv['args'] = args
        answerable.append({'question': text, 'category': category, 'expect': {'matchesView': mv}})

    # counts per county: every county, three figures each, rotating figure and phrasing
    for i, c in enumerate(sorted(counties, key=lambda c: c['code'])):
        for k in range(3):
            column, _, phrasings = COUNTY_FIGURES[(i * 3 + k) % len(COUNTY_FIGURES)]
            text = phrasings[(i + k) % len(phrasings)].format(c=c['name'] if k != 1 else c['name'].lower())
            q(text, 'DomesdayCountyFigures', column, {'county': c['code']}, 'county-count')

    # PEOPLE are answered as households with an estimate — the view says so, and so must the answer
    for text in ['How many people were there in England in total?', 'What was the population of England in Domesday?',
                 'how many inhabitants did England have in 1086']:
        answerable.append({'question': text, 'category': 'population',
                           'expect': {'matchesView': {'name': 'DomesdayPopulation', 'column': ['households', 'estimatedPeopleLow', 'estimatedPeopleHigh']}, 'columnsLike': ['estimat']}})
    for code, name in [('KEN', 'Kent'), ('YKS', 'Yorkshire'), ('LIN', 'Lincolnshire'), ('DEV', 'Devon')]:
        answerable.append({'question': f'How many people lived in {name} in 1086?', 'category': 'population',
                           'expect': {'matchesView': {'name': 'DomesdayPopulation', 'column': ['households', 'estimatedPeopleLow', 'estimatedPeopleHigh'], 'args': {'county': code}}, 'columnsLike': ['estimat']}})
    # before and after the Conquest: values compare; people were counted in 1086 only
    for text, args in [('Was England worth more before or after the Conquest?', {}), ('Did land values rise or fall after 1066?', {}),
                       ('Did Yorkshire lose value after the Conquest?', {'county': 'YKS'}), ('Was Kent richer in 1066 or in 1086?', {'county': 'KEN'}),
                       ('Did Sussex lose value after the Conquest?', {'county': 'SUS'})]:
        answerable.append({'question': text, 'category': 'before-after',
                           'expect': {'matchesView': {'name': 'DomesdayBeforeAndAfter', 'column': ['value1066Pounds', 'value1086Pounds', 'valueChangePercent', 'comparableEntries'], **({'args': args} if args else {})}}})
    for column, phrasings in ENGLAND:
        for text in phrasings:
            q(text, 'DomesdayCountyFigures', column, None, 'england-total')

    for measure, most, fewest in RANKINGS:
        q(most, 'DomesdayCountyRanking', 'county', {'measure': measure}, 'county-ranking')
        if fewest:
            q(fewest, 'DomesdayCountyRanking', 'county', {'measure': measure, 'order': 'asc'}, 'county-ranking')

    # places: one manor entry, a name no other place shares, every figure we ask about stated
    name_count = collections.Counter(p['name'].lower() for p in places.values())
    describes = collections.defaultdict(list)
    roles = collections.defaultdict(lambda: collections.defaultdict(list))
    for e in entries:
        for rel in e['relations']:
            to = rel['to']
            if rel['predicate'] == 'DESCRIBES':
                describes[to['placeId']].append(e)
            elif to.get('type') == 'DomesdayPerson':
                roles[e['data']['entryId']][rel['predicate']].append(people[to['personId']]['name'])
    chosen = []
    for pid, es in describes.items():
        p = places[pid]
        if len(es) != 1 or name_count[p['name'].lower()] != 1 or len(p['name']) < 5 or not p['name'].isalpha():
            continue
        d = es[0]['data']
        r = roles[d['entryId']]
        if all(k in d for k in ('value1086', 'value1066', 'villagers')) and len(r['LORD_1066']) == 1 and len(r['TENANT_IN_CHIEF']) == 1:
            chosen.append((d.get('value1086', 0), pid, p))
    chosen.sort(key=lambda t: (-t[0], t[1]))
    picked, seen_counties = [], set()
    for _, pid, p in chosen:
        if p['county'] in seen_counties:
            continue
        seen_counties.add(p['county'])
        picked.append((pid, p))
        if len(picked) == 25:
            break
    place_qs = [
        ('What was {p} worth in 1086?', 'value1086Pence'),
        ('Who held {p} before 1066?', 'lords1066'),
        ('How many villagers lived at {p}?', 'villagers'),
        ('Who was the tenant-in-chief of {p} in 1086?', 'tenantsInChief'),
        ('What was {p} worth before the Conquest?', 'value1066Pence'),
        ('who owned {p} in 1086', 'tenantsInChief'),
    ]
    for i, (pid, p) in enumerate(picked):
        for k in range(3):
            text, column = place_qs[(i + k) % len(place_qs)]
            q(text.format(p=p['name']), 'DomesdayPlaceEntries', column, {'placeId': pid}, 'place')

    # people: the great tenants-in-chief and the great lords of 1066, by Hull's exact name
    value_by = collections.defaultdict(lambda: collections.Counter())
    for e in entries:
        for rel in e['relations']:
            if rel['predicate'] in ('TENANT_IN_CHIEF', 'LORD_1066'):
                name = people[rel['to']['personId']]['name']
                value_by[rel['predicate']][name] += e['data'].get('value1086' if rel['predicate'] == 'TENANT_IN_CHIEF' else 'value1066', 0)
    natural = lambda n: n.replace('/of ', ' of ').replace('/', ' ').replace('(', '').replace(')', '')
    tics = [n for n, _ in value_by['TENANT_IN_CHIEF'].most_common(14) if not n.startswith('King ') and ',' not in n]
    for i, n in enumerate(tics[:10]):
        q([f"How much was {natural(n)}'s land worth in 1086?", f'How many manors did {natural(n)} hold in 1086?',
           f'In how many counties did {natural(n)} hold land as a tenant-in-chief?'][i % 3], 'DomesdayPersonSummary',
          ['value1086Pence', 'entries', 'countyCount'][i % 3], {'name': n}, 'person')
    lords = [n for n, _ in value_by['LORD_1066'].most_common(12) if ',' not in n and not n.startswith('King ')]
    for n in lords[:8]:
        answerable.append({'question': f'Who took over the lands of {natural(n)} after the Conquest?', 'category': 'conquest',
                           'expect': {'minRows': 2}})

    for text in ['Which lords ruled the most peasants?', 'which lords rule the most peasants']:
        answerable.append({'question': text, 'category': 'lords-peasants', 'expect': {'anyName': ['King William', 'King Edward']}})
    for text, role in [
                       ('Who had the most people living on their land in 1086?', None),
                       ('Which tenant-in-chief had the most villagers?', None),
                       ('Which English lord had the most households under him before 1066?', 'LORD_1066'),
                       ('Who were the biggest landlords by number of households before the Conquest?', 'LORD_1066')]:
        q(text, 'DomesdayLordsByPeasants', 'holder', {'role': role} if role else None, 'lords-peasants')

    for text, view, column, args in [
        ('Who was the richest landholder in 1086?', 'DomesdayGreatestLandholders', 'tenantInChief', None),
        ('Who held the most valuable land before 1066?', 'DomesdayGreatestLords1066', 'lord1066', None),
        ('Which was the most valuable manor in 1086?', 'DomesdayRichestManors', 'places', None),
        ('What was the richest manor in Kent?', 'DomesdayRichestManors', 'places', {'county': 'KEN', 'limit': 5}),
        ('What was the richest manor in Yorkshire?', 'DomesdayRichestManors', 'places', {'county': 'YKS', 'limit': 5}),
        ('Which hundred of Worcestershire was worth most in 1086?', 'DomesdayHundredSummary', 'hundred', {'county': 'WOR'}),
        ('Which hundred of Kent was richest?', 'DomesdayHundredSummary', 'hundred', {'county': 'KEN'}),
        ('Which woman held the most land in Domesday?', 'DomesdayWomenLandholders', 'woman', None),
    ]:
        q(text, view, column, args, 'superlative')

    for text, n in [('Where were the castles in Domesday?', 10), ('List the waste manors in Yorkshire', 20),
                    ('Which places in Kent had a church?', 10), ('Which women held land in 1086?', 5),
                    ('List the hundreds of Worcestershire', 5), ('Which places had markets in 1086?', 10),
                    ('Which manors lost the most value after 1066?', 5), ('Which manors gained most in value by 1086?', 5),
                    ('List the places in Domesday called Norton', 20), ('Which places in Devon had salt-houses?', 3),
                    ('What did Ralph of Tosny hold?', 5), ('Which manors had more than ten mills?', 1),
                    ('Show me manors with more than 100 villagers', 3), ('Which places had fisheries in Lincolnshire?', 3)]:
        answerable.append({'question': text, 'category': 'list', 'expect': {'minRows': n}})

    unanswerable = [{'question': t, 'repeat': 3, 'noFigure': nf} for t, nf in ADVERSARIAL]

    out = os.path.join(ROOT, 'tests', 'questions.generated.yml')
    with open(out, 'w', encoding='utf-8') as f:
        f.write('# Generated by tests/generate_questions.py from reference/ — do not edit by hand.\n'
                '# Questions a person actually asked go in tests/questions.yml.\n\n')
        yaml.safe_dump({'answerable': answerable, 'unanswerable': unanswerable}, f, sort_keys=False, allow_unicode=True, width=200)
    cats = collections.Counter(a['category'] for a in answerable)
    print(f'{len(answerable)} answerable ({dict(cats)}), {len(unanswerable)} unanswerable x3')


if __name__ == '__main__':
    main()
