"""
Ask tests/questions.yml through the appliance's ask surface — the kg_ask tool the app's question box
calls — and check every answer.

Answerable questions reconcile against a named view: the ask's top row must carry the view's
top-row figure (a number, a name, or a list of names). Money may come back in pence or in pounds,
and either reconciles. Unanswerable questions are asked several times each, because a fabrication
that shows one run in five is still a fabrication; each run's generated Cypher is checked against
the live schema (GET /api/v1/admin/kg/schema), and a property no Domesday label declares fails it.

    EMBABEL_AUTH='Bearer …' .cache/venv/bin/python tests/ask_battery.py [base-url] [--only N]

Exits non-zero on any failure. Prints each question's Cypher, so a failure can be read, not guessed.
"""
import collections
import json
import os
import re
import sys
import urllib.request

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
args = [a for a in sys.argv[1:] if not a.startswith('--')]
BASE = (args[0] if args else 'http://localhost:11043').rstrip('/')
AUTH = os.environ.get('EMBABEL_AUTH')
# the app's Ask box scopes every question to Domesday; the battery asks what users actually send
ASK_PREFIX = os.environ.get('ASK_PREFIX', 'In Domesday Book (1086): ')
# ASK_SCHEMA_LINKING=1/0 sends the ask's experimental per-request schema-linking switch; unset sends nothing.
SCHEMA_LINKING = {'1': True, '0': False}.get(os.environ.get('ASK_SCHEMA_LINKING', ''))
# ASK_EXAMPLE_RETRIEVAL=k shows the generator only the k nearest examples; ASK_EXAMPLE_SHORTCUT=1 lets a
# near-exact example answer without generation. Both experimental, per request; unset sends nothing.
EXAMPLE_RETRIEVAL = int(os.environ['ASK_EXAMPLE_RETRIEVAL']) if os.environ.get('ASK_EXAMPLE_RETRIEVAL') else None
EXAMPLE_SHORTCUT = {'1': True, '0': False}.get(os.environ.get('ASK_EXAMPLE_SHORTCUT', ''))
# ASK_SCOPE=<focus> sends the ask's `scope`, as the app does (`domesday`, the realm's own focus): the model
# sees that focus's realms and nothing else. Unset sends nothing, and the appliance resolves from the question.
SCOPE = os.environ.get('ASK_SCOPE')
ONLY = next((a.split('=')[1] for a in sys.argv[1:] if a.startswith('--only=')), None)


def post(path, body, timeout=300):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), method='POST',
                                 headers={'content-type': 'application/json', 'Authorization': AUTH})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def get(path):
    req = urllib.request.Request(BASE + path, headers={'Authorization': AUTH})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def ask(question):
    """The ask's result; a timeout or HTTP failure comes back as an empty result carrying the reason."""
    try:
        body = {'question': ASK_PREFIX + question, 'explain': True}
        if SCOPE:
            body['scope'] = SCOPE
        if SCHEMA_LINKING is not None:
            body['schemaLinking'] = SCHEMA_LINKING
        if EXAMPLE_RETRIEVAL is not None:
            body['exampleRetrieval'] = EXAMPLE_RETRIEVAL
        if EXAMPLE_SHORTCUT is not None:
            body['exampleShortcut'] = EXAMPLE_SHORTCUT
        return post('/api/v1/tools/kg_ask', body, timeout=180).get('result') or {}
    except Exception as e:
        return {'rows': [], 'cypher': '', 'failure': f'{type(e).__name__}: {e}'}


def view_top(name, view_args, column):
    rows = post(f'/api/v1/views/{name}/invoke', {'args': view_args or {}}).get('data') or []
    return rows[0].get(column) if rows else None


def numbers(value):
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, list):
        return [n for v in value for n in numbers(v)]
    return []


def strings(value):
    if isinstance(value, str):
        return [value.lower()]
    if isinstance(value, list):
        return [s for v in value for s in strings(v)]
    return []


ID_COLUMN = re.compile(r'(?i)(^id$|Id$|_id$|^ref$)')


MONEY_COLUMN = re.compile(r'(?i)pence|pounds|value|worth')
PERCENT_COLUMN = re.compile(r'(?i)percent|share')


def reconciles(expected, rows, column=''):
    """Does any value of the ask's top row carry the view's figure? An id column never counts: entry
    8146 is not 8,146 villagers."""
    if not rows:
        return False
    top = [v for k, v in rows[0].items() if not ID_COLUMN.search(k)]
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        # Domesday counts halves (a household shared between two manors), and an answer that rounds
        # 214,191.5 households to 214,192 states the same figure: a fractional count matches its whole.
        # A view's percentage is rounded to one place, so a share matches within the half-step that
        # rounding allows (4.035 is the view's 4.0; a fan-out's 3.71 or 4.06 is not).
        x = float(expected)
        targets = [(x, 0.05 if PERCENT_COLUMN.search(column) else 0.5 if x != int(x) else 0.005)]
        # Only money may come back in pence or in pounds, whichever the view or the answer chose; a view's
        # pounds are rounded to two places, so pence match within the 2.4d that rounding allows. A count of
        # 240 households is not one household.
        if MONEY_COLUMN.search(column):
            targets += [(x / 240, 0.005), (x * 240, 2.5)]
        return any(abs(n - t) <= e for v in top for n in numbers(v) for t, e in targets)
    wanted = strings(expected)
    have = [s for v in top for s in strings(v)]
    return bool(wanted) and all(any(w in h or h in w for h in have) for w in wanted)


