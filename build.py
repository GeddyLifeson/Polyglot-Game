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

# Every language the game knows. The first six are authored inline in the vocab rows and have studio
# recordings; the rest come from content/xlate_<lang>_*.py files (WORDS / SENTENCES / DIALOGUES dicts keyed
# by item id) and are offered only for the tiers they cover completely.
#   code: (English name, native name, flag, Web Speech locale, has a reading line, audio recorded)
LANG_META = {
    'es': ('Spanish', 'Español', '🇪🇸', 'es-ES', False, True),
    'fr': ('French', 'Français', '🇫🇷', 'fr-FR', False, True),
    'it': ('Italian', 'Italiano', '🇮🇹', 'it-IT', False, True),
    'pt': ('Portuguese', 'Português', '🇧🇷', 'pt-BR', False, True),
    'ja': ('Japanese', '日本語', '🇯🇵', 'ja-JP', False, True),
    'zh': ('Mandarin', '普通话', '🇨🇳', 'zh-CN', True, True),
    'de': ('German', 'Deutsch', '🇩🇪', 'de-DE', False, True),
    'nl': ('Dutch', 'Nederlands', '🇳🇱', 'nl-NL', False, True),
    'sv': ('Swedish', 'Svenska', '🇸🇪', 'sv-SE', False, True),
    'pl': ('Polish', 'Polski', '🇵🇱', 'pl-PL', False, True),
    'ru': ('Russian', 'Русский', '🇷🇺', 'ru-RU', True, True),
    'el': ('Greek', 'Ελληνικά', '🇬🇷', 'el-GR', True, True),
    'la': ('Latin', 'Latina', '🏛️', 'it-IT', False, False),
    'tr': ('Turkish', 'Türkçe', '🇹🇷', 'tr-TR', False, True),
    'ar': ('Arabic', 'العربية', '🇸🇦', 'ar-SA', True, True),
    'hi': ('Hindi', 'हिन्दी', '🇮🇳', 'hi-IN', True, True),
    'ko': ('Korean', '한국어', '🇰🇷', 'ko-KR', True, False),
    'yue': ('Cantonese', '廣東話', '🇭🇰', 'zh-HK', True, True),
    'vi': ('Vietnamese', 'Tiếng Việt', '🇻🇳', 'vi-VN', False, True),
    'ind': ('Indonesian', 'Bahasa Indonesia', '🇮🇩', 'id-ID', False, False),   # 'id' would collide with the item id field
}
XL = {}   # lang -> {'words': {id: (text, reading)}, 'sentences': {id: tiles}, 'dialogues': {id: 5 lines}}

vocab_rows, sentences, grammar, idioms, nuance, dialogues, listen = [], [], [], [], [], [], []
stories = []   # English source stories (content/stories_src.py); translations come from xlate_<lang>_stories.py
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

for path in sorted(glob.glob(os.path.join(CONTENT, 'xlate_*.py'))):
    src = os.path.basename(path)
    try:
        mod = load_py(path)
    except Exception as e:   # a translation file still being written is skipped, not fatal
        warnings.append('%s: skipped, does not parse yet (%s)' % (src, str(e).splitlines()[0][:80])); continue
    lang = getattr(mod, 'LANG', None)
    if lang not in LANG_META:
        errors.append('%s: unknown LANG %r (add it to LANG_META in build.py)' % (src, lang)); continue
    x = XL.setdefault(lang, {'words': {}, 'sentences': {}, 'dialogues': {}})
    for k, v in getattr(mod, 'WORDS', {}).items():
        t, r = (tuple(v) + (None,))[:2] if isinstance(v, (list, tuple)) else (v, None)
        if isinstance(t, str) and t.strip():
            x['words'][k] = (t.strip(), (r or '').strip() or None)
    x['sentences'].update(getattr(mod, 'SENTENCES', {}))
    x['dialogues'].update(getattr(mod, 'DIALOGUES', {}))
    # per-language skill drills authored for the added languages (same schema as the core files)
    for name, target in (('GRAMMAR', grammar), ('IDIOMS', idioms), ('NUANCE', nuance)):
        for it in getattr(mod, name, []):
            d = dict(it); d['lang'] = lang; d['_src'] = src
            if not d.get('tier'): errors.append('%s: %s item %s has no tier' % (src, name, d.get('id')))
            target.append(d)
    x['stories'] = x.get('stories', {})
    if isinstance(getattr(mod, 'STORIES', None), dict): x['stories'].update(mod.STORIES)

