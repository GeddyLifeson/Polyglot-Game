# -*- coding: utf-8 -*-
"""Every user-visible interface string of index.html, in English (the source and the key of the `ui` pool).

Sources, in page order:
  - the static HTML: inner HTML of elements marked `data-t`, and every title / placeholder / aria-label attribute
  - the hand-written script: every _t('…') literal, the display fields of the data tables
    (name, desc, title, label, ladder, sub, how, count, unlock, clearance), HOW_TEXT and RARITY_LABEL values
  - the generated block: topic labels, language names, folk-tale origins, word facts

Used by tools/l10n_prep.py (writes l10n_in/ui.json) and build.py (coverage report). The game applies the same
keys at runtime: _t() for literals, applyUiL10n() for the tables, applyStaticUi() for the markup."""
import html as htmllib, json, re
from collections import OrderedDict

FIELDS = r'name|desc|title|label|ladder|sub|how|count|unlock|clearance'

def js_unescape(s):
    def rep(m):
        e = m.group(1)
        if e[0] == 'u': return chr(int(e[1:], 16))
        return {'n': '\n', 't': '\t', 'r': '\r'}.get(e, e)
    return re.sub(r'\\(u[0-9a-fA-F]{4}|.)', rep, s)

def _norm_inner(s):
    # what the browser's innerHTML gives back for our simple markup: trimmed, bare attributes written as =""
    return s.strip()

def extract(h):
    out = OrderedDict()
    def add(s):
        if s is None: return
        s = s.strip() if isinstance(s, str) else s
        if not s or not re.search(r'[A-Za-z]', re.sub(r'<[^>]*>|\{\w+\}', '', s)): return
        out.setdefault(s, s)
    body = h[h.index('<body'):h.index('<script>', h.index('<body'))]
    for m in re.finditer(r'<(\w+)\b([^>]*?)\sdata-t(?:="")?(\s[^>]*)?>(.*?)</\1>', body, re.S):
        add(_norm_inner(m.group(4)))
    for m in re.finditer(r'\s(title|placeholder|aria-label)="([^"]*)"', body):
        add(htmllib.unescape(m.group(2)))
    a = h.index('/* ==== AUDIO CLIPS END ==== */'); b = h.index('</script>', a)
    js = h[a:b]
    # the data tables sit before the COACH texts; _t() literals and table fields are collected in source order
    lit = r"'((?:[^'\\]|\\.)*)'"
    for m in re.finditer(r"\b_t\(\s*" + lit + r"|\b(?:" + FIELDS + r"):\s*" + lit, js):
        add(js_unescape(m.group(1) if m.group(1) is not None else m.group(2)))
    for var in ('HOW_TEXT', 'RARITY_LABEL'):
        m = re.search(r'var ' + var + r' = \{(.*?)\};', js, re.S)
        for v in re.findall(r"\w+\s*:\s*" + lit, m.group(1)): add(js_unescape(v))
    # generated content
    g0 = h.index('/* ==== GENERATED CONTENT START'); g1 = h.index('/* ==== GENERATED CONTENT END')
    gen = h[g0:g1]
    for v in json.loads(re.search(r'var TOPIC_LABELS = (\{.*?\});', gen).group(1)).values(): add(v)
    for v in json.loads(re.search(r'var LANG_META = (\{.*?\});\n', gen).group(1)).values(): add(v['name'])
    add('English')
    for s in json.loads(re.search(r'var STORIES = (\[.*?\n  \]);', gen, re.S).group(1)):
        if s.get('origin'): add(s['origin'])
    for r in json.loads(re.search(r'var VOCAB_RAW = (\[.*?\n  \]);', gen, re.S).group(1)):
        if len(r) > 12 and r[12]: add(r[12])
    return out

PH = re.compile(r'\{(\w+)\}')
TAG = re.compile(r'</?([a-zA-Z]+)')

def check_pair(src, tr):
    """problems with one translated ui string: placeholders and HTML tags must survive unchanged"""
    probs = []
    if sorted(PH.findall(src)) != sorted(PH.findall(tr)): probs.append('placeholders differ')
    if sorted(TAG.findall(src)) != sorted(TAG.findall(tr)): probs.append('html tags differ')
    return probs

if __name__ == '__main__':
    import os, sys
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    u = extract(open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read())
    print(len(u), 'ui strings,', sum(len(k.split()) for k in u), 'words')
    if '-v' in sys.argv:
        for k in u: print(' ', k[:120])
