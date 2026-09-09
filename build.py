# -*- coding: utf-8 -*-
"""
Assembles every content file under content/ into one generated JS block and splices it into
index.html between the GENERATED CONTENT markers.

Content file kinds:
  content/*.json  -> {"type": "vocab", "rows": [...]} or {"type": "sentences"|"grammar"|"idioms"|"nuance"|"dialogues"|"listen", "items": [...]}
  content/*.py    -> python module exporting any of:
                       TIER = 'A1'                        (default tier for WORDS in this file)
                       TOPICS = {key: label}
                       WORDS = [ (en, emoji, topic, es, fr, it, pt, ja, zh, pinyin[, fact]), ... ]  (tier = TIER)
                                or dict rows {en, emoji, topic, tier?, es, fr, it, pt, ja, zh, pinyin?, fact?, id?}
                       SENTENCES, GRAMMAR, IDIOMS, NUANCE, DIALOGUES, LISTEN = [dict, ...]

Vocab row -> JS compact row: [id, en, emoji, topic, tier, es, fr, it, pt, ja, zh, pinyin, fact?]
"""
import glob, importlib.util, json, os, re, sys, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.join(HERE, 'content')
HTML = os.path.join(HERE, 'index.html')
LANGS = ['es', 'fr', 'it', 'pt', 'ja', 'zh']
TIERS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']

vocab_rows, sentences, grammar, idioms, nuance, dialogues, listen = [], [], [], [], [], [], []
topic_labels = {}
errors, warnings = [], []