for path in sorted(glob.glob(os.path.join(CONTENT, '*.py'))):
    src = os.path.basename(path)
    if src.startswith('xlate_'):
        continue
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
    if isinstance(getattr(mod, 'STORIES', None), list):
        stories.extend(dict(x, _src=src) for x in mod.STORIES)
    # folk_<lang>.py: that culture's own tales, target text + English side by side, offered only for that language
    if isinstance(getattr(mod, 'FOLK', None), list) and getattr(mod, 'LANG', None):
        for x in mod.FOLK:
            stories.append({'id': x['id'], 'tier': x['tier'], 'title': x['title_en'], 'paras': x['paras_en'],
                            'questions': x['questions'], 'origin': x.get('origin', ''), 'only': mod.LANG,
                            '_xl': {mod.LANG: {'title': x['title'], 'paras': x['paras']}}, '_src': src})

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

# ---------------- extra languages: merge translations, record per-tier coverage ----------------
EXTRA = [l for l in LANG_META if l not in LANGS and l in XL]
lang_tiers = {l: list(TIERS) for l in LANGS}
for lang in EXTRA:
    have = {t: 0 for t in TIERS}; total = {t: 0 for t in TIERS}
    for d in vocab_rows:
        total[d['tier']] += 1
        tv = XL[lang]['words'].get(d['id'])
        if tv:
            d.setdefault('xl', {})[lang] = [tv[0], tv[1]]
            have[d['tier']] += 1
    lang_tiers[lang] = [t for t in TIERS if total[t] and have[t] == total[t]]
    for t in TIERS:
        if have[t] and have[t] != total[t]:
            warnings.append('%s: %s vocab is partial (%d/%d) — tier not offered for that language' % (lang, t, have[t], total[t]))
    for d in sentences:
        v = XL[lang]['sentences'].get(d['id'])
        if isinstance(v, list) and 3 <= len(v) <= 8 and all(isinstance(x, str) and x.strip() for x in v):
            d[lang] = [x.strip() for x in v]
    for d in dialogues:
        v = XL[lang]['dialogues'].get(d['id'])
        if isinstance(v, list) and len(v) == 5 and all(isinstance(x, str) and x.strip() for x in v):
            d[lang] = [x.strip() for x in v]

for d in sentences:
    claim(d['id'], 'sentence')
    for l in LANGS:
        if not isinstance(d.get(l), list) or not d[l]:
            errors.append('sentence %s missing tiles for %s' % (d['id'], l))
for d in grammar + idioms + nuance:
    claim(d['id'], 'per-lang item')
    if d.get('lang') not in LANG_META:
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

# stories: 7 paragraphs, 4 questions; attach every complete translation under 'xl'
for d in stories:
    claim(d['id'], 'story')
    if len(d.get('paras', [])) != 7 or len(d.get('questions', [])) != 4:
        errors.append('story %s must have 7 paragraphs and 4 questions' % d['id'])
    for q in d.get('questions', []):
        if len(q.get('options', [])) != 4 or not (0 <= q.get('correct', -1) < 4) or not (0 <= q.get('after', -1) < 7):
            errors.append('story %s: bad question %r' % (d['id'], q.get('q')))
    d['xl'] = dict(d.pop('_xl', {}))
    for lang in ([] if d.get('only') else XL):
        v = XL[lang].get('stories', {}).get(d['id'])
        if isinstance(v, dict) and isinstance(v.get('paras'), list) and len(v['paras']) == 7 and v.get('title')                 and all(isinstance(x, str) and x.strip() for x in v['paras']):
            d['xl'][lang] = {'title': v['title'].strip(), 'paras': [x.strip() for x in v['paras']]}
        elif v is not None:
            warnings.append('%s: story %s translation is incomplete, skipped' % (lang, d['id']))

if errors:
    print('BUILD FAILED — %d error(s):' % len(errors))
    for e in errors[:60]:
        print('  -', e)
    sys.exit(1)
for w in warnings[:40]:
    print('  warn:', w)

