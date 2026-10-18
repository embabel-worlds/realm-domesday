"""
Run every Domesday view through the appliance's own invoke endpoint, with its defaults and with each
case below, and fail on zero rows, a warning, or a figure that is not what the source says.

A view that parses, loads and returns nothing looks exactly like a source with no data, so every
view has at least one case that must return rows, and the cases that know a fact assert it: Abberley
is entry 8146 with 18 villagers and £10 10s in 1086 (Open Domesday agrees), and King William heads
the landholders of 1086.

    python3 tests/test_views.py [base-url]        # default http://localhost:11043

Credentials: EMBABEL_AUTH, the full Authorization header value (Basic … or Bearer …).
"""
import json
import os
import sys
import time
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:11043').rstrip('/')
AUTH = os.environ.get('EMBABEL_AUTH')

"""(view, params, check) — check takes the rows and returns an error string or None."""
CASES = [
    ('DomesdayPlaceSearch', {}, lambda r: None if any(x['place'] == 'Abberley' for x in r) else 'no Abberley'),
    ('DomesdayPlaceSearch', {'name': 'norton', 'limit': 200},
     lambda r: None if len(r) >= 20 else f'only {len(r)} Nortons'),
    ('DomesdayPersonSearch', {}, lambda r: None if any('Tosny' in x['person'] for x in r) else 'no Tosny'),
    ('DomesdayPersonSearch', {'name': 'harold'}, None),
    ('DomesdayPlaceEntries', {}, lambda r: None if r and r[0]['villagers'] == 18 and r[0]['value1086Pence'] == 2520
     else f'Abberley figures wrong: {r[:1]}'),
    ('DomesdayEntryDetail', {}, lambda r: None if r and r[0]['ref'] == 'Worcestershire 15,8'
     and any(p['role'] == 'LORD_1066' for p in r[0]['people']) else f'entry 8146 wrong: {r[:1]}'),
    ('DomesdayPersonHoldings', {}, None),
    ('DomesdayPersonHoldings', {'name': 'Earl Harold'}, lambda r: None if len(r) > 50 else f'Harold holds {len(r)}'),
    ('DomesdayPersonSummary', {}, None),
    ('DomesdayGreatestLandholders', {}, lambda r: None if r and r[0]['tenantInChief'] == 'King William'
     else f'first is {r[0]["tenantInChief"] if r else None}'),
    ('DomesdayGreatestLords1066', {}, None),
    ('DomesdayConquestTransfers', {}, None),
    ('DomesdayConquestTransfers', {'lord1066': 'harold'}, None),
    ('DomesdayWomenLandholders', {}, None),
    ('DomesdayLordsByPeasants', {}, lambda r: None if r and r[0]['holder'] == 'King William' else f'first is {r[:1]}'),
    ('DomesdayLordsByPeasants', {'role': 'LORD_1066', 'limit': 5}, None),
    ('DomesdayCounties', {}, lambda r: None if len(r) == 34 else f'{len(r)} counties'),
    ('DomesdayCountySummary', {}, lambda r: None if len(r) >= 31 else f'{len(r)} counties summarised'),
    ('DomesdayCountyFigures', {}, lambda r: None if len(r) == 1 and r[0]['county'].startswith('All England') and r[0]['villagers'] > 90000 else f'England figures: {r[:1]}'),
    ('DomesdayCountyFigures', {'county': 'WOR'}, lambda r: None if r and r[0]['villagers'] == 1540 else f'WOR figures: {r[:1]}'),
    ('DomesdayCountyFigures', {'county': 'YKS'}, lambda r: None if r and r[0]['wasteEntries'] > 300 else f'YKS waste {r[:1]}'),
    ('DomesdayCountyRanking', {}, lambda r: None if len(r) == 31 and r[0]['value'] >= r[-1]['value'] else f'ranking {r[:2]}'),
    ('DomesdayCountyRanking', {'measure': 'waste'}, lambda r: None if r and r[0]['county'] == 'Yorkshire' else f'waste ranking {r[:1]}'),
    ('DomesdayCountyRanking', {'measure': 'slaves', 'order': 'asc', 'limit': 3}, lambda r: None if len(r) == 3 and r[0]['value'] <= r[2]['value'] else f'asc {r}'),
    ('DomesdayCountyFigures', {}, None),
    ('DomesdayPopulation', {}, lambda r: None if r and r[0]['households'] == round(r[0]['households']) and abs(r[0]['estimatedPeopleLow'] - 4 * r[0]['households']) <= 4 and 'not people' in r[0]['note'] else f'population {r[:1]}'),
    ('DomesdayPopulation', {'county': 'KEN'}, lambda r: None if r and r[0]['area'] == 'Kent' else f'Kent population {r[:1]}'),
    ('DomesdayBeforeAndAfter', {}, lambda r: None if r and r[0]['comparableEntries'] > 10000 and r[0]['rose'] + r[0]['fell'] + r[0]['heldSteady'] == r[0]['comparableEntries'] and '1086 only' in r[0]['note'] else f'before/after {r[:1]}'),
    ('DomesdayBeforeAndAfter', {'county': 'YKS'}, lambda r: None if r and r[0]['valueChangePercent'] < -40 else f'Yorkshire should have fallen hard: {r[:1]}'),
    ('DomesdayHundredSummary', {}, None),
    ('DomesdayHundredSummary', {'county': 'YKS'}, None),
    ('DomesdayRichestManors', {}, None),
    ('DomesdayRichestManors', {'county': 'KEN', 'limit': 5}, None),
    ('DomesdayValueChange', {}, lambda r: None if all(x['changePounds'] < 0 for x in r) else 'a rise among falls'),
    ('DomesdayValueChange', {'direction': 'rise', 'county': 'WOR'},
     lambda r: None if all(x['changePounds'] > 0 for x in r) else 'a fall among rises'),
    ('DomesdayWaste', {}, lambda r: None if r and r[0]['countyOrEntry'] == 'Yorkshire' else f'first is {r[:1]}'),
    ('DomesdayWaste', {'county': 'YKS', 'limit': 10}, None),
    ('DomesdayFeature', {}, None),
    ('DomesdayFeature', {'feature': 'market'}, None),
    ('DomesdayFeature', {'feature': 'church', 'county': 'WOR', 'limit': 5}, None),
    ('DomesdayMapPlaces', {'county': 'WOR'}, lambda r: None if len(r) > 200 else f'{len(r)} Worcestershire places'),
    ('DomesdayMapPlaces', {}, lambda r: None if len(r) > 13000 else f'{len(r)} places on the map'),
    ('DomesdayPlacesNear', {}, lambda r: None if r and r[0]['place'] == 'Abberley' else f'nearest is {r[:1]}'),
    ('DomesdayPlacesNear', {'lat': 51.5074, 'lng': -0.1278, 'km': 5}, None),
]

