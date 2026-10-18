"""
Decode the Domesday Explorer Textbase into one record per entry: its coded spans.

The Textbase holds Phillimore's translation of Great Domesday word by word. Nobody documented the
format; this is what the bytes show:

- DataBase is one 8-byte record per word position, laid out (u16 0, u16 page, u16 id, u16 0).
  The word is the WordFile entry at byte offset page * 32704 + id - 1.
- WordFile is a sorted list of [3-byte pointer][length][word], the same 15,663 words as the
  WORDLIST table. It is cp1252, as the Windows program wrote it; the Paradox tables are cp437.
- range.DB rows are (Start, End) word positions, 1-based, and rangevalues.DB says which run of
  range ids carries which property code (POP, VAL, TE1, ... — the Mnemonics table names them).
- Structure.db gives each Phillimore entry its word span.

Output: <cache>/entries.jsonl, one object per Structure row, with the spans keyed by code. The text
itself is kept only so figures.py can read it; build_reference.py never writes it out, because it
is Phillimore's translation and not ours to republish.
"""
import bisect
import collections
import csv
import json
import struct
import sys

PAGE = 32704


def words(path):
    data = open(path, 'rb').read()
    by_offset, p = {}, 0
    while p + 4 <= len(data):
        if p and data[p:p + 4] == b'\0\0\0\0':
            break
        n = data[p + 3]
        by_offset[p] = data[p + 4:p + 4 + n].decode('cp1252')
        p += 4 + n
    return by_offset


def tokens(path, by_offset):
    data = open(path, 'rb').read()
    out = []
    for i in range(len(data) // 8):
        _, page, word_id, _ = struct.unpack_from('<HHHH', data, i * 8)
        out.append(by_offset.get(page * PAGE + word_id - 1))
    return out


def rows(path):
    with open(path, encoding='utf-8') as f:
        yield from csv.DictReader(f)


def integer(value):
    return int(float(value))


def main(cache):
    tb = f'{cache}/explorer/Textbase'
    toks = tokens(f'{tb}/DataBase', words(f'{tb}/WordFile'))
    text = lambda a, b: ' '.join(t for t in toks[a - 1:b] if t)

    code_of = {}
    for rv in rows(f'{cache}/csv/rangevalues.csv'):
        for k in range(integer(rv['Start']), integer(rv['End']) + 1):
            code_of[k] = rv['Type']
    ranges = sorted((integer(r['Start']), integer(r['End']), code_of[integer(r['RangeIdx'])])
                    for r in rows(f'{cache}/csv/range.csv'))
    starts = [r[0] for r in ranges]

    count = 0
    with open(f'{cache}/entries.jsonl', 'w') as out:
        for s in rows(f'{cache}/csv/Structure.csv'):
            a, b = integer(s['Start']), integer(s['End'])
            spans = collections.defaultdict(list)
            for x, y, code in ranges[bisect.bisect_left(starts, a):bisect.bisect_right(starts, b)]:
                if y <= b:
                    spans[code].append(text(x, y))
            out.write(json.dumps({'structIdx': s['StructIdx'], 'county': s['County'],
                                  'phillimore': s['Phillimore'], 'type': s['TextType'],
                                  'text': text(a, b), 'spans': spans}) + '\n')
            count += 1
    print(f'entries.jsonl: {count} entries')


if __name__ == '__main__':
    main(sys.argv[1])
