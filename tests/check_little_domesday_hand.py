"""
The figures of 30 Little Domesday entries, read by hand from the translation, against what
scripts/little_domesday.py makes of them.

The entries are a fixed random draw (seed 30) of those under 700 characters, read on 2026-10-19.
Only what the text states unambiguously is here. Where the reading is a judgement Hull makes one
way and the text does not settle — a lone named free man who may be the holder or a household, or
ploughs on land with no men stated — the field is left out rather than guessed, so a disagreement
here is a parser defect and nothing else. Values are in pence; geld units are acres at 120 to the
unit.

    .cache/venv/bin/python scripts/little_domesday.py .cache
    .cache/venv/bin/python tests/check_little_domesday_hand.py
"""
import collections
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HAND = {
    'SUF 6,111': {'freeMen': 1, 'value1086': 12, 'geldUnits': 0.0333},
    'NFK 9,5': {'smallholders': 2, 'freeMen': 1, 'value1086': 18, 'geldUnits': 0.25},
    'SUF 7,54': {'smallholders': 0.5, 'mensTeams': 0.5, 'meadowAcres': 0.5, 'value1066': 120, 'value1086': 36,
                 'geldUnits': 0.375},
    'SUF 7,11': {'villagers': 2, 'smallholders': 2, 'slaves': 1, 'meadowAcres': 2, 'value1066': 96, 'value1086': 144,
                 'geldUnits': 0.8333},
    'SUF 7,113': {'freeMen': 1, 'value1086': 24, 'geldUnits': 0.1},
    'SUF 4,22': {'smallholders': 10, 'slaves': 1, 'lordsTeams': 1, 'mensTeams': 1, 'woodlandPigs': 10,
                 'meadowAcres': 2, 'value1066': 120, 'value1086': 120, 'geldUnits': 0.5},
    'SUF 19,3': {'freeMen': 5, 'mensTeams': 1, 'value1086': 120, 'geldUnits': 0.5},
    'NFK 66,55': {'freeMen': 1, 'saltHouses': 1, 'value1086': 48, 'geldUnits': 0.1083},
    'SUF 8,73': {'geldUnits': 0.0625},
    'NFK 48,6': {'smallholders': 2, 'freeMen': 8.5, 'mensTeams': 2, 'oxen': 2, 'value1066': 120, 'value1086': 175,
                 'geldUnits': 0.8417},
    'SUF 8,75': {'freeMen': 1, 'value1086': 6, 'geldUnits': 0.025},
    'NFK 4,8': {'smallholders': 3, 'freemen': None, 'meadowAcres': 2, 'mensTeams': 2, 'woodlandPigs': 20,
                'value1086': 120, 'geldUnits': 0.55},
    'SUF 16,28': {'smallholders': 2, 'mensTeams': 1, 'meadowAcres': 1, 'value1086': 240, 'geldUnits': 0.5125},
    'ESS 20,69': {'villagers': 1, 'smallholders': 10, 'slaves': 1, 'freemen': 3, 'lordsTeams': 1, 'mensTeams': 3,
                  'meadowAcres': 8, 'cattle': 4, 'pigs': 8, 'sheep': 80, 'cobs': 1, 'woodlandPigs': 10,
                  'pastureSheep': 200, 'value1066': 2400, 'value1086': 2640, 'geldUnits': 2},
    'SUF 14,37': {'smallholders': 3, 'freeMen': 1, 'mensTeams': 1, 'meadowAcres': 4, 'value1066': 240,
                  'valueLater': 240, 'value1086': 240, 'geldUnits': 0.5},
    'NFK 10,81': {'smallholders': 10, 'freeMen': 19, 'mensTeams': 3, 'oxen': 2, 'meadowAcres': 22, 'value1066': 136,
                  'value1086': 376, 'geldUnits': 2.8833},
    'ESS 25,16': {'villagers': 6, 'smallholders': 16, 'slaves': 0, 'freeMen': None, 'lordsTeams': 2, 'mensTeams': 3,
                  'cobs': 0, 'pigs': 66, 'sheep': 200, 'beehives': 6, 'woodlandPigs': 20, 'meadowAcres': 20,
                  'value1066': 1200, 'value1086': 1920, 'geldUnits': 4.8333},
    'SUF 67,5': {'freeMen': 8, 'mills': 1, 'pigs': 8, 'meadowAcres': 4, 'value1066': 480,
                 'value1086': 280, 'geldUnits': 1.2167},
    'SUF 25,74': {'meadowAcres': 2, 'value1066': 60, 'value1086': 137, 'geldUnits': 0.25},
    'NFK 1,102': {'freeMen': 1, 'geldUnits': 0.0833},
    'ESS 20,78': {'villagers': 9, 'smallholders': 7, 'slaves': 6, 'freemen': 5, 'lordsTeams': 3, 'mensTeams': 5,
                  'cobs': 1, 'pigs': 14, 'sheep': 56, 'woodlandPigs': 20, 'meadowAcres': 10, 'value1066': 2640,
                  'value1086': 2880, 'geldUnits': 1},
    'NFK 31,36': {'freemen': 1, 'value1066': 1200, 'value1086': 1440, 'geldUnits': 0.1667, 'taxPence': 15},
    'NFK 8,26': {'smallholders': 14, 'freeMen': 13, 'lordsTeams': 1, 'mensTeams': 1, 'fisheries': 0.5,
                 'saltHouses': 0.5, 'meadowAcres': 8, 'value1086': 240, 'geldUnits': 1.125},
    'SUF 3,4': {'villagers': 6, 'smallholders': 5, 'freeMen': 17, 'mensTeams': 6, 'woodlandPigs': 30,
                'meadowAcres': 6.5, 'value1086': 12, 'geldUnits': 4.8833, 'taxPence': 7.5},
    'ESS 30,46': {'villagers': 1, 'smallholders': 9, 'slaves': 1, 'lordsTeams': 2, 'mensTeams': 0, 'cattle': 3,
                  'pigs': 30, 'sheep': 220, 'goats': 66, 'woodlandPigs': 30, 'meadowAcres': 10, 'value1066': 2640,
                  'value1086': 1680},
    'NFK 66,82': {'oxen': 2, 'value1086': 16, 'geldUnits': 0.125},
    'NFK 66,53': {'smallholders': 3, 'freeMen': None, 'mensTeams': 0.5, 'value1086': 48, 'geldUnits': 0.25},
    'NFK 1,178': {'freeMen': 11, 'mensTeams': 1, 'meadowAcres': 1, 'geldUnits': 0.25},
    'NFK 66,93': {'freeMen': 8, 'mensTeams': 0.5, 'oxen': 2, 'meadowAcres': 4.5, 'value1066': 24, 'value1086': 54,
                  'geldUnits': 0.2833},
    'NFK 8,27': {'smallholders': 25, 'slaves': 1, 'freeMen': 17, 'lordsTeams': 1, 'mensTeams': 2.5, 'mills': 1,
                 'saltHouses': 0.5, 'meadowAcres': 21, 'value1086': 504, 'geldUnits': 2.2833},
}


def main():
    entries = {e['entryId']: e for e in
               json.load(open(os.path.join(ROOT, '.cache', 'little_domesday.json'), encoding='utf-8'))['entries']}
    agree, compared, misses = collections.Counter(), collections.Counter(), []
    for ref, expected in HAND.items():
        for key, want in expected.items():
            got = entries[ref].get(key)
            compared[key] += 1
            # None is "the text states no such figure", and the parse must state none either
            if (want is None and got is None) or (want is not None and got is not None and abs(got - want) < 0.001):
                agree[key] += 1
            else:
                misses.append((ref, key, got, want))
    total = sum(compared.values())
    print(f'{len(HAND)} entries, {total} figures read by hand: {sum(agree.values())} agree')
    for key in sorted(compared, key=lambda k: -compared[k]):
        print(f'  {key:14} {agree[key]:3}/{compared[key]:<3}')
    for ref, key, got, want in misses:
        print(f'  MISS {ref:10} {key}: parsed {got}, text says {want}')
    sys.exit(1 if misses else 0)


if __name__ == '__main__':
    main()