# ---------------- localization files: l10n/<lang>.json from l10n_out/<lang>_<chunk>.json ----------------
L10N_OUT = os.path.join(HERE, 'l10n_out'); L10N_DIR = os.path.join(HERE, 'l10n')
os.makedirs(L10N_DIR, exist_ok=True)
l10n_report = []
for lang in LANG_META:
    parts = {}
    for chunk in ('notes', 'questions', 'folk_1', 'folk_2', 'folk_3'):
        f = os.path.join(L10N_OUT, '%s_%s.json' % (lang, chunk))
        if not os.path.exists(f): continue
        try:
            parts[chunk] = json.load(open(f, encoding='utf-8'))
        except Exception as e:
            warnings.append('l10n %s/%s does not parse: %s' % (lang, chunk, str(e)[:60]))
    if not parts: continue
    L = {}
    if 'notes' in parts: L.update(parts['notes'])
    if 'questions' in parts: L['questions'] = parts['questions']
    folk = {}
    for k in ('folk_1', 'folk_2', 'folk_3'):
        if k in parts:
            for sid, v in parts[k].items():
                if isinstance(v, dict) and isinstance(v.get('paras'), list) and len(v['paras']) == 7 and v.get('title'):
                    folk[sid] = {'title': v['title'], 'paras': v['paras']}
    if folk: L['folk'] = folk
    with open(os.path.join(L10N_DIR, lang + '.json'), 'w', encoding='utf-8') as fh:
        json.dump(L, fh, ensure_ascii=False, separators=(',', ':'))
    l10n_report.append('%s:%s' % (lang, '+'.join(sorted(parts))))

# ---------------- emit ----------------
def js(v):
    return json.dumps(v, ensure_ascii=False, separators=(',', ':'))

def strip(d):
    return {k: v for k, v in d.items() if not k.startswith('_')}

vocab_js_rows = []
for d in vocab_rows:
    row = [d['id'], d['en'], d['emoji'], d['topic'], d['tier'], d['es'], d['fr'], d['it'], d['pt'], d['ja'], d['zh'], d.get('pinyin', '')]
    if d.get('fact') or d.get('xl'):
        row.append(d.get('fact') or '')
    if d.get('xl'):
        row.append(d['xl'])
    vocab_js_rows.append(js(row))

lang_meta_js = {}
for code, (name, native, flag, speech, reading, audio) in LANG_META.items():
    if code in LANGS or code in XL:
        lang_meta_js[code] = {'name': name, 'native': native, 'flag': flag, 'speech': speech, 'reading': reading,
                              'audio': audio, 'tiers': lang_tiers.get(code, []),
                              'sentences': sum(1 for d in sentences if d.get(code)), 'dialogues': sum(1 for d in dialogues if d.get(code))}

# topic order per tier, in authored order
tier_topics = {}
for d in vocab_rows: tier_topics.setdefault(d['tier'], []).append(d['topic']) if d['topic'] not in tier_topics.get(d['tier'], []) else None

out = []
out.append('  /* ==== GENERATED CONTENT START (build.py — do not hand-edit) ==== */')
out.append('  /* vocab row: [id, en, emoji, topic, tier, es, fr, it, pt, ja, zh, pinyin, fact?, {lang:[text, reading]}?] */')
out.append('  var LANG_META = ' + js(lang_meta_js) + ';')
out.append('  var VOCAB_RAW = [\n' + ',\n'.join('    ' + r for r in vocab_js_rows) + '\n  ];')
out.append('  var TOPIC_LABELS = ' + js(topic_labels) + ';')
out.append('  var BUILD_SENTENCES = [\n' + ',\n'.join('    ' + js(strip(d)) for d in sentences) + '\n  ];')
out.append('  var GRAMMAR_ITEMS = [\n' + ',\n'.join('    ' + js(strip(d)) for d in grammar) + '\n  ];')
out.append('  var IDIOMS = [\n' + ',\n'.join('    ' + js(strip(d)) for d in idioms) + '\n  ];')
out.append('  var NUANCE = [\n' + ',\n'.join('    ' + js(strip(d)) for d in nuance) + '\n  ];')
out.append('  var STORIES = [\n' + ',\n'.join('    ' + js(strip(d)) for d in stories) + '\n  ];')
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
print('stories: %d shared (in %s) + %d folk tales for %s' % (
    sum(1 for d in stories if not d.get('only')), ','.join(sorted(set(l for d in stories if not d.get('only') for l in d['xl']))) or 'nothing yet',
    sum(1 for d in stories if d.get('only')), ','.join(sorted(set(d['only'] for d in stories if d.get('only')))) or 'no language yet'))
print('l10n files:', ' '.join(l10n_report) or 'none yet')
print('sentences %d | grammar %d | idioms %d | nuance %d | dialogues %d | listen modules %d' % (
    len(sentences), len(grammar), len(idioms), len(nuance), len(dialogues), len(listen)))
for code in EXTRA:
    print('  +%s %s: tiers %s, sentences %d, dialogues %d' % (code, LANG_META[code][0], ','.join(lang_tiers[code]) or 'none',
          lang_meta_js[code]['sentences'], lang_meta_js[code]['dialogues']))
print('generated block: %d KB' % (len(block.encode('utf-8')) // 1024))