def slug(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    s = re.sub(r'[^a-zA-Z0-9]+', '-', s).strip('-').lower()
    return s or 'x'


def load_py(path):
    spec = importlib.util.spec_from_file_location('content_' + slug(os.path.basename(path)), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def add_vocab(row, default_tier, src):
    if isinstance(row, dict):
        d = dict(row)
        d.setdefault('tier', default_tier)
        d.setdefault('pinyin', '')
    else:
        if len(row) not in (10, 11):
            errors.append('%s: vocab row needs 10 or 11 fields, got %d: %r' % (src, len(row), row[:2]))
            return
        d = dict(en=row[0], emoji=row[1], topic=row[2], tier=default_tier,
                 es=row[3], fr=row[4], it=row[5], pt=row[6], ja=row[7], zh=row[8], pinyin=row[9])
        if len(row) == 11:
            d['fact'] = row[10]
    for k in ['en', 'emoji', 'topic', 'tier'] + LANGS:
        if not d.get(k):
            errors.append('%s: vocab "%s" missing %s' % (src, d.get('en'), k))
    if d['tier'] not in TIERS:
        errors.append('%s: vocab "%s" bad tier %s' % (src, d.get('en'), d['tier']))
    vocab_rows.append(d)


def add_items(target, items, kind, src, default_tier=None):
    for it in items:
        d = dict(it)
        if default_tier and not d.get('tier'):
            d['tier'] = default_tier
        d['_src'] = src
        target.append(d)


# ---------------- load ----------------
for path in sorted(glob.glob(os.path.join(CONTENT, '*.json'))):
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    src = os.path.basename(path)
    t = data.get('type')
    if t == 'vocab':
        for row in data['rows']:
            # legacy json rows: [en, emoji, topic, tier, es, fr, it, pt, ja, zh, pinyin, fact?]
            d = dict(en=row[0], emoji=row[1], topic=row[2], tier=row[3], es=row[4], fr=row[5], it=row[6], pt=row[7],
                     ja=row[8], zh=row[9], pinyin=row[10])
            if len(row) > 11:
                d['fact'] = row[11]
            add_vocab(d, row[3], src)
    else:
        target = {'sentences': sentences, 'grammar': grammar, 'idioms': idioms, 'nuance': nuance,
                  'dialogues': dialogues, 'listen': listen}[t]
        add_items(target, data['items'], t, src)

for path in sorted(glob.glob(os.path.join(CONTENT, '*.py'))):
    src = os.path.basename(path)
    mod = load_py(path)
    topic_labels.update(getattr(mod, 'TOPICS', {}))
    tier = getattr(mod, 'TIER', None)
    for row in getattr(mod, 'WORDS', []):
        add_vocab(row, tier, src)
    add_items(sentences, getattr(mod, 'SENTENCES', []), 'sentences', src, tier)
    add_items(grammar, getattr(mod, 'GRAMMAR', []), 'grammar', src, tier)
    add_items(idioms, getattr(mod, 'IDIOMS', []), 'idioms', src, tier)
    add_items(nuance, getattr(mod, 'NUANCE', []), 'nuance', src, tier)
    add_items(dialogues, getattr(mod, 'DIALOGUES', []), 'dialogues', src, tier)
    add_items(listen, getattr(mod, 'LISTEN', []), 'listen', src, tier)

# ---------------- ids + validation ----------------
ids = set()
def claim(i, what):
    if i in ids:
        errors.append('duplicate id %s (%s)' % (i, what))
    ids.add(i)

for d in vocab_rows:
    if not d.get('id'):
        base = d['tier'].lower() + '-' + slug(d['en'])
        cand, n = base, 2
        while cand in ids:
            cand = '%s-%d' % (base, n); n += 1
        d['id'] = cand
    claim(d['id'], 'vocab')

for d in sentences:
    claim(d['id'], 'sentence')
    for l in LANGS:
        if not isinstance(d.get(l), list) or not d[l]:
            errors.append('sentence %s missing tiles for %s' % (d['id'], l))
for d in grammar + idioms + nuance:
    claim(d['id'], 'per-lang item')
    if d.get('lang') not in LANGS:
        errors.append('item %s bad lang' % d['id'])
    if d.get('correct') not in d.get('options', []):
        errors.append('item %s: correct answer not in options' % d['id'])
for d in dialogues:
    claim(d['id'], 'dialogue')
    for l in LANGS:
        v = d.get(l)
        if not isinstance(v, list) or len(v) != 5:
            errors.append('dialogue %s: %s must be [line, correct, wrong, wrong, wrong]' % (d['id'], l))
for d in listen:
    claim(d['key'], 'listen module')
    if d.get('source') not in ('vocab', 'sentences', 'dialogues'):
        errors.append('listen %s bad source' % d['key'])

# (tier, topic) -> single type; topics exist for every tier; labels exist
topic_type = {}
def reg_topic(tier, topic, typ, what):
    k = (tier, topic)
    if k in topic_type and topic_type[k] != typ:
        errors.append('topic %s in %s used by both %s and %s' % (topic, tier, topic_type[k], typ))
    topic_type[k] = typ
    if topic not in topic_labels:
        warnings.append('no label for topic %s (%s) — will be auto-humanized' % (topic, what))

for d in vocab_rows: reg_topic(d['tier'], d['topic'], 'match', 'vocab')
for d in sentences: reg_topic(d['tier'], d['topic'], 'build', 'sentences')
for d in grammar: reg_topic(d['tier'], d['topic'], 'blank', 'grammar')
for d in idioms: reg_topic(d['tier'], d['topic'], 'idiom', 'idioms')
for d in nuance: reg_topic(d['tier'], d['topic'], 'nuance', 'nuance')
for d in dialogues: reg_topic(d['tier'], d['topic'], 'dialogue', 'dialogues')
for d in listen: reg_topic(d['tier'], d['key'], 'listen', 'listen')

# no duplicate English labels within a tier (match options would show two identical answers)
seen_en = {}
for d in vocab_rows:
    k = (d['tier'], d['en'].strip().lower())
    if k in seen_en:
        errors.append('duplicate English "%s" in %s (%s and %s)' % (d['en'], d['tier'], seen_en[k], d['id']))
    seen_en[k] = d['id']

# listening modules need material to draw from
for d in listen:
    n = 0
    if d['source'] == 'vocab': n = sum(1 for v in vocab_rows if v['tier'] == d['tier'])
    elif d['source'] == 'sentences': n = sum(1 for v in sentences if v['tier'] == d['tier'])
    else: n = sum(1 for v in dialogues if v['tier'] == d['tier'])
    if n < 4:
        errors.append('listen module %s (%s) has only %d source items' % (d['key'], d['tier'], n))

# per-language pools must have >=1 item per language per topic
for name, pool in [('grammar', grammar), ('idioms', idioms), ('nuance', nuance)]:
    combos = {}
    for d in pool:
        combos.setdefault((d['tier'], d['topic']), set()).add(d['lang'])
    for (tier, topic), langs in combos.items():
        missing = [l for l in LANGS if l not in langs]
        if missing:
            errors.append('%s topic %s/%s has no items for %s' % (name, tier, topic, ','.join(missing)))

if errors:
    print('BUILD FAILED — %d error(s):' % len(errors))
    for e in errors[:60]:
        print('  -', e)
    sys.exit(1)
for w in warnings[:40]:
    print('  warn:', w)

# ---------------- emit ----------------
def js(v):
    return json.dumps(v, ensure_ascii=False, separators=(',', ':'))

def strip(d):
    return {k: v for k, v in d.items() if not k.startswith('_')}

vocab_js_rows = []
for d in vocab_rows:
    row = [d['id'], d['en'], d['emoji'], d['topic'], d['tier'], d['es'], d['fr'], d['it'], d['pt'], d['ja'], d['zh'], d.get('pinyin', '')]
    if d.get('fact'):
        row.append(d['fact'])
    vocab_js_rows.append(js(row))

# topic order per tier, in authored order
tier_topics = {}
for d in vocab_rows: tier_topics.setdefault(d['tier'], []).append(d['topic']) if d['topic'] not in tier_topics.get(d['tier'], []) else None

out = []
out.append('  /* ==== GENERATED CONTENT START (build.py — do not hand-edit) ==== */')
out.append('  /* vocab row: [id, en, emoji, topic, tier, es, fr, it, pt, ja, zh, pinyin, fact?] */')
out.append('  var VOCAB_RAW = [\n' + ',\n'.join('    ' + r for r in vocab_js_rows) + '\n  ];')
out.append('  var TOPIC_LABELS = ' + js(topic_labels) + ';')
out.append('  var BUILD_SENTENCES = [\n' + ',\n'.join('    ' + js(strip(d)) for d in sentences) + '\n  ];')
out.append('  var GRAMMAR_ITEMS = [\n' + ',\n'.join('    ' + js(strip(d)) for d in grammar) + '\n  ];')
out.append('  var IDIOMS = [\n' + ',\n'.join('    ' + js(strip(d)) for d in idioms) + '\n  ];')
out.append('  var NUANCE = [\n' + ',\n'.join('    ' + js(strip(d)) for d in nuance) + '\n  ];')
out.append('  var DIALOGUES = [\n' + ',\n'.join('    ' + js(strip(d)) for d in dialogues) + '\n  ];')
out.append('  var LISTEN_MODULES = [\n' + ',\n'.join('    ' + js(strip(d)) for d in listen) + '\n  ];')
out.append('  /* ==== GENERATED CONTENT END ==== */')
block = '\n'.join(out)

with open(HTML, encoding='utf-8') as f:
    html = f.read()
m = re.search(r'  /\* ==== GENERATED CONTENT START.*?/\* ==== GENERATED CONTENT END ==== \*/', html, re.DOTALL)
if not m:
    print('markers not found in HTML'); sys.exit(1)
html = html[:m.start()] + block + html[m.end():]
with open(HTML, 'w', encoding='utf-8') as f:
    f.write(html)

# ---------------- report ----------------
per_tier = {t: 0 for t in TIERS}
for d in vocab_rows: per_tier[d['tier']] += 1
print('vocab: %d total  %s' % (len(vocab_rows), '  '.join('%s=%d' % (t, per_tier[t]) for t in TIERS)))
print('sentences %d | grammar %d | idioms %d | nuance %d | dialogues %d | listen modules %d' % (
    len(sentences), len(grammar), len(idioms), len(nuance), len(dialogues), len(listen)))
print('generated block: %d KB' % (len(block.encode('utf-8')) // 1024))
