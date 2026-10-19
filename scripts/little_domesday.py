"""
Little Domesday — Essex, Norfolk and Suffolk — entry by entry, from Hull's translation text.

The Domesday Explorer holds no entries for these three counties: its Textbase stops where Great
Domesday does, and Structure, PlaceRef and NameRef have no East Anglian rows. Only its gazetteer
(Places) and its index of names (Names) cover them. Hull's 2025 deposit has the Little Domesday
text, in its "Domesday text translation" (h989r385x), which lies behind no challenge at
/downloads/h989r387g. Hull's statistics database (fn106z48v) may hold the figures as numbers,
but its page sits behind a Cloudflare challenge that a script cannot pass, so its file cannot even
be named. This reads the text instead, and writes <cache>/little_domesday.json in the shape
build_reference.py gives a DomesdayEntry.

Little Domesday states its figures for up to three dates, which Great Domesday rarely does:

    Then 51 villagers, now 60; then 19 smallholders, now 30.       then = 1066, now = 1086
    Then and later 1 plough in lordship, now none.                  later = when acquired
    Always 36 villagers.                                            all three
    Then 3 cobs, 40 cattle, 195 pigs; now 2 cobs ...                a date governs a list

A date applies to every figure after it until another date or the end of the sentence. A number
with no category after it ("now 60") takes the category before it. A figure with no date is
1086's. The 1086 figure goes in the realm's field (villagers, slaves, value1086, …). An earlier
one goes in the same name with 1066 or Later added (villagers1066, slavesLater), and only when the
text states it. An absent key is unstated, never zero, as in figures.py.

What the text cannot give, and so this does not pretend to:

- Hull's coding. There is no StructIdx, Pcode or Tcode. entryId is the reference ("NFK 1,61"),
  which no Explorer StructIdx can collide with. Places and people are joined to Explorer ids
  through the Phillimore references each Places and Names record lists (Names.OldRefs: the
  Phillimore memo is cut at ten characters, and NameRef, which the realm rebuilds it from, has no
  Little Domesday rows). The place named first in upper case is taken as the subject (DESCRIBES),
  the rest as INCLUDES. A tenant-in-chief is the person Names indexes against the whole chapter
  (a bare "7."). Every other role is read from the clause the name stands in (roles_of): the
  subject of held is the lord in 1066, of holds 1086's holder, and a name after "under" the 1066
  overlord. Both are readings, and roleSource says so.
- Ploughlands. Little Domesday has no "land for N ploughs", so there are none.
- The tax as Great Domesday states it. Essex is assessed in hides, and geldUnits is the manor's
  own hidage. Norfolk and Suffolk state land in carucates and acres, and geldUnits is all of it,
  the parts' included, at 120 acres to the carucate: Hull's statistics count both counties so.
  What a Norfolk or Suffolk village pays of each 20s levied on its hundred is taxPence.

Phillimore's "Freemen" (sokemen) and "free men" (liberi homines) are told apart by the space, as
in figures.py, so freemen means sokemen here exactly as it does for Great Domesday. Text Hull
marks as cancelled ({{…}}) is dropped before parsing, and so are the fief heading ([= … =]), the
marginalia (?M?) and the folio marks (<12b>). The words editors supplied are kept, because
"50[s]" is a value only with them.

No running text is written out. It is Phillimore's translation, revised by the Thorns, and not
ours to republish; Hull's collection says each item carries a Creative Commons licence.

How close this comes to Hull's own figures is measured, not assumed:
tests/check_little_domesday.py reconciles it against Open Domesday, which publishes Hull's
hand-coded statistics, and tests/check_little_domesday_hand.py against 30 entries read by hand.

    .cache/venv/bin/python scripts/little_domesday.py .cache
"""
import collections
import csv
import json
import os
import re
import sys

COUNTY_NAME = {'ESS': 'Essex', 'NFK': 'Norfolk', 'SUF': 'Suffolk'}

"""The text is cp1252 with CRLF, as Hull's exporter wrote it. Each entry opens on its own line, 'NFK 1,61'."""
HEADER = re.compile(r'^(ESS|NFK|SUF) ([0-9A-Z][0-9A-Za-z,\-]*)\s*$', re.M)


def entries_of(path):
    text = open(path, encoding='cp1252').read().replace('\r', '')
    heads = list(HEADER.finditer(text))
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        # the next county's banner ("SUFFOLK") is part of no entry
        body = re.split(r'\n\s*\x1a?\s*\n[A-Z ]{5,}\n', text[m.end():end])[0]
        yield m.group(1), m.group(2), body


def fief_of(body):
    m = re.search(r'\[=\s*(?:\?\[?\w+\]?\?)?\s*(.*?)=\]', body, re.S)
    return re.sub(r'\s+', ' ', m.group(1)).strip() if m else None


def strip_marks(body, keep_identifications=True):
    """
    The figures text. Cancelled text and headings go; insertions are unwrapped. An implied-meaning
    insertion (^[…]^) restates what the text leaves implicit, so it is kept for names and dropped
    for figures, where it would count a restated thing twice.
    """
    t = re.sub(r'\{\{.*?\}\}', ' ', body, flags=re.S)
    t = re.sub(r'\[=.*?=\]', ' ', t, flags=re.S)
    t = re.sub(r'\?\[?[^?\s]{1,4}\]?\?', ' ', t)
    t = re.sub(r'<\d+[a-d]?>', ' ', t)
    t = re.sub(r'<[^<>]*>', ' ', t)
    if keep_identifications:
        t = re.sub(r'\^\[(.*?)\]\^', r' \1 ', t, flags=re.S)
    else:
        for _ in range(3):  # implied insertions nest identifications inside them
            t = re.sub(r'\^\[(?:(?!\]\^).)*\]\^', ' ', t, flags=re.S)
    t = re.sub(r'\[\*\s*(.*?)\s*\*\]', r'\1', t, flags=re.S)
    t = t.replace('[', '').replace(']', '').replace('{', '').replace('}', '')
    t = re.sub(r'(?i)\b(?:a\s)?half-a-free-(man|woman)', r'1/2 free \1', t)
    return re.sub(r'\s+', ' ', t).strip()


