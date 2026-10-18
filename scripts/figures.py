"""
Manorial figures from one Domesday Explorer entry.

The Explorer stores no figures as numbers. It stores Phillimore's translation word by word and
codes spans of it: POP is the population clause, LND the arable land and plough teams, TAX the
assessment, VAL the valuation and APP the appurtenances (mills, meadow, woodland, livestock). The
clauses are formulaic, which is what makes them parseable:

    POP  18 villagers 8 smallholders 1 frenchman and 3 cottagers with 17 ploughs a priest and a slave
    LND  land for 6 ploughs in lordship 2 ploughs
    VAL  value before 1066 £7 later £4 now £10 10s

A figure is returned only when its clause says it. An absent key means the entry does not state
it, which is different from zero, so nothing here defaults to 0.

Money is in pence: £1 = 20s = 240d. The text arrives lower case and without punctuation, which
is why "free men" (liberi homines) and "freemen" (Phillimore's word for sokemen) are told apart
by the space and nothing else.
"""
import re

WORDNUM = {'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6,
           'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12}
FRACTION = {'1/2': 0.5, '1/4': 0.25, '3/4': 0.75, '1/3': 1 / 3, '2/3': 2 / 3, '1/8': 0.125}

NUM = r"(\d+(?:\s(?:1/2|1/4|3/4|1/3|2/3|1/8))?|1/2|1/4|3/4|1/3|2/3|1/8|a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"


def number(text):
    text = text.strip()
    if text in WORDNUM:
        return WORDNUM[text]
    if text in FRACTION:
        return FRACTION[text]
    parts = text.split()
    value = float(parts[0])
    if len(parts) > 1:
        value += FRACTION[parts[1]]
    return int(value) if value == int(value) else value


"""
Population. Each category is the plural and singular a clause can use; the first wins, so a
longer phrase ("female slaves", "free men", "men at arms") is listed before anything it contains.
"""
POPULATION = [
    ('freeMen', r'free\s(?:men|man)'),
    ('menAtArms', r'(?:men|man)\sat\sarms'),
    ('slaves', r'(?:female\s)?slaves?'),
    ('villagers', r'villagers?'),
    ('smallholders', r'smallholders?'),
    ('cottagers', r'cottagers?'),
    ('freemen', r'freem[ae]n'),
    ('priests', r'priests?'),
    ('burgesses', r'burgess(?:es)?'),
    ('ploughmen', r'ploughm[ae]n'),
    ('riders', r'riders?'),
    ('frenchmen', r'frenchm[ae]n'),
    ('englishmen', r'englishm[ae]n'),
    ('smiths', r'smiths?'),
    ('swineherds', r'swineherds?'),
    ('beekeepers', r'beekeepers?'),
    ('fishermen', r'fisherm[ae]n'),
]
POP_RE = re.compile(r'\b' + NUM + r'\s(' + '|'.join('(?:%s)' % p for _, p in POPULATION) + r')\b')
POP_KIND = [(k, re.compile(r'^(?:%s)$' % p)) for k, p in POPULATION]


def population(spans):
    out = {}
    for span in spans:
        for m in POP_RE.finditer(span):
            word = m.group(2)
            kind = next(k for k, r in POP_KIND if r.match(word))
            out[kind] = out.get(kind, 0) + number(m.group(1))
    return out


"""
Plough teams, the lord's and the men's. The phrasing varies by circuit, and these are the forms
the text uses:

    in lordship 2 ploughs / in lordship 6 1/2 hides 6 ploughs / in lordship 3 9 villagers   lord's
    1 plough in lordship / 1 plough now in lordship                                         lord's
    land for 1 plough it is there in lordship                                               lord's
    erneis has 4 ploughs / william has in lordship there 5 ploughs                          lord's
    8 villagers and 10 smallholders with 9 ploughs / smallholders have 4 ploughs            men's

A "has N ploughs" is the lord's unless people are named just before it, in which case it is
theirs. A number after "in lordship" that is itself land or people ("in lordship 2 slaves") is not
a team count. Ploughlands ("land for 6 ploughs") are a capacity, not teams, and "4 more ploughs
possible" is neither. Overlapping matches count once.
"""
LAND_UNIT = r'(?:hides?|virgates?|carucates?|bovates?|sulungs?|yokes?|acres?|furlongs?)'
PEOPLE = '|'.join(p for _, p in POPULATION)
NOT_TEAMS = r'(?!\s(?:hides?|virgates?|carucates?|bovates?|sulungs?|yokes?|acres?|furlongs?|' + PEOPLE + r')\b)'
LORD_TEAMS = [
    re.compile(r'in\slordship\s(?:are\s|is\s|there\s(?:is|are)\s)?(?:' + NUM + r'\s' + LAND_UNIT
               + r'(?:\sand\s' + NUM + r'\s' + LAND_UNIT + r')?(?:\sof\sland)?\s)?' + NUM + NOT_TEAMS
               + r'(?:\sploughs?)?'),
    re.compile(r'\b' + NUM + r'\sploughs?\s(?:now\s)?in\slordship\b'),
    re.compile(r'\bland\sfor\s' + NUM + r'\sploughs?\s(?:it\sis|they\sare|which\s(?:is|are))\sthere\sin\slordship\b'),
]
HOLDS_TEAMS = re.compile(r'\b(?:with|have|has)\s(in\slordship\s)?(?:there\s)?' + NUM + r'\sploughs?\b')
PEOPLE_BEFORE = re.compile(r'\b(?:' + PEOPLE + r')\b')
CLAUSE_START = re.compile(r'.*\b(?:ploughs?|land\sfor|value|meadow|woodland|mills?)\b')
PLOUGHLANDS = re.compile(r'\bland\sfor\s' + NUM + r'\sploughs?\b')


def ploughs(text):
    out, taken = {}, []

    def claim(m, key, value):
        if any(m.start() < e and s < m.end() for s, e in taken):
            return
        taken.append((m.start(), m.end()))
        out[key] = out.get(key, 0) + number(value)

    for r in LORD_TEAMS:
        for m in r.finditer(text):
            claim(m, 'lordsTeams', [g for g in m.groups() if g][-1])
    for m in HOLDS_TEAMS.finditer(text):
        before = text[max(0, m.start() - 90):m.start()]
        clause = CLAUSE_START.sub('', before)
        people = not m.group(1) and (m.group(0).startswith('with') or PEOPLE_BEFORE.search(clause))
        claim(m, 'mensTeams' if people else 'lordsTeams', m.groups()[-1])
    for m in PLOUGHLANDS.finditer(text):
        out['ploughlands'] = out.get('ploughlands', 0) + number(m.group(1))
    return out


"""
Assessment, in geld units: the hide in most of England, the carucate in the Danelaw and the
sulung in Kent, each taken as one unit as Open Domesday does, with their fractions. Only the first
assessment in a clause counts — what follows "now" ("now it pays tax for…") is a reduction of the
same holding rather than more of it. A manor's hides may be named in more than one clause ("1 hide in
Blymhill ... in Ruscote 1 hide which belongs to this manor"), so the clauses are summed, each up to
its "now"; a clause that is a church's endowment is not the manor's.
"""
GELD_UNITS = {'hide': 1, 'carucate': 1, 'sulung': 1, 'virgate': 0.25, 'bovate': 0.125, 'yoke': 0.25,
              'acre': 1 / 120}
TAX_RE = re.compile(r'\b' + NUM + r'\s(hide|carucate|sulung|virgate|bovate|yoke|acre)s?\b')


def assessment(spans):
    units = []
    for span in spans:
        if re.match(r'(?:a|the)\schurch\b', span):
            continue
        stop = re.search(r'\bnow\b', span)
        head = span[:stop.start()] if stop else span
        units += [(number(m.group(1)), m.group(2)) for m in TAX_RE.finditer(head)]
    if units:
        return {'geldUnits': round(sum(n * GELD_UNITS[u] for n, u in units), 4)}
    return {}


"""
Valuation. A clause names one or more moments and then an amount, and may do that several times:
"the value was 5s now 50s", "value before 1066 and now £3", "the value is and was 100s before 1066
40s". Moments accumulate until an amount arrives; the amount is assigned to every moment pending,
and the pending set is cleared. A moment named outright (before 1066, now) outranks one implied by
a tense (was, is), so "is and was £6 before 1066 £7" gives 1066 as £7; within a rank the first
amount stands, so "however it pays £12" after "now £8" does not displace it. An amount with no
moment named is the value in 1086.
"""
MOMENTS = [
    (r'before\s1066|formerly', 'value1066', 2),
    (r'was', 'value1066', 1),
    (r'later|afterwards|when\s(?:\w+\s){0,3}(?:acquired|received)|subsequently', 'valueLater', 2),
    (r'now|at\spresent', 'value1086', 2),
    (r'is', 'value1086', 1),
]
MONEY = r'(?:£\s?(?P<l>\d+(?:\s1/2)?))?\s?(?:(?P<s>\d+(?:\s1/2)?)s)?\s?(?:(?P<d>\d+(?:\s1/2)?|1/2)d)?'
VAL_TOKEN = re.compile('|'.join('(?P<m%d>\\b(?:%s)\\b)' % (i, p) for i, (p, _, _) in enumerate(MOMENTS))
                       + r'|(?P<money>(?<![\w£])(?=[£\d])' + MONEY + r'(?![\w/]))')


def pence(m):
    total = 0
    for group, scale in (('l', 240), ('s', 12), ('d', 1)):
        if m.group(group):
            total += number(m.group(group)) * scale
    return total


def valuation(spans):
    out, strength, pending = {}, {}, []
    for span in spans:
        for m in VAL_TOKEN.finditer(span):
            moment = next((MOMENTS[i] for i in range(len(MOMENTS)) if m.group('m%d' % i)), None)
            if moment:
                pending.append(moment)
            elif m.group('money') and (m.group('l') or m.group('s') or m.group('d')):
                amount = pence(m)
                for _, key, rank in (pending or [(None, 'value1086', 0)]):
                    if rank > strength.get(key, -1):
                        out[key], strength[key] = amount, rank
                pending = []
    return out


RESOURCES = [
    ('mills', re.compile(r'\b' + NUM + r'\smills?\b')),
    ('meadowAcres', re.compile(r'\bmeadow\s' + NUM + r'\sacres?\b')),
    ('woodlandPigs', re.compile(r'\bwoodland\s(?:for\s)?' + NUM + r'\spigs\b')),
    ('fisheries', re.compile(r'\b' + NUM + r'\sfisher(?:y|ies)\b')),
    ('saltHouses', re.compile(r'\b' + NUM + r'\ssalt\s?-?\s?houses?\b')),
    ('sheep', re.compile(r'\b' + NUM + r'\ssheep\b')),
    ('cattle', re.compile(r'\b' + NUM + r'\scattle\b')),
    ('goats', re.compile(r'\b' + NUM + r'\sgoats\b')),
]


def resources(spans):
    out = {}
    for span in spans:
        for key, r in RESOURCES:
            for m in r.finditer(span):
                out[key] = out.get(key, 0) + number(m.group(1))
    return out


FLAGS = [
    ('hasChurch', re.compile(r'\bchurch(?:es)?\b')),
    ('hasCastle', re.compile(r'\bcastle\b')),
    ('hasMarket', re.compile(r'\bmarket\b')),
    ('isWaste', re.compile(r'\bwaste\b')),
]


def figures(entry):
    spans = entry.get('spans', {})
    distinct = lambda code: list(dict.fromkeys(spans.get(code, [])))
    pop = distinct('POP')
    out = {}
    out.update(population(pop))
    out.update(ploughs(entry.get('text', '')))
    out.update(assessment(distinct('TAX')))
    out.update(valuation(distinct('VAL')))
    out.update(resources(distinct('APP')))
    households = sum(v for k, v in out.items() if k in dict(POPULATION))
    if households:
        out['households'] = households
    teams = out.get('lordsTeams', 0) + out.get('mensTeams', 0)
    if teams:
        out['ploughTeams'] = teams
    for key, r in FLAGS:
        if r.search(entry.get('text', '')):
            out[key] = True
    return out