def fold(text):
    """A name reduced to what identifies it: accents folded, punctuation and Hull's slashes dropped."""
    import unicodedata
    t = unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9 ]+', ' ', t.replace('/', ' '))


TITLES = {'of', 'the', 'and', 'bishop', 'count', 'earl', 'king', 'queen', 'abbey', 'abbot', 'church', 'st', 'saint'}


def same_name(want, have):
    """Does `have` name the bearer of `want`? Every significant word of the expected name must appear."""
    w = {t for t in fold(want).split() if len(t) > 2 and t not in TITLES} or set(fold(want).split())
    return w <= set(fold(have).split())


def declared_properties():
    schema = get('/api/v1/admin/kg/schema')
    props = {}
    for label in schema.get('labels', []):
        if label.get('label', '').startswith('Domesday'):
            props[label['label']] = {p['name'] for p in label.get('properties', [])}
    return props


def fabricated(cypher, props):
    """Properties the query reads on a Domesday-labelled variable that no Domesday label declares."""
    variables = {}
    for var, label in re.findall(r'\((\w+)\s*:\s*(Domesday\w+)', cypher or ''):
        variables[var] = label
    known = set().union(*props.values()) if props else set()
    used = {(v, p) for v, p in re.findall(r'\b(\w+)\.(\w+)', cypher or '') if v in variables}
    return sorted(f'{variables[v]}.{p}' for v, p in used if p not in props.get(variables[v], known))


def run_answerable(i, case, props):
    q, expect = case['question'], case['expect']
    result = ask(q)
    rows, cypher = result.get('rows') or [], result.get('cypher', '')
    problem = result.get('failure')
    bad = fabricated(cypher, props)
    if problem:
        pass
    elif bad:
        problem = f'fabricated {bad}'
    elif 'matchesView' in expect:
        mv = expect['matchesView']
        # `column` may name several: any one of them reconciling is the figure (households, or the
        # estimate made from them)
        columns = mv['column'] if isinstance(mv['column'], list) else [mv['column']]
        wants = [view_top(mv['name'], mv.get('args'), c) for c in columns]
        if not any(reconciles(w, rows, c) for w, c in zip(wants, columns)):
            problem = f'expected {mv["name"]}.{"|".join(columns)} = {wants!r}, got {rows[:2]}'
    elif 'value' in expect:
        # a literal from Open Domesday: money may come back in pence or in pounds, within a few pence
        want, top = float(expect['value']), [v for k, v in (rows[0].items() if rows else []) if not ID_COLUMN.search(k)]
        tol = [(want, 4), (want / 240, 0.02)] if expect.get('money') else [(want, 1e-6)]
        if not any(abs(n - t) <= e for v in top for n in numbers(v) for t, e in tol):
            problem = f'expected {want:g}{" pence" if expect.get("money") else ""} ({case.get("source")}), got {rows[:2]}'
    elif 'name' in expect or 'anyName' in expect:
        wants = expect.get('anyName') or [expect['name']]
        have = [x for r in rows[:3] for v in r.values() for x in strings(v)]
        if not any(same_name(w, h) for w in wants for h in have):
            problem = f'expected a name like {" or ".join(map(repr, wants))} ({case.get("source")}), got {rows[:3]}'
    # A second check, not part of the chain above: it applies once the figure itself has passed.
    if problem is None and expect.get('columnsLike'):
        cols = [k.lower() for k in (rows[0] if rows else {})]
        missing = [c for c in expect['columnsLike'] if not any(c in k for k in cols)]
        if missing:
            problem = f'the answer must carry a column like {missing} (households are not people), got columns {cols}'
    elif expect.get('minRows') and len(rows) < expect['minRows']:
        problem = f'{len(rows)} rows, wanted {expect["minRows"]}'
    elif expect.get('nonEmpty') and not rows:
        problem = 'no rows'
    category = case.get('category', 'asked')
    if problem and case.get('realm') and not result.get('failure'):
        # Ground truth disagrees. If the realm's own view says what the ask said, the question was
        # answered right and the realm's DATA differs from the outside source: a data finding, kept apart.
        rv = case['realm']
        realm_value = view_top(rv['view'], rv.get('args'), rv['column'])
        realm_silent = realm_value in (None, [], '') or realm_value == [None]
        if (realm_value is not None and reconciles(realm_value, rows, rv['column'])) or (realm_silent and not rows):
            category, problem = 'data-differs', f'realm says {realm_value!r}; {problem}'
    return {'id': f'A{i}', 'question': q, 'category': category, 'ok': problem is None,
            'problem': problem, 'cypher': cypher, 'ms': result.get('cost', {}).get('ms'),
            'llmCalls': result.get('cost', {}).get('llmCalls'), 'linking': result.get('linking'), 'exposure': result.get('exposure'),
            'maxExampleSimilarity': result.get('maxExampleSimilarity'), 'answeredBy': result.get('answeredBy')}