WORDNUM = {'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7,
           'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12, 'none': 0, 'no': 0}
FRACTION = {'1/2': 0.5, '1/4': 0.25, '3/4': 0.75, '1/3': 1 / 3, '2/3': 2 / 3, '1/8': 0.125, '1/6': 1 / 6}


def number(text):
    text = text.strip().lower()
    if text in WORDNUM:
        return WORDNUM[text]
    if text in FRACTION:
        return FRACTION[text]
    parts = text.split()
    value = float(parts[0]) + (FRACTION[parts[1]] if len(parts) > 1 else 0)
    return int(value) if value == int(value) else value


"""
Each category the scanner counts, and the words it is written in. The first match wins, so a
longer phrase is listed before anything it contains. A context category only counts while its
keyword governs the clause: pigs after "woodland" measure the wood, not the herd, and acres
after "meadow" are meadow, where any other acres are land.
"""
CATEGORIES = [
    ('freeMen', r'free\s(?:men|man)'),
    ('freemen', r'freem[ae]n'),
    ('slaves', r'(?:female\s)?slaves?'),
    ('villagers', r'villagers?'),
    ('smallholders', r'smallholders?'),
    ('cottagers', r'cottagers?'),
    ('priests', r'priests?'),
    ('burgesses', r'burgess(?:es)?'),
    ('lordsTeams', r"ploughs?\s(?:now\s)?in\slordship|lordship\sploughs?"),
    ('mensTeams', r"men's\sploughs?|ploughs?\sbelonging\sto\sthe\smen|ploughs?\s(?:of|among)\sthe\smen"),
    ('teams', r'ploughs?'),
    ('oxen', r'oxen|ox'),
    ('mills', r'mills?'),
    ('fisheries', r'fisher(?:y|ies)'),
    ('saltHouses', r'salt[\s-]?houses?|salt[\s-]?pans?'),
    ('beehives', r'beehives?|hives?\sof\sbees'),
    ('cobs', r'cobs?'),
    ('horses', r'(?:wild\s|unbroken\s)?mares?|horses?|foals?|colts?'),
    ('cows', r'cows?'),  # Hull counts cows apart from cattle (animalia), and so does Open Domesday
    ('cattle', r'(?:head\sof\s)?cattle|bullocks?|beasts'),
    ('pigs', r'pigs?'),
    ('sheep', r'sheep'),
    ('goats', r'goats?'),
    ('acres', r'acres?'),
]
CAT_RE = '|'.join('(?P<c%d>%s)' % (i, p) for i, (_, p) in enumerate(CATEGORIES))
NUM = (r"\d+(?:\s(?:1/2|1/4|3/4|1/3|2/3|1/8|1/6))?|1/2|1/4|3/4|1/3|2/3|1/8|1/6|"
       r"a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|none")
MOMENT_RE = (r"(?P<always>always)|(?P<before>before\s1066|formerly|in\sthe\stime\sof\sKing\sEdward)|"
             r"(?P<then>then)|(?P<later>later(?:\son)?|afterwards|when\s(?:\w+\s){0,3}(?:acquired|received))|"
             r"(?P<now>now|at\spresent)")
TOKEN = re.compile(r'(?i)\b(?:' + MOMENT_RE + r')\b'
                   r'|(?P<num>(?<![\w/£])(?:' + NUM + r'))(?:\s(?:more|other|further|whole))?\s(?P<half>half\s)?(?P<cat>' + CAT_RE + r')\b'
                   r'|(?P<halves>(?<![\w/£])(?:' + NUM + r'))\shalves\b'
                   r'|(?P<andhalf>and\sa\shalf)\b(?!\s(?:hides?|virgates?|carucates?|acres?|ploughs?|mills?|leagues?))'
                   r'|(?P<bare>(?<![\w/£])(?:\d+(?:\s(?:1/2|1/4|3/4))?|1/2|none))(?![\w/]|\s?[sd]\b|\s(?:acres?|carucates?|hides?|virgates?|leagues?|perches|feet|furlongs?|wethers|lambs|pence|shillings?|arpents?)\b)'
                   r'|(?P<ctx>woodland|meadow|pasture|value|valued?|worth|pays?|paid|renders?)\b'
                   r'|(?<!\bis\s)(?<!\bare\s)(?<!\bwas\s)(?P<held>held)\b'
                   r'|(?P<possible>possible|could\sbe\srestored|be\srestored)\b'
                   r'|(?P<less>less\s(?P<lessn>\d+)\b)(?!\s(?:acres?|hides?|virgates?|carucates?|bovates?))'
                   r'|(?P<stop>[.;:])')

MOMENTS = {'always': ('1066', 'Later', '1086'), 'before': ('1066',), 'then': ('1066',),
           'later': ('Later',), 'now': ('1086',)}


def scan(text):
    """
    Figures by category and date: {('villagers', '1086'): 60, ('villagers', '1066'): 51, ...}.
    A date persists across a list ("Then 3 cobs, 40 cattle") and across "and" ("then and later")
    until another date replaces it or the clause ends. A semicolon ends the clause: Phillimore
    restates the date after one ("then 19 smallholders, now 30; then 20 slaves"), so a figure after
    it with none is 1086's, which is the reading that claims least. A bare number ("now 60") is
    counted only straight after a date, so the "58 acres" of a later sentence is never a villager.
    """
    out, counted = collections.defaultdict(float), collections.Counter()
    dates, joined, last_cat, context, last_key, last_amount = None, False, None, None, None, 0
    last_dates, last_clause, clause, redated, last_end = (), -1, 0, None, 0
    before_only, assigned, before_dated = [], set(), False
    for m in TOKEN.finditer(text):
        group = next((g for g in ('always', 'before', 'then', 'later', 'now') if m.group(g)), None)
        if group == 'before' and not dates and last_key and last_clause == clause and last_key[1] == '1086' \
                and not joined and last_key[0] in POPULATION and m.start() - last_end <= 70:
            # "12 Freemen before 1066; now 10": the date follows the figure it dates
            out[last_key] -= last_amount
            counted[last_key] -= 1
            if not counted[last_key]:
                del out[last_key]
            out[(last_key[0], '1066')] += last_amount
            counted[(last_key[0], '1066')] += 1
            redated = [last_key[0], last_amount, False]
            last_key, last_dates = (last_key[0], '1066'), ('1066',)
            continue
        if group:
            before_dated = group == 'before'
            new = MOMENTS[group]
            # "then and later", "later and now": a date straight after a date joins it
            if joined and dates:
                dates = tuple(dict.fromkeys(dates + new))
            else:
                dates = new
            joined = True
            continue
        if m.group('stop'):
            joined, context, dates = False, None, None
            clause += 1
            if m.group('stop') == '.':
                """
                "11 free men of Alsi's before 1066, at 30 acres" dates their lord, not their number:
                with no "now" figure after it, the men are 1086's too. "12 Freemen before 1066;
                now 10" has one, and 1086 is 10.
                """
                for cat_, amount_, superseded in [redated] if redated else []:
                    if not superseded:
                        out[(cat_, '1086')] += amount_
                        counted[(cat_, '1086')] += 1
                for cat_, amount_ in before_only:
                    if (cat_, '1086') not in assigned:
                        out[(cat_, '1086')] += amount_
                        counted[(cat_, '1086')] += 1
                last_cat, redated, before_only, assigned = None, None, [], set()
            continue
        if m.group('ctx'):
            word = m.group('ctx').lower()
            context = 'value' if word.startswith(('valu', 'worth')) else word
            joined = False
            continue
        if m.group('possible'):
            # "2 ploughs possible" is capacity, not teams: undo the count it follows
            if last_key and last_key[0] in ('teams', 'lordsTeams', 'mensTeams'):
                out[last_key] -= last_amount
            continue
        if m.group('held'):
            """
            "Godman, a free man, held 20 acres", "1 free woman, Wulffled, held": one person named as
            the holder (not "1 free man is held", who is held and so is population) before 1066 is
            not a household of the holding, and Open Domesday does not count one; nor are men a
            relative clause names as holders ("which 3 free men held"). A body of free men holding
            is the holding's population, and stays; so does a lone Freeman (a sokeman), whom Hull
            counts ("1 Freeman of Earl Gyrth's held WRAMPLINGHAM").
            """
            relative = last_key and re.search(r'\bwhich\s(?:\S+\s){0,2}$', text[max(0, last_start - 20):last_start])
            if last_key and (last_amount == 1 or relative) and last_key[0] in ('freeMen', 'freemen') \
                    and (last_key[0] == 'freeMen' or relative) and last_clause == clause:
                for d in last_dates:
                    out[(last_key[0], d)] -= last_amount
                    counted[(last_key[0], d)] -= 1
                    if not counted[(last_key[0], d)]:
                        del out[(last_key[0], d)]
                last_key = None
            continue
        if m.group('andhalf'):
            # "9 free men and a half", "1 Freeman and a half": a half share more
            if last_key and last_key[0] in POPULATION and last_clause == clause:
                for d in last_dates:
                    out[(last_key[0], d)] += 0.5
            continue
        if m.group('halves'):
            # "13 whole Freemen and 3 halves": a half share of a man is half a household
            if last_cat in POPULATION:
                for d in (dates or ('1086',)):
                    out[(last_cat, d)] += number(m.group('halves')) / 2
            continue
        if m.group('less'):
            # "200 sheep less 7" is 193 sheep; a "less" in another clause is about something else
            if last_key and last_clause == clause:
                out[last_key] -= int(m.group('lessn'))
            continue
        if m.group('num'):
            cat = next(CATEGORIES[i][0] for i in range(len(CATEGORIES)) if m.group('c%d' % i))
            amount = number(m.group('num')) * (0.5 if m.group('half') else 1)
        elif m.group('bare') and last_cat and joined:
            cat, amount = last_cat, number(m.group('bare'))
        else:
            continue
        joined = False
        if cat in POPULATION and re.search(r'(?i)\bof\s$', text[max(0, m.start() - 4):m.start()]):
            # "the jurisdiction of three free men": a reference to men counted elsewhere
            continue
        if cat == 'pigs' and context == 'woodland':
            cat = 'woodlandPigs'
        elif cat == 'sheep' and context == 'pasture':
            cat = 'pastureSheep'  # Essex measures pasture by the sheep it feeds; they are not a flock
        elif cat == 'acres':
            cat = 'meadowAcres' if context == 'meadow' or re.match(r'\s?(?:of\s)?meadow', text[m.end():m.end() + 12]) else None
        if cat is None:
            last_cat = None
            continue
        last_cat = cat
        for d in (dates or ('1086',)):
            out[(cat, d)] += amount
            counted[(cat, d)] += 1
            assigned.add((cat, d))
        if redated and redated[0] == cat and '1086' in (dates or ('1086',)):
            redated[2] = True
        """
        "before 1066, 16 free men of Alsi's, 1 carucate": the date names whose men they were. With
        no figure for 1086 in the sentence, they are 1086's population too.
        """
        if before_dated and dates == ('1066',) and cat in POPULATION:
            before_only.append((cat, amount))
        last_key, last_amount, last_start, last_end = (cat, (dates or ('1086',))[-1]), amount, m.start(), m.end()
        last_dates, last_clause = dates or ('1086',), clause
    return out


VAL_TOKEN = re.compile(r'(?i)\b(?:' + MOMENT_RE + r')\b|(?P<money>(?<![\w£])(?=[£\d])(?:£\s?\d+(?:\s1/2)?(?:\s\d+\s?s\b)?(?:\s\d+\s?d\b)?|\d+(?:\s1/2)?\s?s\b(?:\s\d+\s?d\b)?|\d+(?:\s1/2)?\s?d\b|1/2\s?d\b))')


def pence(text):
    total = 0
    m = re.match(r'£\s?(\d+(?:\s1/2)?)', text)
    if m:
        total += number(m.group(1)) * 240
        text = text[m.end():]
    for n, unit in re.findall(r'(\d+(?:\s1/2)?|1/2)\s?([sd])\b', text):
        total += number(n) * (12 if unit == 's' else 1)
    return total


"""
A clause that says its value is counted elsewhere ("included in the same valuation", "valued
above", "valued in Sporle") adds nothing here. Sentences about what a holding pays in dues,
customs or rent are not its value either: only those that say value, valued or worth are read.
"""
ELSEWHERE = re.compile(r'(?i)included|same\svaluation|part\sof\sthe\sabove|valued\s(?:above|below|in|with|within|under)|in\sthe\svalu')

"""
What follows these in a value sentence is not the value: what the sheriff receives over it, what
it pays in gifts or as a premium ("and 20s as a premium"), what a reeve farmed it for, what it
could render. "Value then £36; now £60, but the sheriff receives £80 from it" values the manor at
£60. Blanched, at face value and by weight say how an amount was assayed, and the amount runs on
through them ("£32 blanched 13s 4d"). What it pays is its value where a date says so ("Value of the
whole before 1066 £13; now it pays £30"), and a sentence that follows a valuation to say what the
holding's men pay ("The free men pay 40s") adds to 1086's, as Hull adds it; one about tax does not.
"""
BEYOND = re.compile(r'(?i)\b(?:but|however|yet|nevertheless|receives?|received|gives?|gave|gifts?|premium|revenue|'
                    r'farm|delivered|could)\b')
"""
Three kinds of sentence change what has been summed so far rather than adding to it. One that
revises a valuation ("The Bishop's men are valued at £63 5s 4d. But now, as the other men of the
Hundred testify, value £100") or states the whole ("Value of the whole then £10; now £13 8s")
replaces the dates it names. One that says what a lord had or was paid from the holding before
1066 without saying value ("From the whole of this and from the manor, Earl Harold had £36 before
1066") is 1066's value. And what the pasture, a mill, a fishery or a house is worth or pays is the
render of that thing, not the holding's value ("Pasture is there which is worth 18s", "12 houses in
London which pay 20s").
"""
REVISES = re.compile(r"(?i)^(?:but|however|now\showever)\b")
WHOLE = re.compile(r"(?i)\b(?:of\sthe\swhole|the\swhole\s(?:manor\s)?(?:is\s|was\s)?(?:valued|value)|in\stotal|"
                   r"altogether|all\sthis\s(?:is\s|was\s)?(?:valued|value)|value\sof\sall)\b")
HAD_BEFORE = re.compile(r"(?i)\b(?:had|paid|rendered|received)\s(£\s?\d+(?:\s\d+s)?(?:\s\d+d)?|\d+\s?s(?:\s\d+d)?)\s"
                        r"(?:from\sit\s)?before\s1066\b")
THING_WORTH = re.compile(r"(?i)\b(?:pasture|mills?|fisher(?:y|ies)|houses?|marsh|wood(?:land)?|salt-?houses?|church)\b"
                         r"[^.;]{0,30}\b(?:worth|pays?|valued?)\b")
PREMIUM = re.compile(r"(?i)(?:,?\s*and\s)?(?:£\s?\d+|\d+\s?[sd])(?:\s\d+\s?[sd])*\s(?:as\s(?:a\s)?|in\s)(?:premium|gifts?)\b[^;.]*")
VAL_SCAN = re.compile(VAL_TOKEN.pattern[len('(?i)'):] + r'|\b(?P<was>was|were)\b|\b(?P<is>is|are)\b'
                      r'|\b(?P<same>the\ssame|as\smuch)\b(?!\s(?:man|men|manor|village|land|hundred|valuation))', re.I)


def cut_beyond(clause):
    """A clause up to what is not its value; "now however it pays only £15" is itself the revision."""
    lead = re.match(r'(?i)\s*(?:now,?\s(?:however|but),?|but\snow,?|however,?\snow,?)\s', clause)
    start = lead.end() if lead else 0
    m = BEYOND.search(clause, start)
    return clause[:m.start()] if m else clause


def undated_first(body):
    """
    "Value £16; later £28; now the same": an amount stated before any date, in a sentence that
    goes on to later or now, is 1066's — the sentence runs from then to now. Read alone ("Value
    20s") it is 1086's.
    """
    first = VAL_TOKEN.search(body)
    if first and first.group('money') and re.search(r'(?i)\b(?:later|now|afterwards|when\s(?:\w+\s){0,3}acquired)\b',
                                                    body[first.end():]) and \
            not re.search(r'(?i)\b(?:then|before\s1066|always|was|now|is)\b', body[:first.start()]):
        return body[:first.start()] + 'then ' + body[first.start():]
    return body


def valuation_of(body):
    """One value sentence's amounts by date, read as valuation() reads it."""
    got = {}
    body = undated_first(body)
    for clause in body.split(';'):
        pending, joined, last_amount = [], False, None
        for m in VAL_SCAN.finditer(clause):
            group = next((g for g in ('always', 'before', 'then', 'later', 'now') if m.group(g)), None)
            if m.group('same'):
                for d in dict.fromkeys(pending or ['1086']):
                    if last_amount is not None:
                        got[d] = got.get(d, 0) + last_amount
                pending = []
                continue
            if not group and (m.group('was') or m.group('is')):
                if not pending:
                    pending = ['1066'] if m.group('was') else ['1086']
                continue
            if group:
                pending = pending + list(MOMENTS[group]) if joined else list(MOMENTS[group])
                joined = True
                continue
            joined = False
            if m.group('money'):
                last_amount = pence(m.group('money'))
                for d in dict.fromkeys(pending or ['1086']):
                    got[d] = got.get(d, 0) + last_amount
    return got


def valuation(text):
    """
    Value by date, in pence, summed over the entry's value sentences: Little Domesday values a
    manor's parts one by one ("Also the value then of the 3 outliers £12, the Freemen's land 45s"),
    and Hull's figure for the holding is their sum. A date governs every amount after it until a
    semicolon or another date. A tense stands in for a date only when none is named: "its value
    was £15 ... now £40" gives 1066 £15.
    """
    out, after_value = {}, False
    first = os.environ.get('LD_VALUES') == 'first'
    for sentence in re.split(r'(?<=\.)\s', text):
        if THING_WORTH.search(sentence) and not re.search(r'(?i)^\W*(?:also\s)?(?:the\s)?value', sentence):
            continue
        had = HAD_BEFORE.search(sentence)
        if had and not re.search(r'(?i)\b(?:value|valued|worth)\b', sentence):
            amount = pence(had.group(1))
            out['1066'] = amount if WHOLE.search(sentence) or 'whole' in sentence.lower() else out.get('1066', 0) + amount
            continue
        replacing = bool(REVISES.search(sentence) or WHOLE.search(sentence))
        head = re.search(r'(?i)\b(?:value|valued|worth)\b', sentence)
        follow = re.match(r"(?i)(?:the|these|those|this|they)\b[^.]{0,40}?\bpays?\s(£\s?\d+(?:\s\d+s)?|\d+\s?s(?:\s\d+d)?|\d+\s?d)\b[^.]*\.?$", sentence)
        if not head and after_value and follow and not re.search(r'(?i)\b(?:tax|geld)\b', sentence):
            out['1086'] = out.get('1086', 0) + pence(follow.group(1))
            continue
        after_value = bool(head)
        if not head or ELSEWHERE.search(sentence[head.start():head.start() + 60]):
            continue
        body = PREMIUM.sub('', sentence[head.start():])
        # a farm, a premium or a "but" ends its own clause, not the sentence: "it was delivered for
        # £20 ...; now however it pays only £15" still values 1086 at £15
        body = ';'.join(cut_beyond(c) for c in body.split(';'))
        pending, joined, last_amount, after_money = [], False, None, False
        """
        LD_VALUES=first is the rule that takes each date's first valuation and adds nothing after
        it; it exists to be measured against Hull's figures (tests/check_little_domesday.py), which
        add a holding's appended parts.
        """
        if (replacing or first) and head:
            mine = valuation_of(body)
            for d, v in mine.items():
                if replacing or d not in out:
                    out[d] = v
            continue
        body = undated_first(body)
        for clause in body.split(';'):
            pending, joined = [], False
            for m in VAL_SCAN.finditer(clause):
                group = next((g for g in ('always', 'before', 'then', 'later', 'now') if m.group(g)), None)
                if m.group('same'):
                    # "Value then 20s; now the same": the amount last stated, for the date now named
                    for d in dict.fromkeys(pending or ['1086']):
                        if last_amount is not None:
                            out[d] = out.get(d, 0) + last_amount
                    pending = []
                    continue
                if not group and (m.group('was') or m.group('is')):
                    if not pending:
                        pending = ['1066'] if m.group('was') else ['1086']
                    continue
                if group == 'always' and after_money and \
                        re.search(r'\band\s$', clause[max(0, m.start() - 5):m.start()]):
                    # "Value then 16d and always": the amount just stated holds for the other dates too
                    for d in ('Later', '1086'):
                        out[d] = out.get(d, 0) + last_amount
                    continue
                after_money = False
                if group:
                    pending = pending + list(MOMENTS[group]) if joined else list(MOMENTS[group])
                    joined = True
                    continue
                joined = False
                if m.group('money'):
                    after_money = True
                    last_amount = pence(m.group('money'))
                    for d in dict.fromkeys(pending or ['1086']):
                        out[d] = out.get(d, 0) + last_amount
    return {'value' + d: int(v) if v == int(v) else v for d, v in out.items()}


GELD = re.compile(r'(?i)\b(' + NUM + r')\s(hides?|carucates?|virgates?|acres?)\b')
GELD_UNITS = {'hide': 1, 'carucate': 1, 'virgate': 0.25, 'acre': 1 / 120}


def assessment(text, county):
    """
    The land the entry states, in geld units: hides in Essex, carucates in Norfolk and Suffolk,
    acres at 120 to the unit, summed over the holding and its parts — the free men's acres, the
    church's — as Hull's statistics, and Open Domesday after them, count it. Meadow, woodland and
    pasture are measured in acres too and are not the assessment, nor is the "now" of a reduced
    assessment ("for 5 hides; now for 3").
    """
    units, whole = [], text
    if county == 'ESS':
        """
        Essex is hidated, and its parts' land is counted in the manor's hides: Hull notes "Freemen's
        holding and subholdings assumed to be included in manorial total". Its geld is the first
        sentence's that states land ("He also holds LAWFORD ... Later Engelric held it as a manor,
        for 2 hides").
        """
        text = next((t for t in re.split(r'(?<=\.)\s', text) if GELD.search(t)), '')
    for sentence in re.split(r'(?<=\.)\s', text):
        # "she had 100 acres. Of these, Robert Malet holds 30": a part of land already counted
        if re.match(r'(?i)of\s(?:these|this|them|which)\b', sentence):
            continue
        units += sentence_units(sentence)
    out = {}
    if units:
        out['geldUnits'] = round(sum(n * GELD_UNITS[u] for n, u in units), 4)
    """
    What the village pays of each 20s the hundred is levied, written three ways: "of a 20s tax it
    pays 8d", "tax of 15d", "7 1/2d in tax".
    """
    m = (re.search(r'(?i)of\sa\s20s\stax,?\s(?:it\s|he\s|they\s)?pays?\s(\d+(?:\s1/2|\s1/4|\s3/4)?\s?[sd](?:\s\d+d)?)', whole)
         or re.search(r'(?i)\btax\sof\s(\d+(?:\s1/2|\s1/4|\s3/4)?\s?[sd](?:\s\d+d)?)', whole)
         or re.search(r'(?i)(\d+(?:\s1/2|\s1/4|\s3/4)?\s?[sd](?:\s\d+d)?)\sin\s(?:tax|geld)\b', whole))
    if m:
        out['taxPence'] = pence(m.group(1).strip())
    return out


def sentence_units(sentence):
    units = []
    for clause in re.split(r'[;.]', sentence):
        clause = re.split(r'\bnow\b', clause)[0]
        for m in GELD.finditer(clause):
            before = clause[max(0, m.start() - 14):m.start()].lower()
            after = clause[m.end():m.end() + 12].lower()
            if re.search(r'meadow|woodland|wood|pasture|marsh', before + ' ' + after):
                continue
            sign = -1 if re.search(r'less\s$', before) else 1  # "for 5 hides less 20 acres"
            units.append((sign * number(m.group(1)), m.group(2).lower().rstrip('s')))
    return units


FLAGS = [('hasChurch', r'\bchurch(?:es)?\b'), ('hasCastle', r'\bcastle\b'), ('hasMarket', r'\bmarket\b'),
         ('isWaste', r'\bwaste\b')]

"""The realm's figures, and the Little Domesday ones beside them; the population makes households."""
POPULATION = ['villagers', 'smallholders', 'slaves', 'cottagers', 'freemen', 'freeMen', 'priests', 'burgesses']
COUNTED = POPULATION + ['lordsTeams', 'mensTeams', 'oxen', 'pastureSheep', 'mills', 'fisheries', 'saltHouses',
                        'beehives', 'cobs', 'horses', 'cows', 'cattle', 'pigs', 'sheep', 'goats', 'woodlandPigs',
                        'meadowAcres']


def tidy(v):
    v = round(v, 4)
    return int(v) if v == int(v) else v


"""
Ploughs the text does not assign are the men's — "Always 3 ploughs" is how free men's land is
written — except in two cases Hull reads as the lord's: where the next sentence goes on to the
men's ploughs ("Then and later 2 ploughs, now 1. Then 1 men's plough"), and where the part of the
entry they belong to has no men to work them ("2 girls held FOUCHERS for 80 acres ... Always 1
plough"). A part runs up to its value sentence: Little Domesday describes a holding and then its
appendages, each valued in turn.
"""
LORDS_BEFORE_MENS = re.compile(r"(?i)\b((?:" + NUM + r")\s)(ploughs?)\b(?!\s(?:in\slordship|now\sin\slordship|possible))"
                               r"(?=[^.;]*[.;]\s(?:[^.;]{0,30}?)\b(?:" + NUM + r")\smen's\sploughs?)")


def parts_of(text):
    out, start = [], 0
    for m in re.finditer(r'(?i)\b(?:value|valued|worth)\b[^.]*\.', text):
        out.append(text[start:m.end()])
        start = m.end()
    out.append(text[start:])
    return [p for p in out if p.strip()]


def scan_parts(text):
    found = collections.defaultdict(float)
    for part in parts_of(LORDS_BEFORE_MENS.sub(r'\1\2 in lordship', text)):
        got = scan(part)
        nobody = not any(cat in POPULATION for cat, _ in got)
        for (cat, d), v in got.items():
            if cat == 'teams':
                cat = 'lordsTeams' if nobody else 'mensTeams'
            found[(cat, d)] += v
    return found


def figures(body, county):
    text = strip_marks(body, keep_identifications=False)
    found = scan_parts(text)
    out = {}
    for cat in COUNTED:
        for date, suffix in (('1086', ''), ('1066', '1066'), ('Later', 'Later')):
            if (cat, date) in found and found[(cat, date)] >= 0:
                out[cat + suffix] = tidy(found[(cat, date)])
    """
    A total for 1066 or later is written only when every part 1086 states is stated for that date
    too. Little Domesday often dates the villagers and not the smallholders, and a sum of whatever
    happens to be dated would be a smaller number that looks like a fall.
    """
    for total, parts in (('ploughTeams', ['lordsTeams', 'mensTeams']), ('households', POPULATION)):
        stated = [k for k in parts if k in out]
        if stated:
            out[total] = tidy(sum(out[k] for k in stated))
        for suffix in ('1066', 'Later'):
            if stated and all(k + suffix in out for k in stated):
                out[total + suffix] = tidy(sum(out[k + suffix] for k in stated))
    out.update(valuation(text))
    out.update(assessment(text, county))
    for key, rx in FLAGS:
        if re.search(rx, text, re.I):
            out[key] = True
    return out


def parse_refs(field):
    """
    An Explorer reference list, '8,22;88. 15,5. 22,15-16;20' (chapter 8 sections 22 and 88, …), as
    a set of refs. A bare chapter ('7.') is the whole chapter, which is how Names marks the
    chapter's tenant-in-chief; it comes back as 'ch:7'. Braces and notes ('and n') are Hull's
    own glosses on a reference and are read through.
    """
    out = set()
    for part in re.split(r'\.\s*', re.sub(r'[{}()]|\band n\b', '', field or '')):
        part = part.strip()
        if not part:
            continue
        if ',' not in part:
            if re.fullmatch(r'\d+', part):
                out.add('ch:' + part)
            else:
                out.update(p.strip() for p in part.split(';') if p.strip())
            continue
        chapter, sections = part.split(',', 1)
        for s in sections.split(';'):
            s = s.strip()
            m = re.fullmatch(r'(\d+)([a-z]?)-(\d+)([a-z]?)', s)
            if m:
                out.update(f'{chapter},{n}' for n in range(int(m.group(1)), int(m.group(3)) + 1))
            elif s:
                out.add(f'{chapter},{s}')
    return out


def rows(cache, name):
    with open(os.path.join(cache, 'csv', name + '.csv'), encoding='utf-8') as f:
        return list(csv.DictReader(f))


def canonical(name):
    return re.sub(r'\s+', ' ', re.sub(r'[()\[\]{}]', '', name)).strip()


def name_forms(name):
    """
    The forms a Names record can appear in, longest first: 'Aitard (of Vaux)/Roger Bigot's man'
    is written 'Aitard of Vaux' or just 'Aitard'. What follows the slash describes him.
    """
    head = name.split('/')[0]
    forms = [canonical(head), canonical(re.sub(r'\([^)]*\)|\{[^}]*\}', '', head))]
    return [f for f in dict.fromkeys(forms) if len(f) > 1]


"""
The roles a mention of a name gives it, read from the mention's own clause and never from a verb
that belongs to someone else:

    Aethelstan held SAXTHORPE under Earl Harold before 1066, now Ribald brother of Count Alan holds

Aethelstan is the subject of "held": the lord in 1066. Harold follows "under": he is Aethelstan's
lord by commendation, the overlord in 1066, and the "holds" later in the sentence is Ribald's, not
his. Ribald is the subject of "holds": 1086's holder. Count Alan follows "brother of": he describes
Ribald and holds nothing here. So a name after under, commended to, patronage of or man of is the
1066 overlord; a name after any other "of", or after from or to, is not a subject at all; and a
name is a subject only when its verb follows it with nothing between but an apposition ("Godman,
a free man, held", "Ribald brother of Count Alan holds"). Having or holding the jurisdiction or
patronage is the jurisdiction, not the land.
"""
"""A title stands between a preposition and the name it governs: "under Earl Harold", "of Count Alan"."""
TITLES = r"(?:Earl|Count|Countess|Bishop|Archbishop|Abbot|Abbess|King|Queen|Ealdorman|Sheriff)"
OVERLORD_BEFORE = re.compile(r"(?i)\b(?:under|commended\sto|in\sthe\scommendation\sof|patronage(?:\sonly)?\sof|"
                             r"(?:a\s)?(?:free\s)?(?:man|men|woman|thane|thanes)\sof|in\sthe\ssoke\sof)\s(?:the\s)?" + r"(?:TITLE\s)?$".replace('TITLE', TITLES))
HOLDS_UNDER = re.compile(r"(?i)\bholds?\s(?:it|this|them|these|that|this\sland|the\swhole|also|now|\s)*under\s(?:the\s)?"
                         + r"(?:TITLE\s)?$".replace('TITLE', TITLES))
OBJECT_BEFORE = re.compile(r"(?i)\b(?:of|from|to|by|with|for|against|and)\s(?:the\s)?" + r"(?:TITLE\s)?$".replace('TITLE', TITLES))
SUBJECT_VERB = re.compile(r"(?i)^\??(?:\s?,[^,.;]{0,60},|\s(?:brother|son|nephew|wife|daughter|father|mother|man)\sof\s"
                          r"(?:the\s)?(?:[A-Z][\w']*\s?){1,4}|\s(?:[A-Z][\w']*\s?){0,3}|\s\(?[a-z][\w']*\)?)?"
                          r"\s?(?:also\s|now\s|still\s|always\s|himself\s|similarly\s|likewise\s)?"
                          r"(?P<verb>held|had|holds|has|have|hold)\b(?P<rest>[^.;]{0,30})")
JURISDICTION = re.compile(r"(?i)^\s(?:the\s|full\s|all\s|also\s)*(?:jurisdiction|patronage|soke|commendation|"
                          r"customary\sdues?|sake\sand\ssoke)")


def fold_ae(s):
    return s.replace('Ae', 'A').replace('ae', 'a').replace('Æ', 'A').replace('æ', 'a')


def roles_of(text, forms, is_tic):
    """
    Every role the name's mentions give it, in the order first seen; empty when none is stated.
    Hull's index and the Thorns' text spell the same name two ways (Athelstan, Aethelstan), so both
    are compared with ae read as a.
    """
    out = []
    text = fold_ae(text)
    for form in map(fold_ae, forms):
        for m in re.finditer(r'\b' + re.escape(form) + r'\b', text):
            before = text[max(0, m.start() - 40):m.start()]
            role = None
            if OVERLORD_BEFORE.search(before):
                """
                "holds it under Richard" names 1086's lord, between the tenant-in-chief and the man
                who holds. Every other "under" is the commendation of 1066 — "Aethelstan held
                SAXTHORPE under Earl Harold", and also "Hugh holds 1 free man, Alfric, under the
                patronage of Edric", where the patronage describes the free man before 1066.
                """
                present = HOLDS_UNDER.search(before)
                role = ('TENANT_IN_CHIEF' if is_tic else 'TENANT_1086') if present else 'OVERLORD_1066'
            elif not OBJECT_BEFORE.search(before):
                v = SUBJECT_VERB.match(text[m.end():m.end() + 110])
                if v:
                    past = v.group('verb').lower() in ('held', 'had')
                    if JURISDICTION.match(v.group('rest')):
                        role = 'JURISDICTION_1066' if past else 'JURISDICTION_1086'
                    elif past:
                        role = 'LORD_1066'
                    else:
                        role = 'TENANT_IN_CHIEF' if is_tic else 'SUBTENANT_1086'
            if role and role not in out:
                out.append(role)
        if out:
            break
    return out


def main(cache):
    source = os.path.join(cache, 'hull_translation.txt')
    if not os.path.exists(source):
        source = os.path.join(cache, 'hull2025', 'translation.txt')
    places = [p for p in rows(cache, 'Places') if p['County'] in COUNTY_NAME]
    names = [n for n in rows(cache, 'Names') if n['County'] in COUNTY_NAME]
    hundreds = {(p['County'], p['Hundred'].upper()) for p in places if p['Hundred']}

    places_at = collections.defaultdict(list)
    for p in places:
        for ref in parse_refs(p['Phillimore']):
            places_at[(p['County'], ref)].append(p)
    people_at, tic_of = collections.defaultdict(list), collections.defaultdict(list)
    for n in names:
        """
        The Phillimore memo is cut at ten characters in the Explorer's record, and NameRef, which
        restores it for Great Domesday, has nothing here. OldRefs is a full-width field; its
        references and the memo's surviving head are read together.
        """
        refs = parse_refs(n['OldRefs']) | parse_refs(re.sub(r'[\d,;.\s-]*$', '', n['Phillimore'])
                                                     if len(n['Phillimore']) >= 10 else n['Phillimore'])
        for ref in refs:
            if ref.startswith('ch:'):
                tic_of[(n['County'], ref[3:])].append(n)
            else:
                people_at[(n['County'], ref)].append(n)

    entries, new_places = [], collections.defaultdict(set)
    hundred = {}
    for county, ref, body in entries_of(source):
        named = strip_marks(body)
        """
        The hundred heads the run of entries it governs ("Hundred of STOWMARKET"), and stays until
        the next; the text names it once.
        """
        m = re.search(r"(?:Half-|Two\s|1\s1/2\s)?Hundreds?\sof\s([A-Z][A-Z' \-]+?)(?=\s[A-Z][a-z]|\s[a-z]|$)", named)
        if m:
            hundred[county] = m.group(1).title()
        chapter = ref.split(',')[0]
        data = {'entryId': f'{county} {ref}', 'ref': f'{COUNTY_NAME[county]} {ref}', 'phillimore': ref,
                'county': county, 'countyName': COUNTY_NAME[county], 'kind': 'manor', 'edition': 'Little Domesday'}
        if ref.startswith('B'):
            data['kind'] = 'urban'
        fief = fief_of(body)
        if fief:
            data['fief'] = fief

        caps = [(c.start(), re.sub(r"(?:\s(?:and|St)|[-'])+$", '', canonical(c.group(0)))) for c in
                re.finditer(r"\b[A-Z][A-Z'\-]{2,}(?:\s(?:[A-Z][A-Z'\-]{1,}|and|St))*\b", named)]
        candidates = places_at.get((county, ref), [])
        placed, seen = [], set()
        for at, word in caps:
            key = word.upper()
            if (county, key) in hundreds and re.search(r'Hundred', named[max(0, at - 20):at + len(word) + 12]):
                continue
            hit = next((p for p in candidates if canonical(p['Vill']).upper() == key
                        or re.sub(r'\[.*?\]\s*', '', p['Vill']).upper().strip() == key), None)
            if hit and hit['PlacesIdx'] not in seen:
                seen.add(hit['PlacesIdx'])
                placed.append(hit)
            elif not hit and key not in {COUNTY_NAME[county].upper(), 'HUNDRED', 'II', 'III'} \
                    and not HEADING.search(key):
                new_places[(county, word.title())].add(ref)
        relations = []
        for i, p in enumerate(placed):
            relations.append({'predicate': 'DESCRIBES' if i == 0 else 'INCLUDES', 'placeId': p['PlacesIdx'],
                              'name': p['Vill'], 'source': 'text'})
        for p in candidates:
            if p['PlacesIdx'] not in seen:
                seen.add(p['PlacesIdx'])
                relations.append({'predicate': 'INCLUDES', 'placeId': p['PlacesIdx'], 'name': p['Vill'],
                                  'source': 'index'})
        if placed:
            data['places'] = ', '.join(dict.fromkeys(p['Vill'] for p in placed))
            data['name'] = f"{data['places']} ({data['ref']})"
            data['holding'] = holding_of(named)
        """
        The hundred is the subject place's, from the gazetteer; the running heading is the fallback,
        because a run of entries can cross into a place the heading does not cover.
        """
        if placed and placed[0]['Hundred']:
            data['hundred'] = placed[0]['Hundred']
        elif county in hundred:
            data['hundred'] = hundred[county]
        else:
            data['name'] = data['ref']

        data.update(figures(body, county))
        if data['kind'] == 'manor' and data.get('burgesses', 0) > data.get('villagers', 0) + data.get('smallholders', 0):
            data['kind'] = 'urban'

        tics = {n['NamesIdx'] for n in tic_of.get((county, chapter), [])}
        people, linked = [], set()
        for n in tic_of.get((county, chapter), []):
            people.append({'predicate': 'TENANT_IN_CHIEF', 'personId': n['NamesIdx'], 'name': n['Name'],
                           'roleSource': 'index'})
            linked.add(n['NamesIdx'])
        for n in people_at.get((county, ref), []):
            if n['NamesIdx'] in linked:
                continue
            found = roles_of(named, name_forms(n['Name']), n['NamesIdx'] in tics)
            for predicate in found or ['NAMES']:
                people.append({'predicate': predicate, 'personId': n['NamesIdx'], 'name': n['Name'],
                               'roleSource': 'text' if found else 'index'})
            linked.add(n['NamesIdx'])
        data['placeRefs'] = relations
        data['people'] = people
        entries.append(data)

    known = {(p['County'], canonical(p['Vill']).upper()) for p in places}
    known |= {(p['County'], re.sub(r'\[.*?\]\s*', '', p['Vill']).upper().strip()) for p in places}
    unplaced = [{'county': c, 'name': n, 'refs': sorted(r)} for (c, n), r in sorted(new_places.items())
                if (c, n.upper()) not in known and (c, n.upper()) not in hundreds]

    counts = collections.Counter(e['county'] for e in entries)
    out = {
        'source': {
            'text': 'Domesday text translation, University of Hull, '
                    'https://digitalcollections.hull.ac.uk/concern/datasets/h989r385x (file /downloads/h989r387g)',
            'licence': 'CC BY-NC-SA 2.0 UK',
            'gazetteer': 'Domesday Explorer 1.1 Places and Names (J.J.N. Palmer and the University of Hull)',
            'method': 'figures parsed from the translation by scripts/little_domesday.py; no running text written',
        },
        'counts': dict(counts),
        'entries': entries,
        'unmatchedPlaceNames': unplaced,
    }
    path = os.path.join(cache, 'little_domesday.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f'{len(entries)} Little Domesday entries ({dict(counts)}) -> {path}')
    print(f"  with a subject place {sum(1 for e in entries if 'places' in e)}, "
          f"with a tenant-in-chief {sum(1 for e in entries if any(p['predicate'] == 'TENANT_IN_CHIEF' for p in e['people']))}, "
          f"upper-case names matching no Explorer place {len(unplaced)}")


"""Upper case also sets the chapter headings the text runs into ("LAND OF WULFEVA WIFE OF FIN")."""
HEADING = re.compile(r"\b(?:LANDS?|ANNEXATIONS?|HOLDING|KING|KING'S|CHARGE|LIST|OF\sTHE|FIEF)\b")


def holding_of(text):
    """What the opening statement says the holding is; nothing when it says nothing."""
    head = re.split(r'(?<=\.)\s', text, maxsplit=1)[0].lower()
    if re.search(r'\bas\s(?:a|1|one|\d+)\smanors?\b|\bmanor\b', head):
        return 'manor'
    if re.search(r'outliers?|berewicks?', head):
        return 'outlier'
    if re.search(r'jurisdiction|soke', head):
        return 'jurisdiction'
    if re.search(r'free\smen|freem[ae]n', head):
        return 'land'
    return 'unclassified'


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.cache'))
