# -*- coding: utf-8 -*-
"""Extract every English-only string the game shows to a non-English speaker into l10n_in/*.json, so
translation agents can work from compact sources. Run after build.py.

  notes.json      coach texts, item notes (grammar / idiom / nuance / sentence / dialogue), idiom option
                  meanings, nuance contexts, dialogue setups
  questions.json  comprehension questions for every story (shared + folk)
  folk_<k>.json   the folk tales' English side (title + 7 paragraphs), in three chunks

Agents write l10n_out/<lang>_<chunk>.json with the same shape; tools/l10n_check.py validates; build.py
assembles l10n/<lang>.json for the game."""
import json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
h = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()

def block(name):
    m = re.search(r'var ' + name + r' = (\[.*?\n  \]);', h, re.S)
    return json.loads(m.group(1))

S = block('BUILD_SENTENCES'); G = block('GRAMMAR_ITEMS'); I = block('IDIOMS'); N = block('NUANCE'); D = block('DIALOGUES'); ST = block('STORIES')
m = re.search(r'var COACH = \{(.*?)\n  \};', h, re.S)
coach = dict(re.findall(r"\n\s+(\w+):\s+'((?:[^'\\]|\\.)*)'", m.group(0)))
coach = {k: v.replace("\\'", "'") for k, v in coach.items()}

notes = {}
for x in G + I + N + S + D:
    if x.get('note'): notes[x['id']] = x['note']
out = {
    'coach': coach,
    'notes': notes,
    'idiom_options': {x['id']: x['options'] for x in I},
    'nuance_context': {x['id']: x['context'] for x in N},
    'setups': {x['id']: x['setup'] for x in D},
}
os.makedirs(os.path.join(ROOT, 'l10n_in'), exist_ok=True)
json.dump(out, open(os.path.join(ROOT, 'l10n_in', 'notes.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump({s['id']: [{'q': q['q'], 'options': q['options']} for q in s['questions']] for s in ST},
          open(os.path.join(ROOT, 'l10n_in', 'questions.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
folk = [s for s in ST if s.get('only')]
k = 3
for i in range(k):
    chunk = {s['id']: {'lang': s['only'], 'title': s['title'], 'paras': s['paras']} for s in folk[i::k]}
    json.dump(chunk, open(os.path.join(ROOT, 'l10n_in', 'folk_%d.json' % (i + 1)), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('notes', len(notes), 'coach', len(coach), 'idiom opts', len(I), 'nuance ctx', len(N), 'setups', len(D), 'stories', len(ST), 'folk', len(folk), 'chunks', k)