# A caveat travelling with a proxy figure. Beyond the plain refusals, a model names the substitution
# itself: "records values for 1086, not 1100", "households, not people", "in ploughlands, not acres",
# "not a complete county total", "may not cover the whole county". A column named for the caveat counts too.
CAVEAT = re.compile(r'(?i)not recorded|no data|does not record|not in domesday|unavailable|not available|cannot'
                    r'|\brecords? \w+ (?:for|in) 1086,? not\b|,\s*not (?:people|persons|population|acres|\d{4})\b'
                    r'|\bno \d{4} (?:value|figure|data)'
                    r'|\bnot an? (?:complete|whole|full|county|population|acreage)\b|\bnot a \w+ (?:count|total)\b'
                    r'|\bmay not cover\b')
# A plain `note` column is not one: its text must say the caveat. These names say it themselves.
NOTE_COLUMN = re.compile(r'(?i)caveat|warning|limitation|isnot|not.?recorded|no.?data|unavailable')
# Bookkeeping columns carry numbers that are no one's answer: an ingestion timestamp is not a figure put forward.
BOOKKEEPING_COLUMN = re.compile(r'[Tt]imestamp|[a-z]At$|_at$')


def run_unanswerable(i, run, case, props):
    q = case['question']
    result = ask(q)
    rows, cypher = result.get('rows') or [], result.get('cypher', '')
    bad = fabricated(cypher, props)
    figures = [n for r in rows for k, v in r.items() if not ID_COLUMN.search(k) and not BOOKKEEPING_COLUMN.search(k)
               for n in numbers(v) if n > 0]
    # The spec counts an honestly flagged answer as correct: a figure that travels with its own
    # "this is not recorded" note is not a fabrication; a bare proxy figure is.
    flagged = any(re.search(CAVEAT, s) for r in rows for v in r.values() for s in strings(v)) or any(
                  re.search(NOTE_COLUMN, k) for r in rows for k in r)
    if flagged:
        figures = []
    problem = (result.get('failure') or (f'fabricated {bad}' if bad
               else f'put forward {figures[:3]} as an answer' if case.get('noFigure') and figures else None))
    return {'id': f'U{i}.{run + 1}', 'question': q, 'category': 'adversarial', 'ok': problem is None,
            'problem': problem, 'cypher': cypher, 'ms': result.get('cost', {}).get('ms'),
            'llmCalls': result.get('cost', {}).get('llmCalls'), 'linking': result.get('linking'), 'exposure': result.get('exposure'),
            'maxExampleSimilarity': result.get('maxExampleSimilarity'), 'answeredBy': result.get('answeredBy')}


def main():
    if not AUTH:
        sys.exit('set EMBABEL_AUTH to the Authorization header value')
    props = declared_properties()
    answerable, unanswerable = [], []
    for name in ('questions.yml', 'questions.generated.yml', 'questions.groundtruth.yml'):
        path = os.path.join(HERE, name)
        if os.path.exists(path):
            battery = yaml.safe_load(open(path)) or {}
            answerable += battery.get('answerable', [])
            unanswerable += battery.get('unanswerable', [])
    jobs = [(run_answerable, (i, c, props)) for i, c in enumerate(answerable, 1)]
    jobs += [(run_unanswerable, (i, r, c, props)) for i, c in enumerate(unanswerable, 1) for r in range(c.get('repeat', 1))]
    if ONLY:
        jobs = [j for j in jobs if (f'A{j[1][0]}' if j[0] is run_answerable else f'U{j[1][0]}') == ONLY]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=int(os.environ.get('WORKERS', 4))) as pool:
        results = list(pool.map(lambda j: j[0](*j[1]), jobs))
    for r in results:
        if not r['ok']:
            print(f"FAIL {r['id']} [{r['category']}] {r['question']}\n       {r['problem']}\n       cypher: {' '.join((r['cypher'] or '').split())}")
    by = collections.defaultdict(lambda: [0, 0])
    for r in results:
        by[r['category']][0] += r['ok']
        by[r['category']][1] += 1
    print()
    for cat, (ok, n) in sorted(by.items()):
        print(f'  {cat:16} {ok:4}/{n:<4} {ok / n:6.1%}')
    judged = [r for r in results if r['category'] != 'data-differs']
    passed = sum(r['ok'] for r in judged)
    differs = len(results) - len(judged)
    print(f'{passed}/{len(judged)} passed' + (f'; {differs} answered as the realm holds it, where the realm differs from the outside source (data findings, listed above)' if differs else ''))
    out = os.environ.get('BATTERY_OUT')
    if out:
        json.dump(results, open(out, 'w'), indent=1)
    sys.exit(0 if passed == len(judged) else 1)


if __name__ == '__main__':
    main()
