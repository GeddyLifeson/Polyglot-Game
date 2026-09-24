"""
import_rodais.py -- write the Diathìris word files (content/xlate_gr_<band>.py) from the Diathìris dictionary.

    python3 tools/import_rodais.py <rodais-folder>

<rodais-folder> is the folder of the Diathìris language (GeddyLifeson/panscriptum,
reference/owner_source_material/rodais/), holding LEXICON.json and rodais_engine.py. Its dictionary covers
every word of the ladder under the ladder's own ids. Each word becomes (text, reading):

    text      the headword as the other languages show theirs: first letter capitalised; a verb shows its
              verbal noun (Ithe "eating, to eat"), the form a Gaelic phrasebook gives
    reading   the pronunciation in IPA, from the language's own pronunciation rules

Re-run it whenever the dictionary changes; it overwrites only the five xlate_gr_<band>.py word files.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.join(os.path.dirname(HERE), 'content')
BANDS = [('a1a2', ('a1-', 'a2-')), ('b1', ('b1-',)), ('b2', ('b2-',)), ('c1', ('c1-',)), ('c2', ('c2-',))]


def cap(s):
    return s[:1].upper() + s[1:] if s else s


def main():
    if len(sys.argv) != 2 or not os.path.isfile(os.path.join(sys.argv[1], 'LEXICON.json')):
        sys.exit(__doc__)
    src = sys.argv[1]
    sys.path.insert(0, src)
    import rodais_engine as R
    lex = json.load(open(os.path.join(src, 'LEXICON.json'), encoding='utf-8'))['entries']
    ladder = {e['id']: e for e in lex if not e['id'].startswith('f-')}
    for band, prefixes in BANDS:
        rows = []
        for i, e in sorted(ladder.items()):
            if not i.startswith(prefixes):
                continue
            text = e.get('vn') if e.get('pos') == 'v' and e.get('vn') and ' ' not in e['rod'] else e['rod']
            text = cap(text)
            rows.append('    %r: (%r, %r),' % (i, text, R.pronounce(text.rstrip('?!.'))))
        path = os.path.join(CONTENT, 'xlate_gr_%s.py' % band)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write('# -*- coding: utf-8 -*-\n# Diathìris, the tongue of Diathìr: written by tools/import_rodais.py from the Diathìris dictionary.\n'
                     "# The reading line is the pronunciation in IPA.\nLANG = 'gr'\nWORDS = {\n%s\n}\n" % '\n'.join(rows))
        print('%s: %d words' % (os.path.basename(path), len(rows)))


if __name__ == '__main__':
    main()
