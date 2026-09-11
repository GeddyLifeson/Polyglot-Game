# -*- coding: utf-8 -*-
"""Validate one translated chunk: python tools/l10n_check.py <lang> <chunk>   (chunk = notes | questions | folk_1..3)
The output must mirror the input's keys and array lengths, with no empty strings. For folk chunks, tales whose own
language is <lang> are skipped (they already exist natively) and must NOT be present."""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lang, chunk = sys.argv[1], sys.argv[2]
src = json.load(open(os.path.join(ROOT, 'l10n_in', chunk + '.json'), encoding='utf-8'))
path = os.path.join(ROOT, 'l10n_out', '%s_%s.json' % (lang, chunk))
try:
    out = json.load(open(path, encoding='utf-8'))
except Exception as e:
    print('BAD: cannot load', path, e); sys.exit(1)
probs = []
def s_ok(v): return isinstance(v, str) and v.strip() != ''
same = total = 0
def cmp(a, b, where):
    global same, total
    if isinstance(a, dict):
        if not isinstance(b, dict): probs.append(where + ': expected object'); return
        for k in a:
            if k not in b: probs.append(where + '.' + k + ': missing'); continue
            cmp(a[k], b[k], where + '.' + k)
    elif isinstance(a, list):
        if not isinstance(b, list) or len(a) != len(b): probs.append(where + ': expected list of %d' % len(a)); return
        for i, (x, y) in enumerate(zip(a, b)): cmp(x, y, where + '[%d]' % i)
    else:
        if not s_ok(b): probs.append(where + ': empty'); return
        total += 1
        if b.strip() == str(a).strip() and len(str(a)) > 12: same += 1
if chunk.startswith('folk'):
    for sid, v in src.items():
        if v['lang'] == lang:
            if sid in out: probs.append(sid + ': is native to ' + lang + ', must not be translated')
            continue
        if sid not in out: probs.append(sid + ': missing'); continue
        cmp({'title': v['title'], 'paras': v['paras']}, out[sid], sid)
else:
    cmp(src, out, chunk)
if total and same / total > 0.25: probs.append('%d of %d strings are unchanged English' % (same, total))
if probs:
    print('BAD (%d):' % len(probs)); [print(' ', p) for p in probs[:25]]; sys.exit(1)
print('OK', lang, chunk, total, 'strings')