BUDGET_MS = 2000
FIRST_PAINT = {'DomesdayCounties', 'DomesdayCountySummary', 'DomesdayMapPlaces', 'DomesdayGreatestLandholders'}


def invoke(view, params):
    req = urllib.request.Request(f'{BASE}/api/v1/views/{view}/invoke', data=json.dumps({'args': params}).encode(),
                                 headers={'content-type': 'application/json', 'Authorization': AUTH}, method='POST')
    started = time.time()
    with urllib.request.urlopen(req, timeout=180) as r:
        body = json.loads(r.read())
    return body, int((time.time() - started) * 1000)


def main():
    if not AUTH:
        sys.exit('set EMBABEL_AUTH to the Authorization header value')
    failures = 0
    for view, params, check in CASES:
        try:
            body, ms = invoke(view, params)
        except Exception as e:
            print(f'FAIL {view} {params}: {e}')
            failures += 1
            continue
        rows, warnings = body.get('data') or [], body.get('warnings') or []
        problem = (f'{body.get("status")} {body.get("outcome")} {body.get("error") or body.get("message")}'
                   if body.get('status') != 'SUCCEEDED'
                   else 'no rows' if not rows else '; '.join(map(str, warnings)) if warnings
                   else check(rows) if check else None)
        if problem is None and view in FIRST_PAINT and not params and ms > BUDGET_MS:
            problem = f'{ms} ms, over the {BUDGET_MS} ms first-paint budget'
        failures += problem is not None
        print(f"{'ok  ' if problem is None else 'FAIL'} {view} {json.dumps(params)} rows={len(rows)} {ms}ms"
              + (f'  — {problem}' if problem else ''))
    print(f'{len(CASES) - failures}/{len(CASES)} cases passed')
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
